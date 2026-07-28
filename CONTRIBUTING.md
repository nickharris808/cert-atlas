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

Include the atlas digest. Results at different digests are not comparable and will be asked for a
re-run.
