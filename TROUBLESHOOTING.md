# Troubleshooting — cert-atlas

## My checker scores 0.000 and I know it works

Almost always precision, not detection. Score `min(detection, precision)` is zero the moment a
checker rejects **one valid artifact** class.

Look at the per-defect rows: `false_alarms` lists the valid cases you rejected. Common causes:

- The checker rejects the `UNDECIDED-AT-K` sequential case for not being a proof. It is a valid
  artifact that asserts nothing, and rejecting it is the intended trap.
- The checker rejects a `VERIFIED-VACUOUS` bundle for having no gated loci.
- The checker requires an anchor and is being scored in the artifact-only track.

## My checker scores 0.964 and I want 1.000

You cannot get it in the artifact-only track, and neither can anyone. See
`cert.self_consistent_forgery` — the ceiling is computed from the corpus and printed beside the
score. Attaining it is the strongest honest claim available there.

Score `--anchored` if your checker consumes an out-of-band fingerprint.

## `ImportError: No module named 'equiv_receipt'`

`cert-atlas` builds receipts and seals as well as certificates, so it needs its three siblings.
Because dependencies are PEP 508 direct references you cannot install everything from local paths
in one command:

```bash
pip install -e ./lcert-verify -e ./equiv-receipt -e ./prereg-seal
pip install --no-deps -e ./cert-atlas
```

## `submission is not well formed: atlas_score is not min(detection, precision)`

Exactly what it says. Reporting the flattering half is rejected.

## `submission was scored against atlas … but this leaderboard tracks …`

The corpus changed. Rebuild and re-score; entries at different digests are not comparable and are
listed as unranked with the reason rather than silently ranked.

## `cert-atlas score` is slow

Every case is a subprocess and the cost is interpreter startup — about 92 ms per case. `--jobs 8`
is worth roughly 6×. Results are assembled in index order, so the score and the missed list are
identical at any `--jobs`; a test asserts it.

## My verifier crashed the run

It should not have. Each case is contained: a checker that raises, or calls `sys.exit`, counts as
a **rejection** for that case and the error is reported in `errors`. A crash is never an
acceptance. If a hostile checker did take down the whole run, that is a bug worth an issue.

## `LEADERBOARD.md does not match a fresh render`

The committed leaderboard is stale. `python scripts/refresh_leaderboard.py`. CI runs it in
`--check` mode so a published number cannot drift from the code.

---

*Still stuck? Open an issue with the atlas digest and the scoring command.*
