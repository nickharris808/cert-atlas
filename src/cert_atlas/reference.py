"""The reference verifier adapters — the baseline every submission is measured against."""
from __future__ import annotations

import json
from pathlib import Path

import equiv_receipt as E
import lcert_verify as L
import prereg_seal as P


def reference_verifier(path: str, case: dict) -> bool:
    """Accept iff the appropriate reference checker accepts.

    **What this atlas measures.** Certificates are checked with
    ``require_anchor=False`` — that is, on the artifact *alone*, with no
    out-of-band fingerprint. That is deliberate: an anchor trivially detects any
    byte-level change, so scoring with one would measure the hash function rather
    than the checker. The interesting question is how much a verifier can catch
    from the artifact by itself.

    The consequence is stated openly: a **self-consistent forgery** — physics
    inputs and recorded verdict edited together — is *not* detectable in this
    track, by anyone, and the atlas contains such a case
    (``cert.self_consistent_forgery``) to make that limit measurable rather than
    merely asserted. Use :func:`anchored_reference_verifier` for the track where
    it is caught.
    """
    fam = case["family"]
    if fam == "certificate":
        return bool(L.verify_bundle(path, require_anchor=False)["ok"])
    if fam == "receipt":
        return bool(E.verify_receipt(json.loads(Path(path).read_text()))["ok"])
    if fam == "seal":
        payload = json.loads(Path(path).read_text())
        spec = payload["spec"]
        try:
            if payload.get("bound") is not None:
                P.verify_bound(payload["bound"], spec)
            else:
                P.verify(spec, payload["seal"])
            return True
        except P.SealMismatch:
            return False
    if fam == "sequential":
        from equiv_receipt import seq
        res = seq.verify_seq_receipt(json.loads(Path(path).read_text()))
        # An abstention is a VALID artifact — it is an honest UNDECIDED-AT-K, not
        # a defect. What must be rejected is an abstention relabelled as a proof.
        return bool(res["ok"])
    raise ValueError(f"unknown family {fam!r}")


def anchored_reference_verifier(path: str, case: dict) -> bool:
    """Reference checker with the out-of-band anchor supplied.

    The case carries ``expected_fingerprint`` — the fingerprint of the *genuine*
    artifact, recorded before mutation. That stands in for a value a real user
    obtains from a signed report or a separate channel.
    """
    fam = case["family"]
    if fam == "certificate":
        anchor = case.get("expected_fingerprint", "")
        if not anchor:
            return bool(L.verify_bundle(path, require_anchor=False)["ok"])
        return bool(L.verify_bundle(path, anchor)["ok"])
    return reference_verifier(path, case)


def accept_everything(path: str, case: dict) -> bool:
    """Negative control: the degenerate verifier that trusts everything."""
    return True


def reject_everything(path: str, case: dict) -> bool:
    """Negative control: the degenerate verifier that trusts nothing."""
    return False
