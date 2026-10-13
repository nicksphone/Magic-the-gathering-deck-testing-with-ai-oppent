# Current Locked Dependency Advisories

## October 13 Refresh

Pinned `2f42a6eb352480fae1940018b70f4395c478c38e` retains all three lock/input
hashes below. A fresh official OSV batch request queried all 242 unique locked
versions (28 PyPI, 214 npm). HTTP 200/curl exit 0 returned 242 complete results,
no affected package, no errors and no continuation token. Independent verification
reconstructed the complete inventory and compared inputs to the pinned Git blobs.
Only public package names, ecosystems and versions were transmitted.

The new immutable evidence is
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/dependency-audit/current-2f42a6e-20261013-KDnZJa16/`.
Its report hash is `f3f1c313550b9964e169c6f0adff0f013562582fc1bdbcbe04ed986f9e5a2ae3`.
No dependency changed or was installed. Current CI installs `requirements.txt`
with resolver-selected transitives; this exact lock audit does not automatically
certify that runtime closure. Current clean-install, runtime and deployment
acceptance remain separate Gate 3 requirements. The earlier evidence below is
preserved, not relabeled. API ordering and pagination semantics are documented
in the [official OSV protocol](https://google.github.io/osv.dev/post-v1-querybatch/).

## October 11 Refresh

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
