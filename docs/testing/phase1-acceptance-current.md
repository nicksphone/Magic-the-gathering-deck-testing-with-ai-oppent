# Phase 1 Acceptance Review

Reviewed on 2026-10-15 against the original
[Tasks 1.1--1.4](../plans/2026-09-09-ai-knowledge-base.md).
Phase 1 is **not signed off**. Implemented code, a passed shipped-corpus check,
and completeness of a particular operator's stored decks are different claims.

## Observed Integrated Evidence

The later [hosted cache-recovery checkpoint](current-95aa-complete-ci.md) is
terminal at exact `95aa731e`: 28,628 passed calls and 82 setup skips across
28,710 unique collected nodes, plus 111 separately counted passed subtests.
Independent raw metadata reconciliation specifically verifies all 92
cache-recovery cases' setup/call/teardown records. This qualifies that recovery
correction on its own source, not the subsequent model/repository changes.

Hosted CI run `38666739801`, exact source
`5e40e4e3774c2fbca9c98e5b1910886eb9be50fe`, succeeds. Independently reconciled
sanitized backend metadata accounts for 28,568 distinct collected nodes:
28,486 passed calls and 82 setup skips. The skips are not executed passing
bodies. All teardowns pass; there are no failed, missing, duplicated,
deselected or expected-failure cases. The 81 passed subtest reports are
separate from that unique-node count. No protected trace or raw backend log
was downloaded for this review.

The Phase 1 audit matched its critical model, ingestion, seed and stored-deck
CLI test node hashes to passed setup/call/teardown records, rather than relying
only on the aggregate. The knowledge, card-data, decks, persistence and scripts
trees, backend requirements and hosted workflow are byte-identical between
that source and published `8448e64718e8104a2836b3847f564fbffddb1a4b`.
This supports reuse of those unchanged Phase 1 results, not a claim that the
entire later source or a subsequent cache-recovery correction passed that run.

Private immutable metadata evidence is under the project's NFS archive:
`diagnostics/ci/hosted-5e40-sanitized-terminal-20261015-bNg3DEtN/`.

## Requirement Status

| Task | Established | Still Open Or Different From The Original |
| --- | --- | --- |
| 1.1: Knowledge model | Fields, repository roundtrip, upsert and queries are implemented and tested. The subsequent domain correction declares the two provenance values and numerical bounds, and validates public repository writes before querying or mutating rows. | SQLite storage is unchanged; this is not DB CHECK enforcement or validation of direct ORM/SQL bypasses. Legacy rows remain readable without rewrite. Historical test-first commit chronology has not been reconstructed. |
| 1.2: Corpus sync | Real repository ingestion of the complete official shipped corpus, persisted rulings, error accumulation and idempotent CLI behavior are tested. Stored mainboard and sideboard names participate. Missing-cache recovery is corrected and locally qualified below. An actual network sync of the legacy copy qualifies all 158 requested names. | Hosted qualification of the changed recovery/model code remains separate. The selected deployment database and any live migration remain unestablished. |
| 1.3: Verified offline seed | The production handwritten fallback module is removed; committed official seed data supports tested offline hydration. | The literal requirement of no handwritten Oracle text anywhere in the repository is not met by test fixtures and rule-generated token descriptions. Offline hydration evidence alone is not a deployment-startup certificate. |
| 1.4: Completeness command | The actual CLI succeeds for the default 149-name corpus. An owned stored-deck mainboard/sideboard expands it to 151 names. The separate real legacy-copy run covers 158 names, rejects pending rulings before sync, then passes with zero-request unchanged repetition. | This is not arbitrary deployment data. CLI success does not itself require every display-cache row, nonblank Oracle text or a local image; the legacy-copy report separately verifies its cache/Oracle fields, but not local images. |

The shipped data checks cover 155 canonical identities, 443 published rulings
and 35 verified empty ruling lists. An empty verified list is valid; demanding
a published ruling for every card would manufacture a failure of authentic
data. See [stored-deck corpus evidence](phase1-stored-deck-corpus-current.md).

The implementation uses exact card-name lookup rather than the plan's proposed
fuzzy lookup. Named/search endpoints use a 0.5-second minimum interval and
other endpoints use the configured interval, not the literal proposed
0.25-second interval for every request. These differences are recorded, not
silently described as exact conformance.

## Missing-Cache Recovery Qualification

The corrected ingestor materializes a missing display-cache row from validated
stored canonical facts and verified rulings using the existing local mapper.
It does not re-ingest the knowledge row, reset learned fields or fetch over the
network. Invalid or incomplete recovery inputs remain cache misses; explicit
forced refresh still uses the existing named-card/rulings refresh path.

