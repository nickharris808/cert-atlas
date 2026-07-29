"""Submission records: a portable, checkable claim about a verifier's score.

A leaderboard is only meaningful if entries can be re-derived. A submission
therefore carries everything needed to reproduce it — the atlas digest, the exact
track, the per-defect outcome — not just a headline number.

Nothing here is signed or authenticated: a submission is a *claim*, and the
leaderboard says so. The atlas digest is what makes it checkable, because anyone
can rebuild the corpus and re-score.
"""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Optional

SUBMISSION_FORMAT = "cert-atlas-submission/1"


def track_ceiling(index: dict, track: str) -> float:
    """The best score attainable in ``track``, computed from the corpus.

    In the artifact-only track a defect tagged ``requires-anchor`` cannot be caught
    by anyone: the artifact is internally flawless and the only distinguishing
    evidence lives outside it. Treating 1.000 as the bar there would fail every
    honest verifier, so the ceiling is derived from the atlas rather than assumed.
    """
    from .defects import DEFECTS

    if track == "anchored":
        return 1.0
    invalid = [c for c in index["cases"] if not c["valid"]]
    if not invalid:
        return 0.0
    blind = sum(1 for c in invalid
                if "requires-anchor" in getattr(DEFECTS.get(c.get("defect")), "tags", []))
    return round((len(invalid) - blind) / len(invalid), 4)


def build_submission(result: dict, *, verifier: str, track: str,
                     url: str = "", notes: str = "",
                     command: Optional[list] = None) -> dict:
    """Assemble a submission record from a scoring result.

    ``track`` is ``artifact-only`` or ``anchored``; the two are not comparable and
    the leaderboard keeps them in separate tables.
    """
    if track not in ("artifact-only", "anchored"):
        raise ValueError("track must be 'artifact-only' or 'anchored'")
    if not verifier.strip():
        raise ValueError("verifier name is required — an anonymous entry cannot be re-run")

    per_defect = {r["id"]: ("caught" if r["correct"] else "MISSED")
                  for r in result.get("rows", []) if not r["should_accept"]}
    return {
        "format": SUBMISSION_FORMAT,
        "verifier": verifier.strip(),
        "url": url.strip(),
        "notes": notes.strip(),
        "track": track,
        "command": list(command or []),
        "atlas_version": result.get("atlas_version"),
        "atlas_digest": result.get("atlas_digest"),
        "detection": result["detection"],
        "precision": result["precision"],
        "atlas_score": result["atlas_score"],
        "sound": result["sound"],
        "missed": list(result.get("missed", [])),
        "false_alarms": list(result.get("false_alarms", [])),
        "n_cases": result.get("n_cases"),
        "per_defect": per_defect,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "implementation": sys.implementation.name,
        },
    }


def validate_submission(sub: dict, *, expected_digest: str = "") -> list:
    """Return a list of problems; empty means the record is well formed.

    A submission at a different atlas digest is **not comparable** and is rejected
    rather than silently ranked against entries from another corpus.
    """
    errs = []
    if sub.get("format") != SUBMISSION_FORMAT:
        errs.append(f"unknown submission format {sub.get('format')!r}")
    for k in ("verifier", "track", "detection", "precision", "atlas_score", "atlas_digest"):
        if sub.get(k) in (None, ""):
            errs.append(f"missing required field {k!r}")
    if sub.get("track") not in ("artifact-only", "anchored"):
        errs.append("track must be 'artifact-only' or 'anchored'")
    for k in ("detection", "precision", "atlas_score"):
        v = sub.get(k)
        if isinstance(v, (int, float)) and not (0.0 <= v <= 1.0):
            errs.append(f"{k} must lie in [0,1], got {v}")
    d, p, s = sub.get("detection"), sub.get("precision"), sub.get("atlas_score")
    if all(isinstance(x, (int, float)) for x in (d, p, s)):
        if abs(min(d, p) - s) > 1e-9:
            errs.append(f"atlas_score {s} is not min(detection {d}, precision {p}) — "
                        f"the metric is defined as the minimum and cannot be reported otherwise")
    if expected_digest and sub.get("atlas_digest") != expected_digest:
        errs.append(f"submission was scored against atlas {sub.get('atlas_digest','?')[:12]}…, "
                    f"but this leaderboard tracks {expected_digest[:12]}… — not comparable")
    return errs


