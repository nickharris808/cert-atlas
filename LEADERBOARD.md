# Leaderboard

Scores are `min(detection, precision)`. A verifier that accepts everything and
one that rejects everything both score **0.000** — the metric cannot be won
from one side.

Atlas digest: `a8e087f0acbc28559b6f17dea0a71fef8633ebdface85a98adf16bd7c4f12a1f`  
Submissions scored against a different digest are listed as unranked: corpora differ, so the numbers are not comparable.

## Track: anchored

The verifier is given each case's out-of-band fingerprint. Everything is catchable here.

Attainable ceiling in this track: **1.000** (computed from the corpus, not assumed).

| # | Verifier | Score | Detection | Precision | Missed |
|---|---|---|---|---|---|
| 1 | [lcert-verify (anchored)](https://github.com/nickharris808/lcert-verify) | **1.000** | 1.000 | 1.000 | — |

## Track: artifact-only

No fingerprint — the verifier sees only the artifact. A self-consistent forgery is **not** catchable in this track by anyone, so 1.000 is not attainable.

Attainable ceiling in this track: **0.955** (computed from the corpus, not assumed).

| # | Verifier | Score | Detection | Precision | Missed |
|---|---|---|---|---|---|
| 1 | [lcert-verify (reference)](https://github.com/nickharris808/lcert-verify) | **0.955** | 0.955 | 1.000 | `cert.self_consistent_forgery` |

---

Submit with `cert-atlas submit`. A forgery the reference verifier **accepts**
is worth more than a passing score — see CONTRIBUTING.