One final declaration of 12 whole modules passes **268 ordinary cases** in
35.09 seconds, with zero failures, errors or skips. It includes all 92 new
recovery cases and the unchanged model, ingestion, rulings, profile repository,
profile sync, stored-deck CLI, completeness and corpus-readiness modules. The
real original ASGI match-start test remains in the ingestion module; it was not
excluded to call the cohort pure. Its one genuine startup/shutdown completed.

The native pre-import guard admits only owned local SQLite files, their
explicit read-only/read-write URIs, actual in-memory callers and the readiness
script's literal read-only `findmnt` query for owned paths. Physical socket
operations and other child commands are denied. No unexpected denial, job or
thread remained; inherited fixture connections left open were explicitly
closed by the runner. Backend source hashes match before and after.
This is a trusted-cohort connection boundary, not a hostile-SQL or arbitrary
child-process sandbox.

Preserved earlier ledgers distinguish product regressions from harness limits:
the original missing-cache RED, the first correction's malformed-field RED,
the independent DFC-root-field RED, and the two broader runs blocked by the
runner's URI/`findmnt` policy. The earlier 244-pass broader result predates the
last 24 regressions and is not substituted for the final 268-pass result.
This local component does not certify the operator's live data or later whole
hosted CI.

The subsequent [domain-admission correction](knowledge-domain-admission.md)
passes the expanded 27-whole-module, 510-case component, retaining the complete
recovery module and a naturally played existing seeded game. It also has a
distinct zero-request real copied-data follow-up on the corrected model source.
Those results remain separate from the earlier 268-case recovery qualification.

## Legacy Database Inspection

A separate read-only transaction inspected the known legacy deployment file,
without importing the application, making HTTP requests or printing deck
contents. It contains 112 cache rows, 38,690 knowledge rows and 76 stored decks.
Their 113 distinct card names all have canonical knowledge, but only 81 have
the stored verified-rulings flag. The file's size and modification time were
unchanged after the connection closed. This is aggregate diagnostic evidence,
not a full canonical/rulings validation or a write/migration qualification.
The currently selected deployment database has not been established, so this
legacy file is not silently substituted for the operator's current data.

The subsequent [real legacy-copy qualification](phase1-legacy-copy-readiness.md)
uses the unmodified CLIs and actual Scryfall responses on an owned backup.
It reaches 158 cached/canonical names with nonblank Oracle text and verified
rulings, then repeats with zero requests and identical full-table digests.
The original and unrelated user data remain unchanged. This closes the lack of
an actual legacy-copy sync, not selection or migration of the live deployment.

## Closure Work

The subsequent [decoded JSON-field correction](knowledge-json-field-contract.md)
closes another reproduced Task 1.1 gap: declaring encoded fields as strings did
not enforce their specified decoded `list[str]` contents. It preserves encoded
text, arbitrary valid profile JSON and legacy reads, without changing SQLite
DDL or the Unicode repository behavior. Its final parent composition passes
899 ordinary cases in 29 whole modules, retains all preceding 645 test
identities, and separately passes the exact-model real copied-data repeat.
Whole final-source hosted acceptance remains distinct from these results.

The subsequent [Unicode name-identity correction](knowledge-unicode-name-identity.md)
addresses an actual Task 1.1 defect: SQLite `lower()` was not equivalent to
Python casefolding, causing accented-name upsert and lookup failures. The
corrected parent component passes 645 ordinary cases in 28 whole modules,
including the complete ingestion module and original natural-game test, with
no failures/errors/skips or I/O denials. The separate real copied-data repeat
also passes without requests or data changes. These are exact-source local
components, not later hosted CI or live-deployment qualification. The
separate [browser checkpoint](browser-4297-response-boundary.md) records both
current native-vendor successes and the generic recovery failure; neither is
silently substituted for whole-current-source acceptance.

1. Retain the now-passed missing-cache recovery regression and preservation
   coverage in normal CI.
2. Retain the now-completed `95aa731e` hosted cache-recovery result, then
   complete hosted qualification of the later model/repository corrections,
   rather than substituting that preceding source or local components.
3. Establish the selected deployment and qualify any migration, retaining the
   completed legacy-copy result without treating it as authorization to replace
   a live database or publish private data.
4. Resolve the remaining literal specification differences explicitly before
   marking Phase 1 complete. Browser compatibility work does not close them.
