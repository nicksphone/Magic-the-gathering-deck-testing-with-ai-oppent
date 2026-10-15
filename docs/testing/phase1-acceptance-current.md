# Phase 1 Acceptance Review

Reviewed on 2026-10-15 against the original
[Tasks 1.1--1.4](../plans/2026-09-09-ai-knowledge-base.md).
Phase 1 is **not signed off**. Implemented code, a passed shipped-corpus check,
and completeness of a particular operator's stored decks are different claims.

## Observed Integrated Evidence

The subsequent exact [`7d2d77bd` whole hosted run](current-7d-complete-ci.md)
succeeds: 29,130 passed calls and 82 setup skips across 29,212 unique nodes,
plus 111 separately counted passing subtests. All retained 899 component
identities pass all three phases. This closes hosted acceptance of the Task 1.2
fuzzy-request/spacing correction and shared copier on that source. The newer
[canonical cache-rule recovery](canonical-cache-rule-recovery.md) has a distinct
603-case local pass and actual two-pass copied-data repair; its own whole hosted
result remains separate. Neither result resolves the literal test-data scope.

The subsequent exact `b443db8a` workflow is terminal success. Independent
sanitized metadata reconciliation verifies 29,150 unique nodes: 29,068 passed
calls and 82 setup skips, with 111 passing subtest reports counted separately.
All retained 899 component identities and their 2,697 phases pass; the five
historical source guards and 17 added identities also pass, with none removed.
This closes hosted acceptance of that test-only correction, not the later
`7d2d77bd` copier and Task 1.2 changes. See
[the exact source and reconciliation](current-b443-complete-ci.md).

The subsequent exact `2d106588ace24587b7b04f3719ba90606ab47017` hosted run
qualifies all 899 retained component identities: each has one passed setup,
call and teardown, with no missing, duplicate or non-passing matched phase.
An independent comparison also matches all 1,986 archived backend files,
including every one of the 29 component test modules, to the published
`bca3ebd4` backend. The backend and hosted workflow are byte-identical between
these two commits. This closes the outstanding hosted-evidence gap for the
model/domain/JSON/Unicode/cache components, not the literal specification
differences below.

That older whole hosted run remains **failed**: 29,046 passed calls, five failed
source-compatibility guards and 82 setup skips across 29,133 collected nodes.
Its 111 passed subtest reports are separate. All five failures are outside the
retained 899 cases; they reject the evolved repository against older finite
source-restoration recipes. Those guards require a scoped correction retaining
their mutation rejection, not deletion or a blanket source-pin replacement.
The protected trace and raw backend job logs were not downloaded.

The follow-up is test-only: a separately pinned finite inverse restores the
current repository to its earlier approved bytes, then applies the unchanged
historical inverse. Public Git preimage, intermediate and current blobs match
the declared domain/Unicode commits. The helper still returns the actual input
SHA and rejects changes inside or outside the approved hunks. Original JSON
contracts, repository implementation and costs remain unchanged.

All 108 ordinary cases in seven whole affected modules pass in 39.53 seconds,
with no failures, errors or skips. The declaration includes the five original
failures, 17 new negative/authority controls and unchanged real cold HTTP
restart cases. All before/after source hashes match; reported server children
end and direct checks of eight actual local database files find no handles.
This is a trusted fixture-cohort result, not a hostile-child sandbox or a new
whole hosted pass. The original failed hosted ledgers remain unchanged.

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

| Task | Established | Remaining Evidence Or Scope Limits |
| --- | --- | --- |
| 1.1: Knowledge model | Fields, repository roundtrip, upsert and queries are implemented and tested. The subsequent domain correction declares the two provenance values and numerical bounds, and validates public repository writes before querying or mutating rows. | SQLite storage is unchanged; this is not DB CHECK enforcement or validation of direct ORM/SQL bypasses. Legacy rows remain readable without rewrite. Historical test-first commit chronology has not been reconstructed. |
| 1.2: Corpus sync | Real repository ingestion of the complete official shipped corpus, persisted rulings, error accumulation and idempotent CLI behavior are tested. Stored mainboard and sideboard names participate. Missing-cache recovery and later model/repository components are hosted-qualified on their exact sources, including the retained 899-case joins. An actual network sync of the legacy copy qualifies all 158 requested names. The subsequent `7d` whole CI qualifies fuzzy lookup and request spacing; corrected cache recovery also repairs 78 copied-data rows and repeats with zero changes. | The newer cache correction still needs its own whole hosted result. Copied-data qualification does not select a live deployment or authorize migration. |
| 1.3: Verified offline seed | The production handwritten fallback module is removed; committed official seed data supports tested offline hydration. | The literal requirement of no handwritten Oracle text anywhere in the repository is not met by test fixtures and rule-generated token descriptions. Offline hydration evidence alone is not a deployment-startup certificate. |
| 1.4: Completeness command | The actual CLI succeeds for the default 149-name corpus. An owned stored-deck mainboard/sideboard expands it to 151 names. The separate real legacy-copy run covers 158 names, rejects pending rulings before sync, then passes with zero-request unchanged repetition. | This is not arbitrary deployment data. CLI success does not itself require every display-cache row, nonblank Oracle text or a local image; the legacy-copy report separately verifies its cache/Oracle fields, but not local images. |

