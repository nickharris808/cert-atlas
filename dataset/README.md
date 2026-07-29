---
license: apache-2.0
task_categories:
  - other
tags:
  - verification
  - adversarial
  - formal-methods
  - eda
  - certificates
  - benchmark
  - red-teaming
pretty_name: Certificate Failure Atlas
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: valid
        path: data/valid-*.jsonl
      - split: invalid
        path: data/invalid-*.jsonl
dataset_info:
  features:
    - name: id
      dtype: string
    - name: family
      dtype: string
    - name: valid
      dtype: bool
    - name: defect
      dtype: string
    - name: severity
      dtype: string
    - name: title
      dtype: string
    - name: why_it_looks_valid
      dtype: string
    - name: caught_by
      dtype: string
    - name: tags
      sequence: string
    - name: artifact_files
      sequence: string
    - name: artifact_json
      dtype: string
    - name: atlas_version
      dtype: string
    - name: atlas_digest
      dtype: string
  splits:
    - name: valid
      num_examples: 8
    - name: invalid
      num_examples: 28
---

# Certificate Failure Atlas

A labelled corpus of **proof-carrying artifacts that look valid and are not**, with a two-sided
metric for scoring any verifier against them.

## Why this exists

Verifiers are almost always tested on artifacts they are supposed to accept. What matters is what
they *reject*, and there was no public corpus of near-miss forgeries to test that against. So a
verifier's soundness was usually an assertion by its own author.

Every case here is a real artifact produced by a real toolchain, then mutated in one specific,
named way — with the defect label, why the forgery looks valid, and which check is supposed to
catch it.

## Usage

```python
from datasets import load_dataset

ds = load_dataset("<owner>/cert-atlas")
row = ds["invalid"][0]
print(row["id"], "|", row["severity"])
print(row["why_it_looks_valid"])
print(row["caught_by"])
```

No `datasets` install? The corpus is small and the loader is dependency-free:

```python
from loader import load, iter_forgeries
d = load()                       # {"valid": [...], "invalid": [...]}
for case in iter_forgeries():
    print(case["id"], case["title"])
```

To actually **score** a verifier, use the generator package rather than the flat rows — artifacts
are directories and file groups that a table cannot fully represent:

```
pip install cert-atlas
cert-atlas build atlas
cert-atlas score atlas my-verifier --check '{path}'
```

## Schema

| field | type | meaning |
|---|---|---|
| `artifact_files` | list[string] | filenames making up the artifact |
| `artifact_json` | string | JSON object mapping each filename to its contents |
| `atlas_digest` | string | content digest; rows are only comparable at equal digest |
| `atlas_version` | string | the atlas release this row came from |
| `caught_by` | string|null | the check that is supposed to reject it |
| `defect` | string|null | defect key; null for valid cases |
| `family` | string | certificate | receipt | seal |
| `id` | string | stable case identifier, e.g. 'cert.forged_verdict' |
| `severity` | string|null | soundness | integrity | vacuity |
| `tags` | list[string] | free-form labels |
| `title` | string|null | one-line description of the mutation |
| `valid` | bool | whether a correct verifier should ACCEPT this artifact |
| `why_it_looks_valid` | string|null | why a naive verifier would accept it |

`artifact_json` is a JSON object mapping each filename to its contents, so a single row
reconstructs the whole artifact — a `bundle.json` plus its payload files, a receipt, or a sealed
specification. It is a string rather than a nested mapping because filenames differ per case, and a
struct over the union of every filename defeats columnar schema inference.

```python
import json
artifact = json.loads(row["artifact_json"])      # {"bundle.json": "...", ...}
```

Fields that only apply to forgeries (`defect`, `severity`, `title`, `why_it_looks_valid`,
`caught_by`) are the **empty string** on valid rows, not null, so every column has one stable type.

## Splits

Families: `certificate`, `receipt`, `seal`, `sequential`.

| split | rows | contents |
|---|---|---|
| `valid` | 8 | artifacts a correct verifier must **accept** |
| `invalid` | 28 | forgeries a correct verifier must **reject** |

By family: `certificate` (1 valid / 10 forged), `receipt` (2 / 8), `seal` (2 / 3).

## The metric

```
detection   = invalid artifacts correctly REJECTED / all invalid
precision   = valid   artifacts correctly ACCEPTED / all valid
atlas_score = min(detection, precision)
```

Ranking on the **minimum** is the design. Measured:

| verifier | detection | precision | score |
|---|---|---|---|
| reference | 1.000 | 1.000 | **1.000** |
| accepts everything | 0.000 | 1.000 | **0.000** |
| rejects everything | 1.000 | 0.000 | **0.000** |
| crashes on everything | 1.000 | 0.000 | **0.000** |

Both degenerate controls ship with the tooling and are asserted to score zero in its test suite.

## Three cases worth reading

- **`receipt.swapped_cnf`** — the proof genuinely refutes the formula presented; it just is not the
  formula corresponding to the circuits. Catching it needs the *encoder identity* committed, not
  only the proof.
- **`cert.vacuous`** — every certificate deleted. The bundle stays well-formed, so a pure format
  check reports success. This case exists because it was found by attacking the reference verifier,
  which had the bug.
- **`seal.repointed_bound_seal`** — criteria doctored *and* a matching seal minted, so the two agree
  perfectly with each other. Only a binding over both catches it.

## Provenance

Generated by `cert-atlas 1.0.0` from artifacts produced by the
reference toolchain (`lcert-verify`, `equiv-receipt`, `prereg-seal`), then mutated by the named
transformations in `cert_atlas.generate`. No third-party or proprietary data is included; every
artifact is synthetic and generated on demand.

**Atlas digest:** `8b7f021842dff8909e7ea696d28b1896e7411ee185882ecabed6ed1dae7335a1`

The corpus is **byte-reproducible** — nothing is randomised, and `cert-atlas build` from a fixed
version yields this digest. Results at different digests are not comparable, and the scorer reports
the digest with every run.

## Limitations

- **Hand-designed, not exhaustive.** Scoring 1.000 means sound against these 28 forgeries — a lower
  bound on soundness, never a proof of it.
- Cases are deliberately small; they exercise decision logic rather than scale.
- The forgeries were written by the same authors as the reference verifier. That is a real bias, and
  it is why adversarial contributions matter more than passing scores.
- The corpus tests **verifiers**, not physics. It says nothing about whether a certificate's numbers
  describe a real physical object.


## The rest of the toolkit

| | |
|---|---|
| [**lcert-verify**](https://github.com/nickharris808/lcert-verify) | Re-derive a manufacturing certificate's verdict. Stdlib only. |
| [**equiv-receipt**](https://github.com/nickharris808/equiv-receipt) | Prove two circuits equivalent, with a re-checkable receipt. |
| [**prereg-seal**](https://github.com/nickharris808/prereg-seal) | Seal acceptance criteria before you measure. |
| [**cert-atlas**](https://github.com/nickharris808/cert-atlas) | This corpus, plus the scorer. |
| [**certified-mcp**](https://github.com/nickharris808/certified-mcp) | All of it, as tools an AI agent can call. |
| [🔏 **Try the verifier**](https://huggingface.co/spaces/nickh007/cert-verifier) | In your browser. Nothing uploaded. |

## Licence

Apache-2.0. See `LICENSE`.
