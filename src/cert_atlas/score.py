"""Score a verifier against the atlas.

THE METRIC, and why it has two halves.

A verifier that rejects everything catches every forgery. A verifier that accepts
everything never raises a false alarm. Either is useless, and either can top a
one-sided leaderboard. So a submission is scored on both and **ranked on the
minimum**:

    detection   = invalid cases correctly REJECTED / all invalid cases
    precision   = valid   cases correctly ACCEPTED / all valid cases
    atlas_score = min(detection, precision)

A verifier claiming soundness must score detection = 1.000. Anything less means a
forgery in this atlas gets through it. Precision below 1.000 means it rejects
artifacts that are genuinely fine — which in practice gets the verifier switched
off, so it is a soundness problem one step removed.

Per-defect results are always reported alongside the aggregate, because *which*
case you miss matters more than how many.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

VerifierFn = Callable[[str, dict], bool]   # (abs_path, case) -> accepted?


def load_index(atlas_dir) -> dict:
    return json.loads((Path(atlas_dir) / "index.json").read_text())


def score(atlas_dir, verifier: VerifierFn, *, families: Optional[List[str]] = None) -> dict:
    """Run ``verifier`` over every case and compute the metric.

    ``verifier`` returns True if it ACCEPTS the artifact. Exceptions count as a
    rejection, since a verifier that crashes has not accepted anything.
    """
    atlas = Path(atlas_dir)
    index = load_index(atlas)
    rows, errors = [], []

    for case in index["cases"]:
        if families and case["family"] not in families:
            continue
        path = str(atlas / case["path"])
        try:
            accepted = bool(verifier(path, case))
        except Exception as exc:                      # a crash is not an acceptance
            accepted = False
            errors.append({"id": case["id"], "error": f"{type(exc).__name__}: {exc}"})
        correct = accepted == case["valid"]
        rows.append({"id": case["id"], "family": case["family"],
                     "should_accept": case["valid"], "accepted": accepted,
                     "correct": correct, "defect": case.get("defect"),
                     "severity": case.get("severity")})

    inv = [r for r in rows if not r["should_accept"]]
    val = [r for r in rows if r["should_accept"]]
    detection = sum(r["correct"] for r in inv) / len(inv) if inv else 0.0
    precision = sum(r["correct"] for r in val) / len(val) if val else 0.0

    missed = [r["id"] for r in inv if not r["correct"]]
    false_alarms = [r["id"] for r in val if not r["correct"]]

    return {
        "atlas_version": index["atlas_version"],
        "atlas_digest": index.get("digest"),
        "n_cases": len(rows),
        "detection": round(detection, 4),
        "precision": round(precision, 4),
        "atlas_score": round(min(detection, precision), 4),
        "sound": detection == 1.0,
        "missed": missed,
        "false_alarms": false_alarms,
        "errors": errors,
        "rows": rows,
    }


def command_verifier(argv_template: List[str], accept_returncode: int = 0) -> VerifierFn:
    """Adapt an external CLI to the scorer.

    ``argv_template`` uses ``{path}`` as the placeholder, e.g.
    ``["my-verifier", "--check", "{path}"]``. Acceptance is signalled by exit code.
    """
    def _v(path: str, case: dict) -> bool:
        argv = [a.replace("{path}", path) for a in argv_template]
        r = subprocess.run(argv, capture_output=True, text=True)
        return r.returncode == accept_returncode
    return _v


def format_report(res: dict, *, show_rows: bool = True) -> str:
    lines = [
        f"atlas {res['atlas_version']}  ({res['n_cases']} cases)",
        f"  detection  {res['detection']:.3f}   (invalid artifacts correctly rejected)",
        f"  precision  {res['precision']:.3f}   (valid artifacts correctly accepted)",
        f"  ATLAS SCORE {res['atlas_score']:.3f}  = min(detection, precision)",
        f"  sound: {'YES' if res['sound'] else 'NO'}",
    ]
    if res["missed"]:
        lines.append("  MISSED (forgeries that got through):")
        lines += [f"    - {m}" for m in res["missed"]]
    if res["false_alarms"]:
        lines.append("  FALSE ALARMS (valid artifacts rejected):")
        lines += [f"    - {m}" for m in res["false_alarms"]]
    if res["errors"]:
        lines.append(f"  errors: {len(res['errors'])}")
    if show_rows:
        lines.append("")
        for r in res["rows"]:
            mark = "ok " if r["correct"] else "MISS"
            lines.append(f"    {mark} {r['id']:<38} "
                         f"{'accept' if r['accepted'] else 'reject':<7}"
                         f"{'(should accept)' if r['should_accept'] else '(should reject)'}")
    return "\n".join(lines)
