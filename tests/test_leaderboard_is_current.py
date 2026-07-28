"""The committed leaderboard must be what the code produces, right now.

This is the same check CI runs. It is here too so a contributor cannot land a
stale published number without a local test going red.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committed_leaderboard_and_reference_scores_are_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "refresh_leaderboard.py"),
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 0, (
        "LEADERBOARD.md or the reference submissions are stale — "
        "run scripts/refresh_leaderboard.py\n" + r.stdout + r.stderr)
