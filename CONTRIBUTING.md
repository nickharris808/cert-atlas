# Contributing

The most valuable contribution is a forgery we do not catch.

## Adding a defect

1. Add a `Defect` entry in `defects.py` — including `why_it_looks_valid` and `caught_by`. An entry
   without those two fields is not accepted; they are what makes the atlas readable as a document
   rather than a pile of files.
2. Add the mutation that produces it in `generate.py`.
3. Run `pytest`. `test_each_defect_is_individually_caught` will **fail** if the reference verifier
   accepts your forgery — that is the interesting outcome, and it means the reference has a real
   bug to fix. Report it; do not weaken the test.

## Rules

- **Determinism is non-negotiable.** No randomness, no timestamps, no environment dependence. The
  digest must be stable, or cross-run comparison is meaningless.
- **Every forgery must be a single named mutation** of a genuinely valid artifact. Compound
  mutations hide which check did the work.
- **A valid case must be genuinely valid.** `test_valid_cases_really_are_valid` enforces it; a bad
  "valid" case silently poisons the precision half of the metric.
- **Do not tune the metric.** If a verifier scores badly, that is the result.

## Submitting a verifier result

Use `cert-atlas submit`, which records the digest for you:

```bash
cert-atlas build atlas
cert-atlas submit atlas --verifier "my-checker" --url https://github.com/me/my-checker \
    -- mycheck --strict '{path}'
```

Open a PR adding the generated `submissions/*.json`. Results at different digests are not
comparable — such an entry is listed as **unranked with the reason stated**, rather than dropped
or silently ranked against a different corpus.

Two things the leaderboard will not do:

- **It will not run your verifier.** A PR that executes submitted code is a supply-chain hole. The
  numbers you submit are your claim; the recorded `command` and `atlas_digest` are what make the
  claim checkable by anyone.
- **It will not accept a score that its own numbers do not support.** `atlas_score` must equal
  `min(detection, precision)`; reporting the flattering half is rejected by validation.

Only the bundled reference entries are recomputed in CI, because they are our code, not yours.

### If your verifier does not reach 1.000

In the `artifact-only` track it cannot: `cert.self_consistent_forgery` is not catchable from the
artifact by any verifier, so the ceiling is 0.955. Submit anyway — attaining the ceiling is the
strongest honest claim available, and the leaderboard states the ceiling next to the scores.

## Installing for development

Dependencies use PEP 508 **direct references** to the public GitHub repositories, so
`pip install ./<pkg>` works for anyone today without anything being on PyPI.

That has one consequence worth knowing: you cannot install every package from local
paths in a single command, because pip sees the direct reference and the local path as
two different sources for the same name. Install the leaf packages first, then the
dependents with `--no-deps`:

```
pip install -e ./lcert-verify -e ./equiv-receipt -e ./prereg-seal
pip install --no-deps -e ./cert-atlas -e ./certified-mcp
```

For a future PyPI release the direct references become plain version specifiers and this
step disappears. That swap is deliberately not on the critical path.
