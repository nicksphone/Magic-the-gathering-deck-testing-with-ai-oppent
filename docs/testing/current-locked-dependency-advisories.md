# Current Locked Dependency Advisories

Source: `710999231ee0b39f8e0498d584294c3629ee1120`.
Actual OSV refresh: HTTP 200 on `2026-10-10`; curl exits zero.

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
| `frontend/package-lock.json` | `12be244799d3aa395226f917d53ad152bbe0d868acaba5814ab1b8b31a55470c` |

Raw requests/responses, HTTP headers, complete input locks, hashes and independent
verification are preserved under:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/dependency-audit/current-7109992-20261010-rJ0OCFeN/`.
The independent parser verifies all query inputs and responses; pinned backend
pip-check also reports no broken requirements. The older `bf6731c` scan retains
its own differing frontend lock pin and immutable archive.
The [OSV batch-query protocol](https://google.github.io/osv.dev/post-v1-querybatch/)
describes the query interface; the archived response is the observed result.

This refresh changes no dependency and performs no installation or runtime test.
It is an advisory-database result at one time, not proof of absence of undisclosed
vulnerabilities or application, operating-system, deployment or complete-release
security. Earlier clean-install/runtime evidence retains its own source pin;
the complete Gate 3 dependency/install requirement remains open.
