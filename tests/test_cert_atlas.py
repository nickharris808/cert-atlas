"""Tests for cert-atlas.

The important ones: the atlas is byte-reproducible (or it cannot be used to
compare verifiers across time), every declared defect is genuinely caught by the
reference (or the taxonomy is aspirational), and the metric cannot be gamed from
either side.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import cert_atlas as A
from cert_atlas.defects import DEFECTS
from cert_atlas.reference import accept_everything, reference_verifier, reject_everything


@pytest.fixture(scope="module")
def atlas(tmp_path_factory):
    d = tmp_path_factory.mktemp("atlas")
    A.build(d)
    return d


# ---------- reproducibility ----------

def test_atlas_is_byte_reproducible(tmp_path):
    """Two builds must be identical, or cross-run comparison is meaningless."""
    a, b = tmp_path / "a", tmp_path / "b"
    ix_a, ix_b = A.build(a), A.build(b)
    assert ix_a["digest"] == ix_b["digest"]
    assert A.atlas_digest(a) == A.atlas_digest(b)


def test_digest_changes_if_any_case_changes(atlas, tmp_path):
    before = A.atlas_digest(atlas)
    victim = next(p for p in Path(atlas).rglob("*.json") if p.name != "index.json")
    original = victim.read_bytes()
    try:
        victim.write_bytes(original + b" ")
        assert A.atlas_digest(atlas) != before
    finally:
        victim.write_bytes(original)


# ---------- the reference catches everything it claims to ----------

def test_reference_is_sound_on_the_whole_atlas(atlas):
    res = A.score(atlas, reference_verifier)
    assert res["detection"] == 1.0, f"forgeries got through: {res['missed']}"
    assert res["precision"] == 1.0, f"false alarms: {res['false_alarms']}"
    assert res["sound"] is True


def test_every_declared_defect_has_a_case(atlas):
    ix = A.load_index(atlas)
    covered = {c["defect"] for c in ix["cases"] if c["defect"]}
    missing = set(DEFECTS) - covered
    assert not missing, f"taxonomy declares defects with no case: {sorted(missing)}"


def test_every_case_defect_is_in_the_taxonomy(atlas):
    ix = A.load_index(atlas)
    for c in ix["cases"]:
        if c["defect"]:
            assert c["defect"] in DEFECTS, f"case cites unknown defect {c['defect']}"


@pytest.mark.parametrize("key", sorted(DEFECTS))
def test_each_defect_is_individually_caught(atlas, key):
    """Per-defect, not just in aggregate — an aggregate can hide a specific miss."""
    ix = A.load_index(atlas)
    case = next(c for c in ix["cases"] if c["defect"] == key)
    accepted = reference_verifier(str(Path(atlas) / case["path"]), case)
    assert accepted is False, f"reference verifier ACCEPTED forgery {key}"


# ---------- the metric resists gaming ----------

def test_accept_everything_scores_zero(atlas):
    res = A.score(atlas, accept_everything)
    assert res["precision"] == 1.0        # perfect on one side...
    assert res["detection"] == 0.0        # ...and useless on the other
    assert res["atlas_score"] == 0.0


def test_reject_everything_scores_zero(atlas):
    res = A.score(atlas, reject_everything)
    assert res["detection"] == 1.0        # "sound" by refusing everything
    assert res["precision"] == 0.0
    assert res["atlas_score"] == 0.0


def test_score_is_the_minimum_of_both_halves(atlas):
    for fn in (reference_verifier, accept_everything, reject_everything):
        r = A.score(atlas, fn)
        assert r["atlas_score"] == min(r["detection"], r["precision"])


def test_a_crashing_verifier_does_not_score_as_accepting(atlas):
    def boom(path, case):
        raise RuntimeError("verifier exploded")
    res = A.score(atlas, boom)
    assert res["detection"] == 1.0        # crashes count as rejections
    assert res["precision"] == 0.0        # so it still cannot win
    assert res["atlas_score"] == 0.0
    assert len(res["errors"]) == res["n_cases"]


# ---------- composition of the atlas ----------

def test_atlas_has_both_valid_and_invalid_cases(atlas):
    ix = A.load_index(atlas)
    assert ix["n_valid"] >= 4 and ix["n_invalid"] >= 15
    assert ix["n_valid"] + ix["n_invalid"] == ix["n_cases"]


def test_all_three_families_present(atlas):
    ix = A.load_index(atlas)
    assert set(ix["families"]) == {"certificate", "receipt", "seal"}


def test_valid_cases_really_are_valid(atlas):
    """A 'valid' case the reference rejects would poison the precision metric."""
    ix = A.load_index(atlas)
    for c in ix["cases"]:
        if c["valid"]:
            assert reference_verifier(str(Path(atlas) / c["path"]), c) is True, c["id"]


def test_severity_labels_are_from_the_fixed_set(atlas):
    assert {d.severity for d in DEFECTS.values()} <= {"soundness", "integrity", "vacuity"}


def test_soundness_defects_dominate():
    """The atlas should mostly test soundness, not formatting."""
    n_sound = sum(1 for d in DEFECTS.values() if d.severity == "soundness")
    assert n_sound >= len(DEFECTS) // 2


# ---------- CLI ----------

def _env():
    root = Path(__file__).parent.parent
    return {"PYTHONPATH": ":".join(str(p) for p in [
        root / "src", root.parent / "lcert-verify" / "src",
        root.parent / "equiv-receipt" / "src", root.parent / "prereg-seal" / "src"]),
        "PATH": ""}


def test_cli_build_and_baseline(tmp_path):
    out = tmp_path / "cli_atlas"
    r = subprocess.run([sys.executable, "-m", "cert_atlas.cli", "build", str(out)],
                       capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stderr
    r = subprocess.run([sys.executable, "-m", "cert_atlas.cli", "baseline", str(out), "--json"],
                       capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["atlas_score"] == 1.0


def test_cli_defects_lists_taxonomy():
    r = subprocess.run([sys.executable, "-m", "cert_atlas.cli", "defects"],
                       capture_output=True, text=True, env=_env())
    assert r.returncode == 0
    assert "cert.forged_verdict" in r.stdout and "caught by" in r.stdout


def test_cli_score_external_command_that_accepts_everything(tmp_path):
    """Scoring `true` — a command that accepts everything — must fail the gate."""
    out = tmp_path / "a2"
    subprocess.run([sys.executable, "-m", "cert_atlas.cli", "build", str(out)],
                   capture_output=True, env=_env())
    r = subprocess.run([sys.executable, "-m", "cert_atlas.cli", "score", str(out),
                        "true", "{path}"], capture_output=True, text=True,
                       env={**_env(), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 1
    assert "ATLAS SCORE 0.000" in r.stdout


# ---------- dataset export ----------

def test_export_writes_jsonl_and_schema(atlas, tmp_path):
    import cert_atlas as A
    counts = A.hf_export(atlas, tmp_path)
    assert counts == {"valid": 5, "invalid": 21}
    for split, n in counts.items():
        p = tmp_path / "data" / f"{split}-00000.jsonl"
        lines = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        assert len(lines) == n
    schema = json.loads((tmp_path / "schema.json").read_text())
    assert schema["atlas_digest"] == A.load_index(atlas)["digest"]
    # artifacts are stored as a JSON string plus a filename list: a mapping whose keys
    # vary per row breaks columnar schema inference on dataset hubs.
    assert "artifact_json" in schema["fields"]
    assert "artifact_files" in schema["fields"]


def test_exported_rows_reconstruct_the_artifact(atlas, tmp_path):
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / "data" / "invalid-00000.jsonl").read_text().splitlines() if x.strip()]
    cert_row = next(r for r in rows if r["family"] == "certificate")
    assert "bundle.json" in cert_row["artifact_files"]
    art = json.loads(cert_row["artifact_json"])
    json.loads(art["bundle.json"])                           # must be real, parseable content


def test_exported_columns_have_one_stable_type_each(atlas, tmp_path):
    """Columnar viewers infer a schema; a column that is null in one split and a
    string in another, or a struct whose keys vary per row, breaks them."""
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    for split in ("valid", "invalid"):
        rows = [json.loads(x) for x in
                (tmp_path / "data" / f"{split}-00000.jsonl").read_text().splitlines() if x.strip()]
        for key in rows[0]:
            kinds = {type(r[key]).__name__ for r in rows}
            assert len(kinds) == 1, f"{split}.{key} has mixed types {kinds}"
            assert None not in [r[key] for r in rows], f"{split}.{key} contains null"


def test_artifact_json_round_trips(atlas, tmp_path):
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / "data" / "invalid-00000.jsonl").read_text().splitlines() if x.strip()]
    for r in rows:
        art = json.loads(r["artifact_json"])
        assert sorted(art) == r["artifact_files"]
        assert all(isinstance(v, str) and v for v in art.values())


def test_every_exported_row_carries_its_label(atlas, tmp_path):
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / "data" / "invalid-00000.jsonl").read_text().splitlines() if x.strip()]
    for r in rows:
        assert r["defect"] and r["severity"] and r["caught_by"] and r["why_it_looks_valid"]


def test_valid_rows_use_empty_strings_not_nulls(atlas, tmp_path):
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / "data" / "valid-00000.jsonl").read_text().splitlines() if x.strip()]
    for r in rows:
        for k in ("defect", "severity", "title", "why_it_looks_valid", "caught_by"):
            assert r[k] == "", f"{r['id']}.{k} should be an empty string, got {r[k]!r}"


def test_shipped_dataset_matches_a_fresh_export(tmp_path):
    """The committed dataset must not drift from the generator."""
    import cert_atlas as A
    a = tmp_path / "atlas"
    A.build(a)
    A.hf_export(a, tmp_path / "out")
    shipped = Path(__file__).parent.parent / "dataset"
    for split in ("valid", "invalid"):
        fresh = (tmp_path / "out" / "data" / f"{split}-00000.jsonl").read_text()
        assert (shipped / "data" / f"{split}-00000.jsonl").read_text() == fresh, \
            f"committed {split} shard is stale — re-run `cert-atlas export`"


def test_standalone_loader_needs_no_dependencies():
    import importlib.util
    shipped = Path(__file__).parent.parent / "dataset"
    spec = importlib.util.spec_from_file_location("atlas_loader", shipped / "loader.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    d = mod.load(shipped)
    assert len(d["valid"]) == 5 and len(d["invalid"]) == 21
    assert mod.schema(shipped)["atlas_digest"]
    assert len(list(mod.iter_forgeries(shipped))) == 21


def test_list_columns_are_never_empty_across_a_whole_split(atlas, tmp_path):
    """Regression: an all-empty list column infers as list<null> and will not
    unify with the list<string> of the other split, which broke the dataset
    viewer. Every list column must be non-empty on at least one row per split —
    in practice, on every row."""
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    for split in ("valid", "invalid"):
        rows = [json.loads(x) for x in
                (tmp_path / "data" / f"{split}-00000.jsonl").read_text().splitlines() if x.strip()]
        for key in ("tags", "artifact_files"):
            assert all(r[key] for r in rows), f"{split}.{key} is empty on some row"
            assert all(isinstance(v, str) for r in rows for v in r[key])


def test_both_splits_load_together_if_datasets_is_available(atlas, tmp_path):
    """The exact failure the viewer hit: splits that load alone but not together."""
    datasets = pytest.importorskip("datasets")
    import cert_atlas as A
    A.hf_export(atlas, tmp_path)
    ds = datasets.load_dataset("json", data_files={
        "valid": str(tmp_path / "data" / "valid-00000.jsonl"),
        "invalid": str(tmp_path / "data" / "invalid-00000.jsonl")})
    assert len(ds["valid"]) == 5 and len(ds["invalid"]) == 21
