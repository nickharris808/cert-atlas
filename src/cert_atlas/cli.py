"""``cert-atlas build|score|baseline|defects``."""
from __future__ import annotations

import argparse
import json
import sys

from .defects import DEFECTS
from .generate import build
from .score import command_verifier, format_report, score


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="cert-atlas",
        description="A labelled corpus of valid and forged certificates, and a scorer.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="generate the atlas")
    b.add_argument("out", nargs="?", default="atlas")

    s = sub.add_parser("score", help="score an external verifier command")
    s.add_argument("atlas")
    s.add_argument("cmd", nargs="+",
                   help="verifier argv; use {path} as the artifact placeholder")
    s.add_argument("--accept-returncode", type=int, default=0)
    s.add_argument("--json", action="store_true")
    s.add_argument("--quiet", action="store_true", help="aggregate only")

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

    a = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if a.cmd == "build":
        ix = build(a.out)
        print(f"built atlas {ix['atlas_version']} -> {a.out}")
        print(f"  {ix['n_cases']} cases  ({ix['n_valid']} valid, {ix['n_invalid']} invalid)")
        print(f"  digest {ix['digest']}")
        return 0

    if a.cmd == "export":
        from .hf_export import export
        counts = export(a.atlas, a.out)
        print(f"exported to {a.out}: " +
              ", ".join(f"{k}={v}" for k, v in counts.items()))
        return 0

    if a.cmd == "defects":
        if a.json:
            print(json.dumps({k: vars(v) for k, v in DEFECTS.items()}, indent=2, default=list))
        else:
            for k, v in DEFECTS.items():
                print(f"{k:38} [{v.severity:10}] {v.title}")
                print(f"{'':38} caught by: {v.caught_by}")
        return 0

    if a.cmd == "baseline":
        from .reference import anchored_reference_verifier, reference_verifier
        res = score(a.atlas,
                    anchored_reference_verifier if a.anchored else reference_verifier)
    else:
        res = score(a.atlas, command_verifier(a.cmd, a.accept_returncode))

    if getattr(a, "json", False):
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))
    else:
        print(format_report(res, show_rows=not getattr(a, "quiet", False)))
    return 0 if res["atlas_score"] == 1.0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
