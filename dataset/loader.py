"""Standalone loader for the certificate failure atlas.

Works with `datasets` if you have it, and without it if you don't — the corpus is
small and dependency-free access matters more here than streaming.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional

HERE = Path(__file__).parent
SPLITS = ("valid", "invalid")


def load_split(split: str, root: Optional[Path] = None) -> List[dict]:
    """Load one split as a list of dicts. No third-party dependency required."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    path = (root or HERE) / "data" / f"{split}-00000.jsonl"
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load(root: Optional[Path] = None) -> Dict[str, List[dict]]:
    """Load every split."""
    return {s: load_split(s, root) for s in SPLITS}


def iter_forgeries(root: Optional[Path] = None) -> Iterator[dict]:
    """Every invalid case, which is what the corpus is for."""
    yield from load_split("invalid", root)


def artifact(row: dict) -> Dict[str, str]:
    """Decode a row's artifact into {filename: contents}."""
    return json.loads(row["artifact_json"])


def schema(root: Optional[Path] = None) -> dict:
    return json.loads(((root or HERE) / "schema.json").read_text(encoding="utf-8"))


def as_hf_dataset(root: Optional[Path] = None):
    """Return a `datasets.DatasetDict` if the `datasets` package is installed."""
    try:
        from datasets import Dataset, DatasetDict
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "the `datasets` package is not installed; use load() for plain dicts") from exc
    return DatasetDict({s: Dataset.from_list(load_split(s, root)) for s in SPLITS})


if __name__ == "__main__":
    d = load()
    print(f"valid: {len(d['valid'])}  invalid: {len(d['invalid'])}")
    print(f"atlas digest: {schema()['atlas_digest']}")
    for r in d["invalid"][:3]:
        print(f"  {r['id']:34} [{r['severity']}] {r['title']}")
        print(f"      files: {', '.join(artifact(r))}")
