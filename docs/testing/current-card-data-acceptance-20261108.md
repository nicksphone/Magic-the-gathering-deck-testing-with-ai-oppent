# Current-source card-data acceptance

The seventeen whole modules in the [original 833-case data declaration](phase1-final-data-acceptance833.md)
pass again on the isolated `4775d475` backend/audit archive, whose tracked bytes
remain identical to the current candidate's backend/audit tree. The current
execution passes **833 tests** in 43.21 seconds, with zero failures, errors or
skips. Its ordered JUnit identities are unique and retained privately; this is a
new execution, not a transfer of the October result.

| Whole module | Passed |
| --- | --- |
| `test_knowledge_models.py` | 5 |
| `test_knowledge_domain_boundaries.py` | 34 |
| `test_knowledge_json_boundaries.py` | 254 |
| `test_repository_unicode_names.py` | 135 |
| `test_knowledge_ingest.py` | 20 |
| `test_knowledge_ingest_fixture_fidelity.py` | 4 |
| `test_knowledge_sync_task12.py` | 33 |
| `test_knowledge_cache_recovery.py` | 92 |
| `test_knowledge_rulings_corpus.py` | 4 |
| `test_phase1_stored_deck_corpus_cli.py` | 3 |
| `test_knowledge_gap_report_fields.py` | 44 |
| `test_knowledge_gap_report_cli_corpus.py` | 8 |
| `test_knowledge_gap_report_face_cache.py` | 14 |
| `test_knowledge_gap_report_face_cache_repository.py` | 6 |
| `test_task13_seed_loader_migration.py` | 169 |
| `test_oracle_corpus_report.py` | 4 |
| `test_phase1_final_data_acceptance.py` | 4 |

The existing assertions exercise canonical complete records and rulings,
casefold/face joins, malformed input, recovery, actual owned SQLite repositories,
in-process gap/sync CLIs, idempotent repeated intake and offline hydration. Official
HTTP responses come from the existing complete fixture corpus through
`httpx.MockTransport`; no external service is contacted. These are fixture and
component checks, not arbitrary-card rules support or live-cache migration.

The original 900-second cohort bound remains, with a 915-second outer bound.
The [test-only 10 ms timer](asgi-timer-qualification-20261108.md) is used for the
existing offline HTTP case; one event loop and 23 timer ticks are observed.
Application sources, tests, assertions, fixture data and policies are unchanged.
The cohort records 553 SQLite connections involving literal process-local
`:memory:` and 236 distinct file targets within its new bootstrap/pytest roots.
Per-kind connection counts were not retained and are not inferred from the
historical run. Six positive and nine negative native SQLite alias controls
check the runner's target admission before application imports.

All 2,875 bound source hashes match before/after. Children and external networking
remain forbidden; zero denied events occur during the cohort. The target audit
does not establish a complete filesystem or SQLite `ATTACH` fence. Existing
deprecation warnings remain visible (4,170). The source uses the existing
installed Python dependencies, so this is not a clean-install certificate.
Independent read-only review verifies JUnit, the exact roster, runner pin,
source hashes and SQL target metadata, with no findings.

The declaration, runner, controls, JUnit, ordered nodes and independent metadata
verification remain private under
`/home/nick/mtg-rc-evidence-20261108/http-current-4775/canonical-data/` and its
adjacent runner/control paths. No user database or private game trace is included
in the public change. Literal Task 1.3 cleanup, full Phase 1, whole-backend hosted
CI, browser/native acceptance and all RC gates remain open.
