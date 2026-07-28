"""Export the atlas as flat JSON splits for dataset hubs.

The atlas is natively a set of directories and file groups, which a flat table
cannot fully represent. This exporter produces a faithful *view*: each row carries
the artifact inline (as text where it is a single file, or as a mapping of
relative path to text where it is a directory) plus every label.

Scoring should still be done with `cert-atlas score` against the real atlas — the
flat view is for browsing, filtering and analysis.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .defects import DEFECTS
from .score import load_index


def _artifact(atlas: Path, rel: str) -> Dict[str, str]:
    p = atlas / rel
    if p.is_file():
        return {p.name: p.read_text()}
    return {str(f.relative_to(p)): f.read_text()
            for f in sorted(p.rglob("*")) if f.is_file()}


def to_rows(atlas_dir) -> List[dict]:
    atlas = Path(atlas_dir)
    index = load_index(atlas)
    rows = []
    for c in index["cases"]:
        d = DEFECTS.get(c.get("defect") or "")
        art = _artifact(atlas, c["path"])
        rows.append({
            "id": c["id"],
            "family": c["family"],
            "valid": c["valid"],
            "defect": c.get("defect") or "",
            "severity": c.get("severity") or "",
            "title": c.get("title") or "",
            "why_it_looks_valid": (d.why_it_looks_valid if d else "") or "",
            "caught_by": c.get("caught_by") or "",
            # Valid rows carry real tags rather than an empty list: an all-empty
            # list column infers as list<null>, which will not unify with the
            # list<string> of the other split when both are loaded together.
            "tags": list(d.tags) if d else ["valid", c["family"]],
            # Stored as a JSON string, not a mapping: artifacts have different
            # filenames per case, and a struct with a union of every filename
            # makes columnar schema inference fail. `artifact_files` gives the
            # names without needing to parse.
            "artifact_files": sorted(art),
            "artifact_json": json.dumps(art, sort_keys=True, ensure_ascii=False),
            "atlas_version": index["atlas_version"],
            "atlas_digest": index.get("digest"),
        })
    return rows


SCHEMA = {
    "id": "string — stable case identifier, e.g. 'cert.forged_verdict'",
    "family": "string — certificate | receipt | seal",
    "valid": "bool — whether a correct verifier should ACCEPT this artifact",
    "defect": "string — defect key; empty for valid cases",
    "severity": "string — soundness | integrity | vacuity; empty for valid cases",
    "title": "string — one-line description of the mutation; empty for valid cases",
    "why_it_looks_valid": "string — why a naive verifier would accept it; empty if valid",
    "caught_by": "string — the check that is supposed to reject it; empty if valid",
    "tags": "list[string] — free-form labels",
    "artifact_files": "list[string] — filenames making up the artifact",
    "artifact_json": "string — JSON object mapping each filename to its contents",
    "atlas_version": "string — the atlas release this row came from",
    "atlas_digest": "string — content digest; rows are only comparable at equal digest",
}


def export(atlas_dir, out_dir) -> dict:
    """Write JSONL shards plus a machine-readable schema.

    JSONL rather than a JSON array: it streams, it diffs line-by-line in review,
    and it is what dataset loaders expect.
    """
    rows = to_rows(atlas_dir)
    out = Path(out_dir)
    (out / "data").mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in ("valid", "invalid"):
        want = split == "valid"
        sel = [r for r in rows if r["valid"] == want]
        path = out / "data" / f"{split}-00000.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for r in sel:
                fh.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")
        counts[split] = len(sel)
        # remove any stale array-format shard from an earlier export
        legacy = out / "data" / f"{split}-00000.json"
        if legacy.exists():
            legacy.unlink()
    (out / "schema.json").write_text(
        json.dumps({"fields": SCHEMA,
                    "atlas_version": rows[0]["atlas_version"] if rows else None,
                    "atlas_digest": rows[0]["atlas_digest"] if rows else None,
                    "counts": counts}, indent=1, sort_keys=True) + "\n")
    return counts
