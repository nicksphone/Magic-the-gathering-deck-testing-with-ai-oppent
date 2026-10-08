# Current Locked Dependency Advisories

Source: `bf6731cbdfdb9c4e752d23bff84c3e97ed404a17`.
Actual OSV response: HTTP 200, `2026-10-08 23:24:27 UTC`.

All **242 unique locked versions** were queried: 28 PyPI packages from
`backend/requirements-py312-linux.lock` and 214 npm packages from
`frontend/package-lock.json`, including optional platform packages.
**No affected package was returned.** Independent verification reconstructs the
complete request inventory, checks response cardinality and absent pagination,
and compares every archived input against the published source.

| Input | SHA256 |
| --- | --- |
| `backend/requirements-py312-linux.lock` | `5414ba2ce2f5b3f4e11ab3f764d8bea970b48bd146644fcff3415aca76ea273c` |
| `backend/requirements.txt` | `7aa9f2b409551322171d8fdc0fcdde02fc5f38aedacdb9c904d6e47966c95b97` |
| `frontend/package-lock.json` | `4ae850251ee5490028fbe14738d17daa41ef214d6945a60dcdeeb5126c8df6a0` |

Raw requests/responses, HTTP headers, complete input locks, hashes and independent
verification are preserved under:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/dependency-audit/current-bf6731c-20261008/`.
The [OSV batch-query protocol](https://google.github.io/osv.dev/post-v1-querybatch/)
describes the query interface; the archived response is the observed result.

This refresh changes no dependency and performs no installation or runtime test.
It is an advisory-database result at one time, not proof of absence of undisclosed
vulnerabilities or application, operating-system, deployment or complete-release
security. Earlier clean-install/runtime evidence retains its own source pin;
the complete Gate 3 dependency/install requirement remains open.
