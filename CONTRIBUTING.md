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
