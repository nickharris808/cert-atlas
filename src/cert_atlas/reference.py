"""The reference verifier adapters — the baseline every submission is measured against."""
from __future__ import annotations

import json
from pathlib import Path

import equiv_receipt as E
import lcert_verify as L
import prereg_seal as P


def reference_verifier(path: str, case: dict) -> bool:
    """Accept iff the appropriate reference checker accepts."""
    fam = case["family"]
    if fam == "certificate":
        return bool(L.verify_bundle(path)["ok"])
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
    raise ValueError(f"unknown family {fam!r}")


def accept_everything(path: str, case: dict) -> bool:
    """Negative control: the degenerate verifier that trusts everything."""
    return True


def reject_everything(path: str, case: dict) -> bool:
    """Negative control: the degenerate verifier that trusts nothing."""
    return False
