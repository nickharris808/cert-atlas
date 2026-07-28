#!/usr/bin/env python3
"""Re-derive the bundled reference submissions and regenerate LEADERBOARD.md.

Run with ``--check`` in CI. The check is meaningful because the reference entries
are *recomputed here from the atlas*, not read from the committed file: if the
published 0.955 ever stopped being what the code produces, this fails.

External submissions are validated but NOT re-executed — running a stranger's
verifier command would be arbitrary code execution from a pull request. Their
numbers are a claim; the recorded ``command`` and ``atlas_digest`` are what make
that claim checkable by anyone who chooses to run it.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cert_atlas.generate import build                                    # noqa: E402
from cert_atlas.reference import (anchored_reference_verifier,           # noqa: E402
                                  reference_verifier)
from cert_atlas.score import score                                       # noqa: E402
from cert_atlas.submit import (build_submission, load_submissions,       # noqa: E402
                               render_leaderboard, track_ceiling,
                               validate_submission, write_submission)

REFERENCES = [
    ("lcert-verify (reference)", reference_verifier, "artifact-only", "reference-artifact-only",
     "The bundled reference verifier with no out-of-band fingerprint. It misses "
     "cert.self_consistent_forgery, which is not catchable from the artifact alone."),
    ("lcert-verify (anchored)", anchored_reference_verifier, "anchored", "reference-anchored",
     "The same verifier given each case's fingerprint out of band."),
]
URL = "https://github.com/nickharris808/lcert-verify"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed leaderboard or reference scores are stale")
    a = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="atlas-"))
    try:
        index = build(tmp / "atlas")
        digest = index["digest"]
        subs_dir = ROOT / "submissions"
        stale = []

        for name, fn, track, stem, notes in REFERENCES:
            res = score(tmp / "atlas", fn)
            fresh = build_submission(res, verifier=name, track=track, url=URL, notes=notes,
                                     command=["cert-atlas", "baseline", "atlas"]
                                     + (["--anchored"] if track == "anchored" else []))
            path = subs_dir / f"{stem}.json"
            if a.check:
                if not path.exists():
                    stale.append(f"{path.name} is missing")
                    continue
                old = json.loads(path.read_text(encoding="utf-8"))
                for k in ("atlas_score", "detection", "precision", "atlas_digest", "per_defect"):
                    if old.get(k) != fresh[k]:
                        stale.append(f"{path.name}: {k} is {old.get(k)!r}, "
                                     f"recomputing gives {fresh[k]!r}")
            else:
                write_submission(path, fresh)
                print(f"  {name:26} {track:14} {fresh['atlas_score']:.3f}")

        subs = load_submissions(subs_dir)
        for s in subs:
            errs = validate_submission(s, expected_digest=digest)
            for e in errs:
                print(f"  submission {s.get('verifier','?')!r}: {e}")

        ceilings = {t: track_ceiling(index, t) for t in ("anchored", "artifact-only")}
        md = render_leaderboard(subs, atlas_digest=digest, ceilings=ceilings) + "\n"
        lb = ROOT / "LEADERBOARD.md"
        if a.check:
            if not lb.exists() or lb.read_text(encoding="utf-8") != md:
                stale.append("LEADERBOARD.md does not match a fresh render "
                             "(run scripts/refresh_leaderboard.py)")
            if stale:
                print("STALE:", file=sys.stderr)
                for s_ in stale:
                    print(f"  - {s_}", file=sys.stderr)
                return 1
            print(f"leaderboard is current  ({len(subs)} submissions, atlas {digest[:12]}…)")
            return 0

        lb.write_text(md, encoding="utf-8")
        print(f"wrote LEADERBOARD.md  ({len(subs)} submissions, atlas {digest[:12]}…)")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
