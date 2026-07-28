"""Submission and leaderboard tests.

The leaderboard is a public claim surface, so the properties that matter are:
a degenerate verifier cannot be made to look good, a submission cannot report a
score its own numbers do not support, and an entry scored against a different
corpus is never silently ranked alongside one that is comparable.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cert_atlas.generate import build
from cert_atlas.reference import anchored_reference_verifier, reference_verifier
from cert_atlas.score import score
from cert_atlas.submit import (SUBMISSION_FORMAT, build_submission, load_submissions,
                               render_leaderboard, validate_submission, write_submission)


@pytest.fixture(scope="module")
def atlas(tmp_path_factory):
    d = tmp_path_factory.mktemp("atlas")
    build(d)
    return d


@pytest.fixture(scope="module")
def ref(atlas):
    return score(atlas, reference_verifier)


def _sub(res, **kw):
    kw.setdefault("verifier", "v")
    kw.setdefault("track", "artifact-only")
    return build_submission(res, **kw)


# ------------------------------------------------------------------ record

def test_submission_carries_what_is_needed_to_re_derive_it(ref):
    s = _sub(ref, command=["mycheck", "{path}"])
    assert s["format"] == SUBMISSION_FORMAT
    assert s["atlas_digest"] and s["atlas_version"]
    assert s["command"] == ["mycheck", "{path}"]
    assert s["environment"]["python"]
    assert s["per_defect"], "a headline score without a per-defect breakdown is not checkable"


def test_per_defect_breakdown_covers_every_invalid_case(atlas, ref):
    index = json.loads((Path(atlas) / "index.json").read_text())
    n_invalid = index["n_invalid"]
    assert len(_sub(ref)["per_defect"]) == n_invalid


def test_reference_scores_are_the_published_ones(atlas, ref):
    anchored = score(atlas, anchored_reference_verifier)
    assert _sub(ref)["atlas_score"] == pytest.approx(0.9545, abs=5e-4)
    assert _sub(anchored, track="anchored")["atlas_score"] == 1.0


def test_an_anonymous_submission_is_refused(ref):
    with pytest.raises(ValueError, match="verifier name"):
        build_submission(ref, verifier="   ", track="anchored")


def test_an_unknown_track_is_refused(ref):
    with pytest.raises(ValueError, match="track"):
        build_submission(ref, verifier="v", track="easy-mode")


# ------------------------------------------------------------------ validation

def test_a_wellformed_submission_validates(ref):
    assert validate_submission(_sub(ref)) == []


def test_a_score_that_is_not_the_minimum_is_refused(ref):
    s = _sub(ref)
    s["atlas_score"] = s["precision"]        # report the flattering side only
    errs = validate_submission(s)
    assert errs and "minimum" in errs[0]


def test_out_of_range_scores_are_refused(ref):
    s = _sub(ref)
    s["detection"] = 1.7
    assert any("[0,1]" in e for e in validate_submission(s))


def test_a_submission_from_another_corpus_is_not_comparable(ref):
    errs = validate_submission(_sub(ref), expected_digest="0" * 64)
    assert errs and "not comparable" in errs[0]


def test_missing_fields_are_named(ref):
    s = _sub(ref)
    del s["atlas_digest"]
    assert any("atlas_digest" in e for e in validate_submission(s))


def test_an_unknown_format_version_is_refused(ref):
    s = _sub(ref)
    s["format"] = "cert-atlas-submission/99"
    assert any("format" in e for e in validate_submission(s))


# ------------------------------------------------------------------ leaderboard

def _degenerate(atlas, accept):
    return score(atlas, lambda path, case: accept)


def test_both_degenerate_verifiers_rank_at_zero(atlas):
    """The point of the two-sided metric, asserted on the leaderboard itself."""
    always_yes = _sub(_degenerate(atlas, True), verifier="Always Accept")
    always_no = _sub(_degenerate(atlas, False), verifier="Always Reject")
    assert always_yes["atlas_score"] == 0.0 and always_no["atlas_score"] == 0.0
    md = render_leaderboard([always_yes, always_no])
    body = md.split("## Track: artifact-only")[1]
    assert body.count("**0.000**") == 2, "both degenerate verifiers must rank at zero"
    assert "the metric cannot be won" in md and "from one side" in md


def test_ranking_is_by_score_then_detection(atlas, ref):
    rows = [_sub(ref, verifier="ref"),
            _sub(_degenerate(atlas, True), verifier="yes"),
            _sub(_degenerate(atlas, False), verifier="no")]
    body = render_leaderboard(rows).split("## Track: artifact-only")[1]
    ranked = [ln.split("|")[2].strip() for ln in body.splitlines()
              if ln.startswith("| ") and ln.split("|")[1].strip().isdigit()]
    assert ranked[0] == "ref", ranked
    assert ranked[1] == "no", "at equal score the higher detection ranks first"


def test_tracks_are_rendered_separately_and_never_merged(atlas, ref):
    anchored = _sub(score(atlas, anchored_reference_verifier),
                    verifier="anchored-ref", track="anchored")
    md = render_leaderboard([_sub(ref, verifier="artifact-ref"), anchored])
    art = md.split("## Track: artifact-only")[1]
    assert "anchored-ref" not in art
    assert "1.000 is not attainable" in art


def test_an_incomparable_entry_is_unranked_with_a_stated_reason(ref):
    md = render_leaderboard([_sub(ref, verifier="stale")], atlas_digest="f" * 64)
    assert "## Unranked" in md
    assert "not comparable" in md
    assert "| 1 | stale" not in md, "an incomparable entry must not be ranked"


def test_an_unparseable_submission_is_reported_not_dropped(tmp_path, ref):
    write_submission(tmp_path / "good.json", _sub(ref, verifier="good"))
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    subs = load_submissions(tmp_path)
    assert len(subs) == 2
    md = render_leaderboard(subs)
    assert "## Unranked" in md and "bad.json" in md


def test_empty_leaderboard_says_so_rather_than_rendering_an_empty_table():
    md = render_leaderboard([])
    assert md.count("_No submissions yet._") == 2


def test_a_url_is_optional_and_a_missing_one_is_not_a_broken_link(ref):
    md = render_leaderboard([_sub(ref, verifier="nourl")])
    assert "[nourl](" not in md and "nourl" in md


def test_missed_list_is_truncated_but_the_count_is_not_hidden(atlas):
    md = render_leaderboard([_sub(_degenerate(atlas, True), verifier="yes")])
    assert "+19" in md, "the count of further misses must survive truncation"


# ------------------------------------------------------------------ CLI

def _child_env():
    import os

    import cert_atlas
    roots = [str(Path(cert_atlas.__file__).resolve().parents[1])]
    for name in ("lcert_verify", "equiv_receipt", "prereg_seal"):
        try:
            mod = __import__(name)
        except ImportError:      # pragma: no cover - only if a sibling is absent
            continue
        roots.append(str(Path(mod.__file__).resolve().parents[1]))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(roots + [env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    return env


def _cli(args, cwd):
    return subprocess.run([sys.executable, "-m", "cert_atlas.cli", *args],
                          capture_output=True, text=True, cwd=cwd, env=_child_env())


def test_cli_submit_writes_a_valid_record(atlas, tmp_path):
    script = tmp_path / "accept.py"
    script.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    r = _cli(["submit", str(atlas), "--verifier", "CLI Test", "--track", "artifact-only",
              "--", sys.executable, str(script), "{path}"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    out = tmp_path / "submissions" / "cli-test.json"
    assert out.exists()
    assert validate_submission(json.loads(out.read_text())) == []


def test_cli_submit_is_reached_and_not_shadowed_by_its_own_positional(atlas, tmp_path):
    """`score` and `submit` both take a positional argv; dispatch must survive it."""
    script = tmp_path / "a.py"
    script.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    r = _cli(["submit", str(atlas), "--verifier", "Shadow", "--",
              sys.executable, str(script), "{path}"], cwd=tmp_path)
    assert "wrote" in r.stdout, "submit fell through to another subcommand"


def test_cli_leaderboard_renders_from_a_directory(atlas, tmp_path, ref):
    d = tmp_path / "subs"
    write_submission(d / "a.json", _sub(ref, verifier="A"))
    r = _cli(["leaderboard", str(d), "--atlas", str(atlas)], cwd=tmp_path)
    assert r.returncode == 0 and "| 1 | A |" in r.stdout


def test_cli_leaderboard_on_an_absent_directory_is_empty_not_an_error(tmp_path):
    r = _cli(["leaderboard", str(tmp_path / "nope")], cwd=tmp_path)
    assert r.returncode == 0 and "_No submissions yet._" in r.stdout


# ------------------------------------------------------------------ ceiling

def test_artifact_only_ceiling_is_below_one_and_derived_from_the_corpus(atlas):
    from cert_atlas.score import load_index
    from cert_atlas.submit import track_ceiling
    index = load_index(atlas)
    assert track_ceiling(index, "anchored") == 1.0
    c = track_ceiling(index, "artifact-only")
    assert 0.0 < c < 1.0, "an unreachable ceiling would fail every honest verifier"


def test_the_reference_verifier_attains_the_artifact_only_ceiling(atlas, ref):
    """Sound up to the theoretical limit — the strongest honest claim available."""
    from cert_atlas.score import load_index
    from cert_atlas.submit import track_ceiling
    assert ref["atlas_score"] == pytest.approx(
        track_ceiling(load_index(atlas), "artifact-only"))


def test_the_ceiling_gap_is_exactly_the_unanchorable_defects(atlas):
    from cert_atlas.defects import DEFECTS
    from cert_atlas.score import load_index
    from cert_atlas.submit import track_ceiling
    index = load_index(atlas)
    invalid = [c for c in index["cases"] if not c["valid"]]
    blind = [c for c in invalid
             if "requires-anchor" in DEFECTS[c["defect"]].tags]
    assert blind, "the corpus must contain the honest-limit case"
    assert track_ceiling(index, "artifact-only") == pytest.approx(
        (len(invalid) - len(blind)) / len(invalid), abs=1e-4)


def test_the_leaderboard_states_the_ceiling_rather_than_implying_one(ref):
    from cert_atlas.submit import render_leaderboard
    md = render_leaderboard([_sub(ref)],
                            ceilings={"artifact-only": 0.9545, "anchored": 1.0})
    assert "Attainable ceiling in this track: **0.955**" in md
    assert "computed from the corpus, not assumed" in md


# ------------------------------------------------------------------ subprocess path

def test_the_subprocess_scoring_path_matches_the_in_process_reference(atlas, ref):
    """Every external submission goes through argv; that path must not differ."""
    from cert_atlas.score import command_verifier
    shim = str(Path(__file__).resolve().parents[1] / "scripts" / "reference_cli.py")
    got = score(atlas, command_verifier([sys.executable, shim, "{path}"], 0))
    assert got["atlas_score"] == ref["atlas_score"]
    assert got["missed"] == ref["missed"]
    assert got["false_alarms"] == ref["false_alarms"]
