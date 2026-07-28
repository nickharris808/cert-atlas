# cert-atlas

![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![cases](https://img.shields.io/badge/atlas-26%20cases%20%2F%2021%20forgeries-blueviolet)
![tests](https://img.shields.io/badge/tests-38%20passing-brightgreen)
![status](https://img.shields.io/badge/status-pre--release-orange)

**A corpus of certificates that look valid and are not — and a metric that a
reject-everything verifier cannot win.**

Verifiers are almost always tested on artifacts they should accept. What matters is what they
*reject*, and there has been no public corpus of near-miss forgeries to test that against. So
soundness is usually an assertion by the verifier's own author. This is the corpus that turns it
into a number.

## Install

> **Status: pre-release.** Not yet on PyPI. Until it is published, install from a checkout:
>
> ```
> pip install ./lcert-verify ./equiv-receipt ./prereg-seal ./cert-atlas
> ```

```
pip install cert-atlas
```

## 30-second quickstart

```
cert-atlas build atlas
cert-atlas baseline atlas
```

```
atlas 1.0.0  (26 cases)
  detection  1.000   (invalid artifacts correctly rejected)
  precision  1.000   (valid artifacts correctly accepted)
  ATLAS SCORE 1.000  = min(detection, precision)
  sound: YES
```

Now score *your* verifier — any command, any language:

```
cert-atlas score atlas my-verifier --check '{path}'
```

Exit code 0 means a perfect score. Anything else prints exactly which forgeries got through.

## The metric

```
detection   = invalid artifacts correctly REJECTED / all invalid
precision   = valid   artifacts correctly ACCEPTED / all valid
atlas_score = min(detection, precision)
```

Ranking on the **minimum** is the entire design. Consider the two ways to cheat:

| Verifier | detection | precision | **score** |
|---|---|---|---|
| Reference | 1.000 | 1.000 | **1.000** |
| Accepts everything | 0.000 | 1.000 | **0.000** |
| Rejects everything | 1.000 | 0.000 | **0.000** |
| Crashes on everything | 1.000 | 0.000 | **0.000** |

Both degenerate strategies are shipped as controls and are asserted to score zero in the test
suite. A crash counts as a rejection, so crashing is not a strategy either.

A claim of soundness requires **detection = 1.000**. Anything less means a forgery in this atlas
gets past you, and the report names which.

## What is in it

26 cases, 21 of them forgeries, across three families:

| Family | Valid | Invalid | Certifies |
|---|---|---|---|
| `certificate` | 1 | 10 | a manufacturing admission verdict over per-locus physical margins |
| `receipt` | 2 | 8 | logic equivalence of two circuits, via a DRAT refutation |
| `seal` | 2 | 3 | that acceptance criteria were fixed before measurement |

Three worth singling out:

- **`receipt.swapped_cnf`** — the proof genuinely refutes the formula presented. It is just not the
  formula corresponding to the circuits. Catching it requires committing the *encoder identity*,
  not only the proof. Most equivalence tooling does not.
- **`cert.vacuous`** — every certificate deleted; the bundle stays perfectly well-formed, so a pure
  format check reports success. This case exists because it was found by attacking our own
  verifier, which had the bug.
- **`seal.repointed_bound_seal`** — the criteria are doctored *and* a matching seal is minted, so
  specification and seal agree with each other perfectly. Only a binding over both catches it.

`cert-atlas defects` prints the full taxonomy with, for each entry, why the forgery looks valid and
which check is supposed to catch it.

## Submitting

Two kinds of contribution, and the second is worth more:

1. **A verifier submission.** Run `cert-atlas score` and open a PR adding your result. Include the
   atlas digest — results are only comparable at equal digest.
2. **A new defect class.** If you can construct a forgery the reference verifier accepts, that is
   the most valuable thing you can send. It becomes a case, and the reference gets fixed. The
   atlas is designed to be embarrassing to its own authors.

## Reproducibility

The atlas is **byte-reproducible**: a fixed version yields a fixed content digest over every case
file, recorded in `index.json` and asserted by the test suite. Nothing is randomised. Results at
different digests are not comparable and the scorer reports the digest with every run.

## Honest limitations

- Hand-designed, **not exhaustive**. Scoring 1.000 means sound *against these 21 forgeries* — a
  lower bound on soundness, never a proof of it.
- Cases are deliberately small; they exercise decision logic, not scale.
- The forgeries were written by the same people as the reference verifier. That is a real bias, and
  it is the reason contribution #2 above matters more than #1.

## What this does not measure

The atlas scores whether a verifier catches forgeries. It says nothing about whether the underlying
certificates are *physically meaningful* — whether the numbers in a manufacturing certificate
actually describe your mask. That requires sound enclosures over physical models, which is a
separate closed product and not in these packages. A verifier scoring 1.000 here is trustworthy
about arithmetic and integrity, which is necessary but not sufficient.

## Licence

Apache-2.0.
