# Tutorial — cert-atlas

Score your verifier against artifacts designed to fool it, and find out what it misses.

## Install and score the reference

```bash
pip install "lcert-verify @ git+https://github.com/nickharris808/lcert-verify.git@main" \
            "equiv-receipt @ git+https://github.com/nickharris808/equiv-receipt.git@main" \
            "prereg-seal @ git+https://github.com/nickharris808/prereg-seal.git@main"
pip install --no-deps "cert-atlas @ git+https://github.com/nickharris808/cert-atlas.git@main"

cert-atlas build atlas
cert-atlas baseline atlas
```

## 1. Score your own checker

Your checker needs one interface: take a path, exit `0` to **accept** and anything else to
**reject**.

```bash
cert-atlas score atlas -- mycheck --strict '{path}'
```

`{path}` is replaced per case. Add `--jobs 8` — the cost is interpreter startup, so it is worth
about 6× and the result is identical either way.

## 2. Read the metric properly

```
  detection  0.964   (invalid artifacts correctly rejected)
  precision  1.000   (valid artifacts correctly accepted)
  ATLAS SCORE 0.964  = min(detection, precision)
```

**`min`, deliberately.** A checker that rejects everything catches every forgery; one that accepts
everything never raises a false alarm. Both score **0.000**. The metric cannot be won from one
side, and both degenerate checkers are in the leaderboard to prove it.

Which case you miss matters more than how many, so per-defect results are always reported.

## 3. Understand the two tracks

| Track | Ceiling | |
|---|---|---|
| `anchored` | 1.000 | the checker is given each case's out-of-band fingerprint |
| `artifact-only` | **0.964** | the artifact and nothing else |

The artifact-only ceiling is **computed from the corpus, not assumed**. One case,
`cert.self_consistent_forgery`, has its inputs and its recorded verdict edited together — no
checker can catch it from the artifact alone. Attaining 0.964 is therefore the strongest honest
claim available in that track, and the reference does exactly that.

Scores from different tracks are not comparable and the leaderboard keeps them apart.

## 4. Submit

```bash
cert-atlas submit atlas --verifier "my-checker" \
    --url https://github.com/me/my-checker -- mycheck '{path}'
```

That writes `submissions/my-checker.json` with the score, the per-defect breakdown, the atlas
digest and the exact command. Open a PR adding it.

CI checks the record is well formed and was scored against the current corpus. It does **not**
re-run your verifier — executing a stranger's command from a pull request is a supply-chain hole.
Your numbers are a claim; the recorded command and digest are what make the claim checkable.

It also will not accept a score its own numbers do not support: `atlas_score` must equal
`min(detection, precision)`.

## 5. Score in CI

```yaml
- uses: nickharris808/cert-atlas@main
  with:
    command: "mycheck --strict {path}"
```

`min-score: auto` uses the ceiling for the track, so the build fails on any forgery you *could*
have caught and never on one nobody can.

## 6. Contribute a forgery — the valuable one

If you can construct an artifact that is invalid and that the reference **accepts**, that is worth
more than any passing score. It becomes a case and the reference gets fixed.

See [CONTRIBUTING.md](CONTRIBUTING.md). The four families are `certificate`, `receipt`, `seal` and
`sequential`; `cert-atlas defects` prints the whole taxonomy with, for each entry, why the forgery
looks valid and which check is supposed to catch it.

---

*See [LEADERBOARD.md](LEADERBOARD.md), [CLI.md](CLI.md), and
[certified-oss](https://github.com/nickharris808/certified-oss).*
