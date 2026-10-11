# Current Locked Dependency Advisories

Source: `1a8e086964039605a8663a5f4e51d3e3902ffe14`.
Actual OSV refresh: HTTP 200 on `2026-10-11` at `02:07:07 UTC`; curl exits zero.

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
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/dependency-audit/current-1a8e086-20261011-a4PZmFIR/`.
The request inventory was reconstructed from the current complete locks and
compared with the previous full inventory. All inputs remained byte-identical
to the published source before and after the request. Response cardinality is
242, with no errors or continuation tokens. Only public package names,
ecosystems and versions were transmitted; no private project trace was sent.
The earlier `7109992` scan and pip-check retain their own immutable evidence;
pip-check was not rerun as part of this advisory refresh. The older `bf6731c`
scan retains its own differing frontend lock pin and immutable archive.
The [OSV batch-query protocol](https://google.github.io/osv.dev/post-v1-querybatch/)
describes the query interface; the archived response is the observed result.

This refresh changes no dependency and performs no installation or runtime test.
It is an advisory-database result at one time, not proof of absence of undisclosed
vulnerabilities or application, operating-system, deployment or complete-release
security. Earlier clean-install/runtime evidence retains its own source pin;
the complete Gate 3 dependency/install requirement remains open.