def write_submission(path, sub: dict) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def render_leaderboard(subs: list, *, atlas_digest: str = "",
                       ceilings: Optional[dict] = None) -> str:
    """Render submissions as Markdown, one table per track.

    Ranked by atlas_score, then detection. Entries that fail validation are listed
    separately as unranked rather than dropped silently.
    """
    ranked, rejected = [], []
    for s in subs:
        if not isinstance(s, dict):
            rejected.append(({"verifier": "?"}, ["submission is not an object"]))
            continue
        errs = validate_submission(s, expected_digest=atlas_digest)
        (rejected if errs else ranked).append((s, errs))

    out = ["# Leaderboard", "",
           "Scores are `min(detection, precision)`. A verifier that accepts everything and",
           "one that rejects everything both score **0.000** — the metric cannot be won",
           "from one side.",
           ""]
    ceilings = ceilings or {}
    if atlas_digest:
        out += [f"Atlas digest: `{atlas_digest}`  ",
                "Submissions scored against a different digest are listed as unranked: "
                "corpora differ, so the numbers are not comparable.", ""]

    for track, blurb in (
        ("anchored",
         "The verifier is given each case's out-of-band fingerprint. "
         "Everything is catchable here."),
        ("artifact-only",
         "No fingerprint — the verifier sees only the artifact. A self-consistent forgery "
         "is **not** catchable in this track by anyone, so 1.000 is not attainable."),
    ):
        rows = sorted((s for s, _ in ranked if s.get("track") == track),
                      key=lambda s: (-s["atlas_score"], -s["detection"], s["verifier"]))
        out += [f"## Track: {track}", "", blurb, ""]
        if track in ceilings:
            out += [f"Attainable ceiling in this track: **{ceilings[track]:.3f}** "
                    f"(computed from the corpus, not assumed).", ""]
        if not rows:
            out += ["_No submissions yet._", ""]
            continue
        out += ["| # | Verifier | Score | Detection | Precision | Missed |",
                "|---|---|---|---|---|---|"]
        for i, s in enumerate(rows, 1):
            missed = ", ".join(f"`{m}`" for m in s["missed"][:3]) or "—"
            if len(s["missed"]) > 3:
                missed += f" +{len(s['missed'])-3}"
            # A verifier name is attacker-controlled text going into a Markdown
            # table. A newline would split the row and a pipe would add a column.
            safe = str(s["verifier"]).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
            safe = safe[:120] or "(unnamed)"
            url = str(s.get("url") or "").replace(")", "%29").replace("\n", "")
            name = f"[{safe}]({url})" if url else safe
            out.append(f"| {i} | {name} | **{s['atlas_score']:.3f}** | "
                       f"{s['detection']:.3f} | {s['precision']:.3f} | {missed} |")
        out.append("")

    if rejected:
        out += ["## Unranked", "",
                "These could not be ranked. The reason is stated rather than the "
                "entry dropped.", "",
                "| Verifier | Reason |", "|---|---|"]
        for s, errs in rejected:
            who = str(s.get("verifier", "?")).replace("|", "\\|")
            who = who.replace("\n", " ").replace("\r", " ")[:120] or "(unnamed)"
            why = str(errs[0]).replace("|", "\\|").replace("\n", " ")
            out.append(f"| {who} | {why} |")
        out.append("")

    out += ["---", "",
            "Submit with `cert-atlas submit`. A forgery the reference verifier **accepts**",
            "is worth more than a passing score — see CONTRIBUTING."]
    return "\n".join(out)


def load_submissions(directory) -> list:
    d = Path(directory)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            out.append({"verifier": f.name, "format": "unparseable"})
            continue
        # Valid JSON that is not an object is not a submission. It is listed as
        # unranked with the file name, rather than crashing the render.
        out.append(obj if isinstance(obj, dict)
                   else {"verifier": f.name, "format": "unparseable"})
    return out
