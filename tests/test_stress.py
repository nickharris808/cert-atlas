"""The adversarial suite for cert-atlas.

Oracle: no input may produce a confident-looking answer that is wrong. Here that
means a hostile *verifier* cannot take down the harness or inflate its own score,
and a hostile *submission* cannot be ranked on numbers it does not support.
"""
from __future__ import annotations

import sys

import pytest

from cert_atlas.generate import build
from cert_atlas.reference import anchored_reference_verifier, reference_verifier
from cert_atlas.score import command_verifier, load_index, score
from cert_atlas.submit import (build_submission, load_submissions, render_leaderboard,
                               track_ceiling, validate_submission)


@pytest.fixture(scope="module")
def atlas(tmp_path_factory):
    d = tmp_path_factory.mktemp("atlas")
    build(d)
    return d


# ============================================================ 1. HOSTILE VERIFIERS

HOSTILE = [
    ("raises", lambda p, c: (_ for _ in ()).throw(RuntimeError("boom"))),
    ("exits", lambda p, c: sys.exit(9)),
    ("keyboard interrupt", lambda p, c: (_ for _ in ()).throw(KeyboardInterrupt())),
    ("memory error", lambda p, c: (_ for _ in ()).throw(MemoryError())),
    ("returns a string", lambda p, c: "yes"),
    ("returns None", lambda p, c: None),
    ("returns a list", lambda p, c: [1]),
    ("mutates the case", lambda p, c: c.clear() or True),
]


@pytest.mark.parametrize("label,fn", HOSTILE, ids=[h[0] for h in HOSTILE])
def test_a_hostile_verifier_is_contained_and_never_takes_down_the_run(atlas, label, fn):
    res = score(atlas, fn)                                 # must not raise
    assert res["n_cases"] > 0, label
    assert 0.0 <= res["atlas_score"] <= 1.0


@pytest.mark.parametrize("label,fn", HOSTILE, ids=[h[0] for h in HOSTILE])
def test_a_hostile_verifier_is_contained_under_concurrency(atlas, label, fn):
    res = score(atlas, fn, jobs=8)
    assert res["n_cases"] > 0, label


def test_a_crash_is_never_counted_as_an_acceptance(atlas):
    def crasher(path, case):
        raise RuntimeError("boom")

    res = score(atlas, crasher)
    assert all(r["accepted"] is False for r in res["rows"])
    assert res["errors"], "the failures must be reported, not swallowed"
    # rejecting everything catches every forgery but fails every valid case
    assert res["detection"] == 1.0 and res["precision"] == 0.0
    assert res["atlas_score"] == 0.0


def test_neither_degenerate_verifier_can_score_above_zero(atlas):
    for constant in (True, False):
        res = score(atlas, lambda p, c, v=constant: v)
        assert res["atlas_score"] == 0.0, constant


def test_a_verifier_that_reads_the_label_is_not_special_cased(atlas):
    """A cheating verifier scores 1.000 — the corpus does not hide the labels.

    That is deliberate and worth pinning: the atlas is a *measurement*, not an
    access-control mechanism. Nothing here pretends a local score is trustworthy;
    only a re-derived one is.
    """
    res = score(atlas, lambda p, c: c["valid"])
    assert res["atlas_score"] == 1.0


def test_a_subprocess_verifier_that_hangs_is_bounded(atlas, tmp_path):
    """A verifier that never returns must not hang the harness forever."""
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(30)\n")
    v = command_verifier([sys.executable, str(script), "{path}"], 0, timeout=1)
    res = score(atlas, v)
    assert res["n_cases"] > 0
    assert res["errors"] or res["detection"] == 1.0


# ============================================================ 2. CONCURRENCY

@pytest.mark.parametrize("jobs", [1, 2, 4, 8, 16])
def test_the_score_does_not_depend_on_scheduling(atlas, jobs):
    a = score(atlas, reference_verifier, jobs=1)
    b = score(atlas, reference_verifier, jobs=jobs)
    for k in ("atlas_score", "detection", "precision", "missed", "false_alarms",
              "n_cases", "sound"):
        assert a[k] == b[k], k
    assert [r["id"] for r in a["rows"]] == [r["id"] for r in b["rows"]]


def test_scoring_twice_gives_the_same_answer(atlas):
    a = score(atlas, reference_verifier)
    b = score(atlas, reference_verifier)
    assert a == b


# ============================================================ 3. SUBMISSIONS

@pytest.fixture(scope="module")
def ref(atlas):
    return score(atlas, reference_verifier)


MALFORMED_SUBMISSIONS = [
    ("empty", {}),
    ("unknown format", {"format": "x/9"}),
    ("no verifier", {"format": "cert-atlas-submission/1", "track": "anchored"}),
    ("score above one", {"detection": 2.0}),
    ("score below zero", {"detection": -1.0}),
    ("score is not the minimum", {"atlas_score": 1.0, "detection": 0.5,
                                  "precision": 1.0}),
    ("track invented", {"track": "easy-mode"}),
]


@pytest.mark.parametrize("label,overrides", MALFORMED_SUBMISSIONS,
                         ids=[m[0] for m in MALFORMED_SUBMISSIONS])
