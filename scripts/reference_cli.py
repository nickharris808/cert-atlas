#!/usr/bin/env python3
"""The bundled reference verifier as a command, for exercising the scoring path.

`cert-atlas baseline` runs the reference in-process. This exposes the same logic
over argv so the subprocess scoring path — the one every external submission uses
— is itself tested rather than assumed to work.

Exit 0 = ACCEPT, 1 = REJECT.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cert_atlas.reference import reference_verifier   # noqa: E402
from cert_atlas.score import load_index               # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: reference_cli.py <artifact-path>", file=sys.stderr)
        return 2
    path = Path(argv[0]).resolve()
    # The scorer passes only a path, so the case metadata (which family it is) has
    # to be recovered from the atlas index beside it rather than guessed.
    atlas = path if path.is_dir() else path.parent
    for _ in range(4):
        if (atlas / "index.json").exists():
            break
        atlas = atlas.parent
    index = load_index(atlas)
    rel = str(path.relative_to(atlas.resolve()))
    for case in index["cases"]:
        if case["path"] == rel:
            return 0 if reference_verifier(str(path), case) else 1
    print(f"no atlas case matches {rel}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
