# Contributing to cert-atlas

This package is part of [certified-oss][p]. **The portfolio-wide guide is
[CONTRIBUTING.md][c] and it is the one to read** — it covers the rules that are not negotiable,
how to install packages that depend on each other, and what kind of contribution is most wanted
(a forgery this project fails to catch).

What is specific to this package:

- **A new defect must be minimal and must state why it looks valid.** Compound mutations hide which
  check did the work. `cert-atlas defects` is the taxonomy and every entry carries `why_it_looks_valid`
  and `caught_by`.
- **A "valid" case must be genuinely valid.** `test_valid_cases_really_are_valid` enforces it; a bad
  one silently poisons the precision half of the metric.
- **Do not tune the metric.** If a verifier scores badly, that is the result.
- **`LEADERBOARD.md` and the reference scores are generated.** `python scripts/refresh_leaderboard.py`;
  CI runs it in `--check` mode.

## Working on it

```bash
pip install -e ".[test]"
pytest -q
ruff check .
```

## Licence

Apache-2.0. By contributing you agree your contribution is licensed the same way.

[p]: https://github.com/nickharris808/certified-oss
[c]: https://github.com/nickharris808/certified-oss/blob/main/CONTRIBUTING.md
