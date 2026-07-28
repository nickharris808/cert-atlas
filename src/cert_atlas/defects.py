"""The defect taxonomy — every way a certificate can be wrong while looking right.

Each defect is a *named, reproducible mutation* applied to a valid artifact. The
atlas exists because verifiers are usually tested on artifacts they accept. What
matters is what they reject, and nobody publishes a corpus of near-miss forgeries.

Every entry records: what was mutated, why a naive verifier might miss it, and
which check is supposed to catch it. A defect nobody's verifier catches is more
interesting than one everybody catches, so the atlas keeps both.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

CERT = "certificate"
RECEIPT = "receipt"
SEAL = "seal"
SEQ = "sequential"


@dataclass(frozen=True)
class Defect:
    """One labelled way of being wrong."""
    key: str
    family: str                 # CERT | RECEIPT | SEAL
    title: str
    why_it_looks_valid: str
    caught_by: str
    severity: str               # "soundness" | "integrity" | "vacuity"
    tags: List[str] = field(default_factory=list)


DEFECTS: Dict[str, Defect] = {}


def _d(**kw) -> Defect:
    d = Defect(**kw)
    DEFECTS[d.key] = d
    return d


# ---------------- certificate-family defects ----------------

_d(key="cert.forged_verdict", family=CERT, severity="soundness",
   title="Recorded verdict flipped to ADMIT",
   why_it_looks_valid="Every other field is untouched and internally consistent; only "
                      "the recorded outcome is a lie.",
   caught_by="Re-deriving the verdict from the per-locus data instead of reading it.",
   tags=["verdict", "trust-the-producer"])

_d(key="cert.mutated_intensity", family=CERT, severity="soundness",
   title="A locus intensity moved across the threshold, verdict left as ADMIT",
   why_it_looks_valid="The certificate still parses and its structure is intact.",
   caught_by="Re-deriving the per-locus classification.",
   tags=["physics-input", "verdict"])

_d(key="cert.inflated_photons", family=CERT, severity="soundness",
   title="Photon count inflated to shrink the safety constant",
   why_it_looks_valid="A larger photon budget is a physically meaningful edit, so the "
                      "number looks plausible in isolation.",
   caught_by="Recomputing K bit-identically from (kappa, safety, n_photons).",
   tags=["derived-constant"])

_d(key="cert.tampered_kappa", family=CERT, severity="soundness",
   title="kappa perturbed so the stated budget no longer holds",
   why_it_looks_valid="kappa is an opaque constant most readers will not check.",
   caught_by="The erfc round-trip against the declared budget.",
   tags=["derived-constant", "transcendental"])

_d(key="cert.dropped_field", family=CERT, severity="integrity",
   title="A re-derived field deleted from the record to dodge comparison",
   why_it_looks_valid="Absence is easy to mistake for 'not applicable'.",
   caught_by="Comparing every re-derived field, treating a missing one as a mismatch.",
   tags=["omission"])

_d(key="cert.vacuous", family=CERT, severity="vacuity",
   title="All certificates stripped; the bundle is empty but well-formed",
   why_it_looks_valid="An empty bundle is trivially internally consistent, so a pure "
                      "format check reports success.",
   caught_by="Refusing a bundle that certifies nothing.",
   tags=["vacuity", "the-quiet-one"])

_d(key="cert.self_consistent_forgery", family=CERT, severity="soundness",
   title="Physics inputs AND recorded verdict edited together, so they agree",
   why_it_looks_valid="Every internal check passes. The forger simply did the interval "
                      "arithmetic correctly on fabricated inputs, so re-derivation "
                      "reproduces exactly the verdict that was recorded.",
   caught_by="An out-of-band fingerprint ONLY. No amount of internal checking can "
             "distinguish this from a genuine certificate — which is why the reference "
             "verifier abstains (UNVERIFIED) rather than passing when no anchor is given.",
   tags=["verdict", "physics-input", "requires-anchor", "the-honest-limit"])

_d(key="cert.broken_manifest", family=CERT, severity="integrity",
   title="A payload file edited after the manifest was written",
   why_it_looks_valid="The bundle metadata is untouched.",
   caught_by="Re-hashing every payload file against the manifest.",
   tags=["payload"])

_d(key="cert.broken_merkle", family=CERT, severity="integrity",
   title="Merkle root replaced",
   why_it_looks_valid="The root is an opaque hex string.",
   caught_by="Recomputing the root from the manifest.",
   tags=["commitment"])

_d(key="cert.broken_outputs_commitment", family=CERT, severity="integrity",
   title="A reported value edited without updating its commitment",
   why_it_looks_valid="The value is plausible and the rest of the bundle verifies.",
   caught_by="Recomputing the outputs commitment over the reported values.",
   tags=["reported-values"])

_d(key="cert.noncanonical", family=CERT, severity="integrity",
   title="Bundle re-serialized with different byte formatting",
   why_it_looks_valid="Semantically identical JSON; only the bytes differ.",
   caught_by="A canonical-form round-trip, or a fingerprint obtained out of band.",
   tags=["serialization"])

# ---------------- receipt-family defects ----------------

_d(key="receipt.unjustified_empty_clause", family=RECEIPT, severity="soundness",
   title="Empty clause asserted with no derivation",
   why_it_looks_valid="A one-line proof of an unsatisfiable-looking formula.",
   caught_by="RUP-checking every lemma, including the empty one.",
   tags=["drat", "proof"])

_d(key="receipt.non_rup_lemma", family=RECEIPT, severity="soundness",
   title="A lemma inserted that does not follow by unit propagation",
   why_it_looks_valid="The proof has the right shape and ends in a contradiction.",
   caught_by="Checking each lemma is RUP against the active clause set.",
   tags=["drat", "proof"])

_d(key="receipt.swapped_cnf", family=RECEIPT, severity="soundness",
   title="Formula replaced by a trivially unsatisfiable one",
   why_it_looks_valid="The proof genuinely refutes the formula presented — just not "
                      "the formula that corresponds to the circuits.",
   caught_by="Committing the formula and the encoder identity, and checking both.",
   tags=["encoding", "the-subtle-one"])

_d(key="receipt.swapped_description", family=RECEIPT, severity="soundness",
   title="One circuit description swapped after the proof was made",
   why_it_looks_valid="Proof and formula are genuinely valid; only the claim about "
                      "*what* was proven is false.",
   caught_by="Binding both descriptions into the commitment.",
   tags=["binding"])

_d(key="receipt.forged_counterexample", family=RECEIPT, severity="soundness",
   title="Counterexample that does not satisfy the formula",
   why_it_looks_valid="A plausible-looking assignment over the right variables.",
   caught_by="Re-simulating the assignment against the committed formula.",
   tags=["counterexample"])

_d(key="receipt.truncated_chain", family=RECEIPT, severity="integrity",
   title="Trailing records removed from the hash chain",
   why_it_looks_valid="The surviving prefix is internally consistent.",
   caught_by="Requiring the chain to reach a terminal record.",
   tags=["chain"])

_d(key="receipt.broken_chain_link", family=RECEIPT, severity="integrity",
   title="A record's predecessor digest altered",
   why_it_looks_valid="Individual records still parse.",
   caught_by="Recomputing each link.",
   tags=["chain"])

_d(key="receipt.swapped_encoder", family=RECEIPT, severity="soundness",
   title="Encoder identity replaced with an untrusted one",
   why_it_looks_valid="The formula and proof are unchanged and valid.",
   caught_by="Committing the encoder identity so a substitution is visible.",
   tags=["provenance"])

# ---------------- seal-family defects ----------------

_d(key="seal.moved_threshold", family=SEAL, severity="soundness",
   title="Acceptance threshold loosened after sealing",
   why_it_looks_valid="The specification is well-formed and the seal file exists.",
   caught_by="Recomputing the digest of the specification actually in force.",
   tags=["preregistration"])

_d(key="seal.repointed_bound_seal", family=SEAL, severity="soundness",
   title="Specification doctored AND a matching seal minted",
   why_it_looks_valid="Specification and seal agree with each other perfectly.",
   caught_by="A binding that covers the result and the seal together.",
   tags=["preregistration", "the-hard-direction"])

_d(key="seal.altered_result", family=SEAL, severity="soundness",
   title="Measured result edited after binding",
   why_it_looks_valid="The seal still matches the specification.",
   caught_by="Recomputing the binding over result and seal.",
   tags=["preregistration"])


def by_family(family: str) -> List[Defect]:
    return [d for d in DEFECTS.values() if d.family == family]


def summary() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for d in DEFECTS.values():
        out[d.family] = out.get(d.family, 0) + 1
    return out


# ---------------------------------------------------------------- sequential receipts
#
# A sequential equivalence receipt is several proof obligations plus an inductive
# argument over them. That is more surface than a single refutation, and two of
# the defects below have no analogue in the other families: an argument can be
# *incomplete* rather than wrong, and a formula can be a valid proof of the wrong
# problem.

_d(key="seq.forged_undecided_as_equivalent", family=SEQ, severity="soundness",
   title="An abstention relabelled as a proof of equivalence",
   why_it_looks_valid="Every obligation present carries a real, checkable proof. "
                      "The base cases genuinely hold. Only the inductive step is "
                      "missing, and the recorded verdict does not mention it.",
   caught_by="Re-deriving the argument rather than reading the verdict: with no "
             "step obligation discharged, EQUIVALENT does not follow, and the "
             "honest answer is UNDECIDED-AT-K.",
   tags=["verdict", "abstention", "the-hardest-one"])

_d(key="seq.valid_proof_of_a_different_problem", family=SEQ, severity="soundness",
   title="A real proof, of a formula this design does not encode to",
   why_it_looks_valid="The DRAT checks. The formula is UNSAT. Everything about "
                      "the obligation is internally impeccable — it is simply an "
                      "obligation for different circuits.",
   caught_by="Re-encoding the obligation from the committed design and comparing "
             "bytes. A receipt that only commits the formula cannot catch this.",
   tags=["encoder", "physics-input"])

_d(key="seq.dropped_obligation", family=SEQ, severity="soundness",
   title="An obligation claimed UNSAT but shipped without its proof",
   why_it_looks_valid="The receipt still lists the obligation and marks it "
                      "discharged; only the proof body is empty.",
   caught_by="An UNSAT claim with no proof is a claim, and claims are not "
             "accepted.",
   tags=["proof"])

_d(key="seq.edited_design", family=SEQ, severity="integrity",
   title="The design changed after the proofs were produced",
   why_it_looks_valid="Every proof still checks against the formula beside it.",
   caught_by="The design digest, and re-encoding: the formulas no longer "
             "correspond to the circuits now in the receipt.",
   tags=["commitment"])

_d(key="seq.tampered_verdict", family=SEQ, severity="soundness",
   title="A counterexample receipt relabelled EQUIVALENT",
   why_it_looks_valid="Nothing else was touched.",
   caught_by="The verdict is re-derived from the obligations, never read.",
   tags=["verdict"])

_d(key="seq.broken_chain", family=SEQ, severity="integrity",
   title="A record edited inside the hash chain",
   why_it_looks_valid="The payload is untouched and every proof still checks.",
   caught_by="Recomputing the chain digests.",
   tags=["commitment"])