The shipped data checks cover 155 canonical identities, 443 published rulings
and 35 verified empty ruling lists. An empty verified list is valid; demanding
a published ruling for every card would manufacture a failure of authentic
data. See [stored-deck corpus evidence](phase1-stored-deck-corpus-current.md).

The earlier implementation used exact card-name lookup and allowed other
endpoints below the proposed quarter-second request spacing. The subsequent
Task 1.2 correction below addresses those two gaps. Named/search requests retain
their longer 0.5-second minimum, rather than increasing network request rates.

## Task 1.2 Protocol Follow-Up

The corrected sync uses the specified fuzzy endpoint but requires its returned
canonical name or an allowed real face name to match the requested corpus
identity before persistence. It cannot silently substitute a nearby typo or
unrelated card. All endpoints now retain at least 0.25 seconds between requests;
longer caller intervals, the named/search floor and existing 429 handling remain.

The new 33-case module first reports 23 failures and ten passes. The corrected
nine-whole-module composition passes all 231 cases in 77.16 seconds, with no
failures, errors or skips. Two existing modules change only four request operands
from `exact` to `fuzzy`; their assertions and request counts remain intact.
The declaration retains real repository, CLI, recovery, face-alias, forced-refresh,
verified-empty-rulings and learned-field preservation controls. Independent
source review finds no actionable regression. This is a trusted owned-SQL cohort,
not a child sandbox, a natural AI game or a live-provider result.

A distinct real-provider check then syncs Lightning Bolt and the front-face name
Fable of the Mirror-Breaker into a fresh owned database using the corrected
production ingestor. All four actual API responses return 200, both canonical
records have verified rulings, and a new-session repetition makes zero requests.
The source remains unchanged and the closed database has no remaining handles.
This is two-name protocol evidence, not another full-corpus or live-data run.

The first attempt stopped before test execution because pytest scanned the
operator's home directory. Its separate failed ledger is preserved; fixing only
the runner's working directory produced the meaningful RED and GREEN above.
Final hosted acceptance for this protocol correction is subsequently established
by the exact `7d` result above. The literal handwritten-test-data scope question
remains open; this correction does not itself sign off Phase 1.

## Named-Card Fixture Follow-Up

The ingestion module's positive Bolt, Island, Grizzly Bears and Delver fixtures
now load complete pinned official objects instead of assembling card metadata.
All 20 existing tests and 88 assertions remain; two expected operands now use
the genuine full legalities map and Oracle identity. Deliberately invalid
identity/mutation vectors remain explicitly noncanonical.

The original nine Task 1.2 modules plus the new four-case fidelity module pass
one ten-whole-module cohort: 235 cases in 69.351 seconds, with no failures,
errors or skips. Production ingestion, canonical fixture files and runtime
dependencies are unchanged. This closes those four positive fixture gaps,
not the repository-wide synthetic/token/history scope question or whole hosted
acceptance. See [the exact fixture evidence](knowledge-ingest-canonical-fixtures.md).

## Delver Cache Fixture Follow-Up

The later [Delver cache-fixture correction](task13-delver-cache-fixture-fidelity.md)
also replaces an incomplete named positive fixture with the complete pinned
official root/face projection, retaining only explicit image overrides. Its
two-whole-module run passes all nine cases, preserving the original six tests
and all 40 assertions. That is another bounded Task 1.3 fixture migration, not
resolution of the remaining repository-wide handwritten-data requirement.

The adjacent [card-hydration fixture migration](canonical-hydration-fixtures.md)
replaces truncated Skewer/Figure facts, reduced Valki faces and the unnamed
devoid example with complete pinned official inputs. Deliberate missing-metadata
and unknown-card boundaries remain explicit. All five original tests and their
14 assertions remain. One final five-whole-module composition includes both
hydration migrations and the preceding ingestion-fidelity module: 24 ordinary
passes, zero failures/errors/skips, with physical SQL/socket/child denial active.
That does not certify HTTP, arbitrary gameplay or the remaining fixture families.

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
The subsequent exact hosted identity/phase join and backend byte comparison
above establish that same component on published source. Whole-run acceptance
remains distinct and is not inferred from those component passes.

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
2. Retain the `95aa731e` cache-recovery result and the now-established exact
   `2d106588` hosted proof for all 899 later component cases. The five historical
   guards are corrected and locally requalified in the 108-case whole-module
   cohort; the subsequent exact `b443db8a` whole workflow now succeeds. The later
   Task 1.2 changes subsequently pass whole hosted CI on exact `7d`; retain that
   source boundary and separately review the later cache correction's result.
   Do not label the preceding failed whole run a pass.
3. Resolve the remaining literal specification differences explicitly before
   marking Phase 1 complete. Browser compatibility work does not close them.

Selected-deployment startup and migration remain release-operations work. The
completed copied-data sync is not authorization to replace a live database or
publish private data. These boundaries do not add DB CHECK constraints, test
history reconstruction, image completeness, browser acceptance or AI benchmarks
to the original Phase 1 model/ingestion/seed/completeness exit criteria.
