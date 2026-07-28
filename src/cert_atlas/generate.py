"""Generate the atlas: valid artifacts and labelled near-miss forgeries.

Determinism matters more than variety here. A benchmark whose cases move between
runs cannot be used to compare verifiers, so every case is built from fixed
inputs and the whole atlas is content-addressed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Callable, Dict, List

import equiv_receipt as E
import lcert_verify as L
import prereg_seal as P
from lcert_verify import _verifier as V

from .defects import DEFECTS

ATLAS_VERSION = "1.0.0"

# Fixed inputs. Never randomise: the atlas must be byte-reproducible.
GOOD_LOCI = [(0.10, 0.11, 0.05), (0.09, 0.10, 0.04), (0.12, 0.13, 0.06)]
SPEC = {"criterion": "worst-corner edge placement within budget",
        "threshold_nm": 3.0, "corners": ["nominal", "defocus+", "defocus-"]}


def _cert():
    return L.gate_cert("clip", budget=0.05, safety=1.5, n_photons=100.0,
                       thr=0.30, delta_dose=0.02, loci=GOOD_LOCI)


def _write_bundle(d: Path, mutate: Callable | None = None) -> Path:
    L.make_bundle(d, gate_certs=[_cert()],
                  kpis=[{"key": "worst_pfail_upper", "value": 0.0041}],
                  prereg={"declared": "before measurement", "budget": 0.05})
    if mutate is not None:
        mutate(d)
    return d


# ---------------- certificate mutations ----------------

def _edit(d: Path, fn, canonical: bool = True) -> None:
    p = d / "bundle.json"
    b = json.loads(p.read_text())
    fn(b)
    p.write_bytes((V._canon(b) + b"\n") if canonical else (json.dumps(b, indent=1).encode()))


CERT_MUTATIONS: Dict[str, Callable[[Path], None]] = {
    "cert.forged_verdict":
        lambda d: _edit(d, lambda b: b["gate_certs"][0]["recorded"]
                        .__setitem__("interval_admit", False)),
    "cert.mutated_intensity":
        lambda d: _edit(d, lambda b: b["gate_certs"][0]["loci"]["I_hi"].__setitem__(0, 0.31)),
    "cert.inflated_photons":
        lambda d: _edit(d, lambda b: b["gate_certs"][0].__setitem__("n_photons", 1e12)),
    "cert.tampered_kappa":
        lambda d: _edit(d, lambda b: b["gate_certs"][0].__setitem__(
            "kappa", b["gate_certs"][0]["kappa"] * 1.01)),
    "cert.dropped_field":
        lambda d: _edit(d, lambda b: b["gate_certs"][0]["recorded"].pop("n_straddle", None)),
    "cert.vacuous":
        lambda d: _edit(d, lambda b: b.__setitem__("gate_certs", [])),
    "cert.broken_manifest":
        lambda d: (d / "preregistration.json").write_bytes(b'{"declared": "after the fact"}\n'),
    "cert.broken_merkle":
        lambda d: _edit(d, lambda b: b.__setitem__("merkle_root", "00" * 32)),
    "cert.broken_outputs_commitment":
        lambda d: _edit(d, lambda b: b.__setitem__(
            "kpis", [{"key": "worst_pfail_upper", "value": 1e-9}])),
    "cert.noncanonical":
        lambda d: _edit(d, lambda b: None, canonical=False),
    "cert.self_consistent_forgery":
        lambda d: _self_consistent(d),
}


def _self_consistent(d: Path) -> None:
    """Rewrite the physics to something safe, then recompute the verdict to match.

    The result is internally flawless: it is a lie only relative to the artifact
    that was actually measured, and only an out-of-band fingerprint reveals it.
    """
    def fn(b):
        c = b["gate_certs"][0]
        n = len(c["loci"]["ae0"])
        c["loci"]["I_lo"] = [0.10] * n
        c["loci"]["I_hi"] = [0.11] * n
        red = V.rederive_gate_verdict(c)
        c["recorded"] = dict(red)
        c["recorded"]["float_admit"] = red["interval_admit"]
        c["recorded"]["match"] = True
    _edit(d, fn)


# ---------------- receipt mutations ----------------

def _f(n, p):
    return n.AND(p + "and", "a", "b")


def _g(n, p):
    n.NOT(p + "na", "a")
    n.NOT(p + "nb", "b")
    n.OR(p + "or", p + "na", p + "nb")
    return n.NOT(p + "out", p + "or")


def _h(n, p):
    return n.OR(p + "or", "a", "b")


def _good_receipt():
    return E.prove_equivalence(_f, _g, ["a", "b"], name_a="a AND b",
                               name_b="NOT(NOT a OR NOT b)")


def _cex_receipt():
    return E.prove_equivalence(_f, _h, ["a", "b"], name_a="a AND b", name_b="a OR b")


def _set_verdict(r, verdict):
    for rec in r["records"]:
        if rec.get("kind") == "verdict":
            rec["verdict"] = verdict
    return r


def _m_unjustified_empty(r):
    r = _set_verdict(copy.deepcopy(_cex_receipt()), "EQUIVALENT")
    r["payload"]["drat"] = "0\n"
    return r


def _m_non_rup(r):
    r = copy.deepcopy(r)
    r["payload"]["drat"] = "1 0\n0\n"
    return r


def _m_swapped_cnf(r):
    r = _set_verdict(copy.deepcopy(_cex_receipt()), "EQUIVALENT")
    r["payload"]["cnf"] = "p cnf 1 2\n1 0\n-1 0\n"
    r["payload"]["drat"] = "0\n"
    return r


def _m_swapped_description(r):
    r = copy.deepcopy(r)
    r["payload"]["description_b"] = "a completely different circuit"
    return r


def _m_forged_cex(r):
    r = copy.deepcopy(_cex_receipt())
    for rec in r["records"]:
        if rec.get("kind") == "verdict":
            rec["counterexample"] = {"1": False, "2": False}
    return r


def _m_truncated_chain(r):
    r = copy.deepcopy(r)
    r["records"] = r["records"][:1]
    return r


def _m_broken_link(r):
    r = copy.deepcopy(r)
    r["records"][1]["prev"] = "ff" * 32
    return r


def _m_swapped_encoder(r):
    r = copy.deepcopy(r)
    r["payload"]["encoder_id"] = "untrusted-encoder/9"
    return r


RECEIPT_MUTATIONS = {
    "receipt.unjustified_empty_clause": _m_unjustified_empty,
    "receipt.non_rup_lemma": _m_non_rup,
    "receipt.swapped_cnf": _m_swapped_cnf,
    "receipt.swapped_description": _m_swapped_description,
    "receipt.forged_counterexample": _m_forged_cex,
    "receipt.truncated_chain": _m_truncated_chain,
    "receipt.broken_chain_link": _m_broken_link,
    "receipt.swapped_encoder": _m_swapped_encoder,
}


# ---------------- seal mutations ----------------

def _seal_cases() -> List[dict]:
    sealed = P.seal(SPEC)
    bound = P.bind({"measured_nm": 2.4, "verdict": "PASS"}, P.seal(SPEC))
    doctored = dict(SPEC, threshold_nm=9.9)
    return [
        {"key": "seal.valid", "valid": True, "spec": SPEC, "seal": sealed, "bound": None},
        {"key": "seal.valid_bound", "valid": True, "spec": SPEC, "seal": None, "bound": bound},
        {"key": "seal.moved_threshold", "valid": False, "spec": doctored,
         "seal": sealed, "bound": None},
        {"key": "seal.repointed_bound_seal", "valid": False, "spec": doctored, "seal": None,
         "bound": dict(bound, seal=P.seal(doctored))},
        {"key": "seal.altered_result", "valid": False, "spec": SPEC, "seal": None,
         "bound": dict(bound, measured_nm=99.0)},
    ]


# ---------------- driver ----------------

def build(out_dir) -> dict:
    """Write the full atlas. Returns the index."""
    out = Path(out_dir)
    if out.exists():
        import shutil
        shutil.rmtree(out)
    (out / "certificates").mkdir(parents=True)
    (out / "receipts").mkdir(parents=True)
    (out / "seals").mkdir(parents=True)

    cases = []

    _write_bundle(out / "certificates" / "valid")
    genuine_fp = _fingerprint(out / "certificates" / "valid")
    cases.append({"id": "cert.valid", "family": "certificate", "valid": True,
                  "path": "certificates/valid", "defect": None,
                  "expected_fingerprint": genuine_fp})

    for key, mut in CERT_MUTATIONS.items():
        name = key.split(".", 1)[1]
        _write_bundle(out / "certificates" / name, mut)
        # Every certificate case carries the fingerprint of the GENUINE artifact,
        # standing in for a value a real user obtains out of band.
        cases.append({"id": key, "family": "certificate", "valid": False,
                      "path": f"certificates/{name}", "defect": key,
                      "expected_fingerprint": genuine_fp})

    good = _good_receipt()
    (out / "receipts" / "valid.json").write_bytes(E.canon(good) + b"\n")
    cases.append({"id": "receipt.valid", "family": "receipt", "valid": True,
                  "path": "receipts/valid.json", "defect": None})
    cex = _cex_receipt()
    (out / "receipts" / "valid_counterexample.json").write_bytes(E.canon(cex) + b"\n")
    cases.append({"id": "receipt.valid_counterexample", "family": "receipt", "valid": True,
                  "path": "receipts/valid_counterexample.json", "defect": None})

    for key, mut in RECEIPT_MUTATIONS.items():
        name = key.split(".", 1)[1]
        r = mut(good)
        (out / "receipts" / f"{name}.json").write_bytes(E.canon(r) + b"\n")
        cases.append({"id": key, "family": "receipt", "valid": False,
                      "path": f"receipts/{name}.json", "defect": key})

    for c in _seal_cases():
        name = c["key"].split(".", 1)[1]
        payload = {k: v for k, v in c.items() if k != "key"}
        (out / "seals" / f"{name}.json").write_bytes(
            json.dumps(payload, indent=1, sort_keys=True).encode() + b"\n")
        cases.append({"id": c["key"], "family": "seal", "valid": c["valid"],
                      "path": f"seals/{name}.json",
                      "defect": None if c["valid"] else c["key"]})

    for c in cases:
        if c["defect"]:
            d = DEFECTS[c["defect"]]
            c["severity"] = d.severity
            c["title"] = d.title
            c["caught_by"] = d.caught_by

    index = {
        "atlas_version": ATLAS_VERSION,
        "n_cases": len(cases),
        "n_valid": sum(1 for c in cases if c["valid"]),
        "n_invalid": sum(1 for c in cases if not c["valid"]),
        "families": sorted({c["family"] for c in cases}),
        "cases": cases,
    }
    (out / "index.json").write_bytes(
        json.dumps(index, indent=1, sort_keys=True).encode() + b"\n")
    index["digest"] = atlas_digest(out)
    (out / "index.json").write_bytes(
        json.dumps(index, indent=1, sort_keys=True).encode() + b"\n")
    return index


def _fingerprint(bundle_dir) -> str:
    return hashlib.sha256((Path(bundle_dir) / "bundle.json").read_bytes()).hexdigest()


def atlas_digest(out_dir) -> str:
    """Content digest over every file except the index itself."""
    out = Path(out_dir)
    h = hashlib.sha256()
    for f in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "index.json"):
        h.update(str(f.relative_to(out)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()
