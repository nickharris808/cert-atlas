"""``cert-atlas build|score|baseline|defects|submit|leaderboard``."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .defects import DEFECTS
from .generate import build
from .score import command_verifier, format_report, score


def _slug(name: str) -> str:
    """A filename-safe stem. Submissions are files in a PR, so the name must be tame."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-.")
    return s.lower() or "submission"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="cert-atlas",
        description="A labelled corpus of valid and forged certificates, and a scorer.")
    sub = ap.add_subparsers(dest="_cmd", required=True)

    b = sub.add_parser("build", help="generate the atlas")
    b.add_argument("out", nargs="?", default="atlas")

    s = sub.add_parser("score", help="score an external verifier command")
    s.add_argument("atlas")
    s.add_argument("cmd", nargs="+",
                   help="verifier argv; use {path} as the artifact placeholder")
    s.add_argument("--accept-returncode", type=int, default=0)
    s.add_argument("--json", action="store_true")
    s.add_argument("--quiet", action="store_true", help="aggregate only")
    s.add_argument("-j", "--jobs", type=int, default=1,
                   help="score cases concurrently. Worth it for a subprocess "
                        "verifier, where the cost is interpreter startup; the "
                        "result is identical either way")

    r = sub.add_parser("baseline", help="score the bundled reference verifiers")
    r.add_argument("atlas")
    r.add_argument("--anchored", action="store_true",
                   help="supply each case's out-of-band fingerprint (catches everything); "
                        "without it, the artifact-only track is scored")
    r.add_argument("--json", action="store_true")

    d = sub.add_parser("defects", help="print the defect taxonomy")
    d.add_argument("--json", action="store_true")

    x = sub.add_parser("export", help="export flat JSON splits for a dataset hub")
    x.add_argument("atlas")
    x.add_argument("out")

    m = sub.add_parser("submit", help="score a verifier and write a submission record")
    m.add_argument("atlas")
    m.add_argument("cmd", nargs="+",
                   help="verifier argv; use {path} as the artifact placeholder")
    m.add_argument("--verifier", required=True, help="name to be listed under")
    m.add_argument("--track", choices=("artifact-only", "anchored"),
                   default="artifact-only",
                   help="artifact-only is the default; the two tracks are not comparable")
    m.add_argument("--url", default="", help="link to the verifier's source")
    m.add_argument("--notes", default="")
    m.add_argument("--accept-returncode", type=int, default=0)
    m.add_argument("-j", "--jobs", type=int, default=1)
    m.add_argument("-o", "--output", default="",
                   help="write the record here (default: submissions/<verifier>.json)")

    lb = sub.add_parser("leaderboard", help="render submissions/*.json as Markdown")
    lb.add_argument("submissions", nargs="?", default="submissions")
    lb.add_argument("--atlas", default="",
                    help="atlas directory; entries scored against another digest are unranked")
    lb.add_argument("-o", "--output", default="", help="write here instead of stdout")

    a = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if a._cmd == "build":
        ix = build(a.out)
        print(f"built atlas {ix['atlas_version']} -> {a.out}")
        print(f"  {ix['n_cases']} cases  ({ix['n_valid']} valid, {ix['n_invalid']} invalid)")
        print(f"  digest {ix['digest']}")
        return 0

    if a._cmd == "export":
        from .hf_export import export
        counts = export(a.atlas, a.out)
        print(f"exported to {a.out}: " +
              ", ".join(f"{k}={v}" for k, v in counts.items()))
        return 0

    if a._cmd == "submit":
        from .submit import build_submission, validate_submission, write_submission
        res = score(a.atlas, command_verifier(a.cmd, a.accept_returncode),
                    jobs=a.jobs)
        sub_rec = build_submission(res, verifier=a.verifier, track=a.track,
                                   url=a.url, notes=a.notes, command=a.cmd)
        errs = validate_submission(sub_rec)
        if errs:
            for e in errs:
                print(f"submission is not well formed: {e}", file=sys.stderr)
            return 2
        out = a.output or f"submissions/{_slug(a.verifier)}.json"
        path = write_submission(out, sub_rec)
        print(format_report(res, show_rows=False))
        print()
        print(f"wrote {path}")
        print("Open a pull request adding that file to the atlas repository.")
        print("CI checks that the record is well formed and was scored against the "
              "current atlas; it does not re-run your verifier, because that would be "
              "arbitrary code execution from a pull request. The recorded command and "
              "atlas digest are what let anyone re-derive the number themselves.")
        return 0

    if a._cmd == "leaderboard":
        from .submit import load_submissions, render_leaderboard
        digest = ""
        if a.atlas:
            digest = json.loads(
                (Path(a.atlas) / "index.json").read_text(encoding="utf-8")).get("digest", "")
        md = render_leaderboard(load_submissions(a.submissions), atlas_digest=digest)
        if a.output:
            Path(a.output).write_text(md + "\n", encoding="utf-8")
            print(f"wrote {a.output}")
        else:
            print(md)
        return 0

    if a._cmd == "defects":
        if a.json:
            print(json.dumps({k: vars(v) for k, v in DEFECTS.items()}, indent=2, default=list))
        else:
            for k, v in DEFECTS.items():
                print(f"{k:38} [{v.severity:10}] {v.title}")
                print(f"{'':38} caught by: {v.caught_by}")
        return 0

    if a._cmd == "baseline":
        from .reference import anchored_reference_verifier, reference_verifier
        res = score(a.atlas,
                    anchored_reference_verifier if a.anchored else reference_verifier)
    else:
        res = score(a.atlas, command_verifier(a.cmd, a.accept_returncode),
                    jobs=getattr(a, "jobs", 1))

    if getattr(a, "json", False):
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))
    else:
        print(format_report(res, show_rows=not getattr(a, "quiet", False)))
    return 0 if res["atlas_score"] == 1.0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
