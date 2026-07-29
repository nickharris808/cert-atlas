# CLI reference — `cert-atlas`

**The command listings below are generated.** Run `python gen_cli_docs.py` after changing any
argument; a test fails if they are stale.

## Top level

```
usage: cert-atlas [-h]
                  {build,score,baseline,defects,export,submit,leaderboard} ...

A labelled corpus of valid and forged certificates, and a scorer.

positional arguments:
  {build,score,baseline,defects,export,submit,leaderboard}
    build               generate the atlas
    score               score an external verifier command
    baseline            score the bundled reference verifiers
    defects             print the defect taxonomy
    export              export flat JSON splits for a dataset hub
    submit              score a verifier and write a submission record
    leaderboard         render submissions/*.json as Markdown

options:
  -h, --help            show this help message and exit
```

## `cert-atlas build`

```
usage: cert-atlas build [-h] [out]

positional arguments:
  out

options:
  -h, --help  show this help message and exit
```

## `cert-atlas score`

```
usage: cert-atlas score [-h] [--accept-returncode ACCEPT_RETURNCODE] [--json]
                        [--quiet] [-j JOBS]
                        atlas cmd [cmd ...]

positional arguments:
  atlas
  cmd                   verifier argv; use {path} as the artifact placeholder

options:
  -h, --help            show this help message and exit
  --accept-returncode ACCEPT_RETURNCODE
  --json
  --quiet               aggregate only
  -j JOBS, --jobs JOBS  score cases concurrently. Worth it for a subprocess
                        verifier, where the cost is interpreter startup; the
                        result is identical either way
```

## `cert-atlas baseline`

```
usage: cert-atlas baseline [-h] [--anchored] [--json] atlas

positional arguments:
  atlas

options:
  -h, --help  show this help message and exit
  --anchored  supply each case's out-of-band fingerprint (catches everything);
              without it, the artifact-only track is scored
  --json
```

## `cert-atlas defects`

```
usage: cert-atlas defects [-h] [--json]

options:
  -h, --help  show this help message and exit
  --json
```

## `cert-atlas export`

```
usage: cert-atlas export [-h] atlas out

positional arguments:
  atlas
  out

options:
  -h, --help  show this help message and exit
```

## `cert-atlas submit`

```
usage: cert-atlas submit [-h] --verifier VERIFIER
                         [--track {artifact-only,anchored}] [--url URL]
                         [--notes NOTES]
                         [--accept-returncode ACCEPT_RETURNCODE] [-j JOBS]
                         [-o OUTPUT]
                         atlas cmd [cmd ...]

positional arguments:
  atlas
  cmd                   verifier argv; use {path} as the artifact placeholder

options:
  -h, --help            show this help message and exit
  --verifier VERIFIER   name to be listed under
  --track {artifact-only,anchored}
                        artifact-only is the default; the two tracks are not
                        comparable
  --url URL             link to the verifier's source
  --notes NOTES
  --accept-returncode ACCEPT_RETURNCODE
  -j JOBS, --jobs JOBS
  -o OUTPUT, --output OUTPUT
                        write the record here (default:
                        submissions/<verifier>.json)
```

## `cert-atlas leaderboard`

```
usage: cert-atlas leaderboard [-h] [--atlas ATLAS] [-o OUTPUT] [submissions]

positional arguments:
  submissions

options:
  -h, --help            show this help message and exit
  --atlas ATLAS         atlas directory; entries scored against another digest
                        are unranked
  -o OUTPUT, --output OUTPUT
                        write here instead of stdout
```

## Exit codes

Every command in this toolkit uses the same taxonomy, so a caller can branch on it:

| Code | Meaning |
|---|---|
| `0` | verified / sealed / equivalent — the check was made and it stood |
| `1` | refuted by re-derivation |
| `2` | refuted on integrity: fingerprint, manifest, root, commitment |
| `3` | vacuous — nothing was certified |
| `4` | **abstained** — the evidence for an assertion is absent |
| `5` | usage error — not a verdict at all |

`4` is the one worth wiring up. It is not a failure of the artifact; it means nothing was
established, and treating it as a pass is the failure this toolkit exists to prevent.

---

*Part of [certified-oss](https://github.com/nickharris808/certified-oss).*