def test_a_malformed_submission_is_never_valid(ref, label, overrides):
    if label in ("empty", "unknown format", "no verifier"):
        sub = dict(overrides)              # these cannot be built at all
    else:
        sub = build_submission(ref, verifier="v", track="artifact-only")
        sub.update(overrides)
    assert validate_submission(sub), f"{label} validated"


def test_a_submission_cannot_report_the_flattering_half(ref):
    sub = build_submission(ref, verifier="v", track="artifact-only")
    sub["atlas_score"] = sub["precision"]
    errs = validate_submission(sub)
    assert errs and "minimum" in errs[0]


def test_a_submission_from_another_corpus_is_never_ranked(ref):
    sub = build_submission(ref, verifier="stale", track="artifact-only")
    md = render_leaderboard([sub], atlas_digest="f" * 64)
    assert "## Unranked" in md and "not comparable" in md
    assert "| 1 | stale" not in md


@pytest.mark.parametrize("bad", [
    b"", b"not json", b"[1,2,3]", b'{"unclosed": ', b"null", b"\x00\x01",
])
def test_an_unparseable_submission_file_is_reported_not_dropped(tmp_path, bad):
    (tmp_path / "bad.json").write_bytes(bad)
    subs = load_submissions(tmp_path)
    assert len(subs) == 1
    md = render_leaderboard(subs)
    assert "## Unranked" in md


def test_an_anonymous_submission_cannot_even_be_built(ref):
    """A name is required at construction — an unnamed entry cannot be re-run."""
    for blank in ("", "  ", "\n", "\t"):
        with pytest.raises(ValueError, match="verifier name"):
            build_submission(ref, verifier=blank, track="artifact-only")


HOSTILE_NAMES = ["| pipe |", "<script>alert(1)</script>", "a\nb", "a\r\nb",
                 "x" * 500, "[link](http://evil)", "`code`", "\\", "|---|"]


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_a_hostile_verifier_name_cannot_break_the_leaderboard_table(ref, name):
    """The name is attacker-controlled text going into a Markdown table."""
    sub = build_submission(ref, verifier="placeholder", track="artifact-only")
    sub["verifier"] = name
    md = render_leaderboard([sub])
    body = md.split("## Track: artifact-only")[1]
    rows = [ln for ln in body.splitlines()
            if ln.startswith("| ") and ln.split("|")[1].strip().isdigit()]
    assert len(rows) == 1, f"{name!r} produced {len(rows)} rows"
    # exactly the six pipes of a six-column row: any unescaped pipe adds a column
    assert rows[0].count("|") - rows[0].count("\\|") == 7, rows[0]


def test_a_hostile_url_cannot_escape_the_markdown_link(ref):
    sub = build_submission(ref, verifier="v", track="artifact-only")
    sub["url"] = "http://x)](javascript:alert(1)"
    md = render_leaderboard([sub])
    assert "javascript:alert(1)" not in md or "%29" in md


# ============================================================ 4. THE CEILING

def test_the_ceiling_is_between_zero_and_one_and_derived(atlas):
    index = load_index(atlas)
    assert track_ceiling(index, "anchored") == 1.0
    c = track_ceiling(index, "artifact-only")
    assert 0.0 < c < 1.0


def test_the_reference_attains_the_ceiling_and_nothing_exceeds_it(atlas, ref):
    index = load_index(atlas)
    ceiling = track_ceiling(index, "artifact-only")
    assert ref["atlas_score"] == pytest.approx(ceiling)
    anchored = score(atlas, anchored_reference_verifier)
    assert anchored["atlas_score"] <= 1.0


def test_an_empty_corpus_has_a_ceiling_of_zero_not_one():
    assert track_ceiling({"cases": []}, "artifact-only") == 0.0


# ============================================================ 5. THE CORPUS ITSELF

def test_every_valid_case_is_accepted_by_the_reference(atlas):
    """A bad 'valid' case would silently poison the precision half of the metric."""
    index = load_index(atlas)
    for case in index["cases"]:
        if case["valid"]:
            path = str(atlas / case["path"])
            assert reference_verifier(path, case) is True, case["id"]


def test_every_invalid_case_has_a_defect_entry(atlas):
    from cert_atlas.defects import DEFECTS
    for case in load_index(atlas)["cases"]:
        if not case["valid"]:
            assert case["defect"] in DEFECTS, case["id"]
            d = DEFECTS[case["defect"]]
            assert d.why_it_looks_valid and d.caught_by


def test_the_corpus_is_byte_reproducible(tmp_path):
    a = build(tmp_path / "a")
    b = build(tmp_path / "b")
    assert a["digest"] == b["digest"]
    assert a["n_cases"] == b["n_cases"]


def test_the_corpus_contains_a_case_nobody_can_catch(atlas):
    """The ceiling is only honest if the uncatchable case is actually there."""
    from cert_atlas.defects import DEFECTS
    blind = [k for k, d in DEFECTS.items() if "requires-anchor" in d.tags]
    assert blind, "the honest-limit case is missing"
    ids = {c["id"] for c in load_index(atlas)["cases"]}
    assert any(b in ids for b in blind)
