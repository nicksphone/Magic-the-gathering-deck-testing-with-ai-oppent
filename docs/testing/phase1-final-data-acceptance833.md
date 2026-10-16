# Phase1 Final Data Acceptance Component: 833

This is a finite data-acceptance component, not Phase1 completion. It does not
close literal Task1.3, certify all rules support, or inspect live user data.

## Source Boundary

The executed source is immutable Git
`7fddf697342621c42d3ef618bc96443d0cad181e`, backend tree
`edd5bdb738660dc633914f906623285d671bdb5c`, plus the new four-test module
`backend/tests/test_phase1_final_data_acceptance.py`:

```text
SHA256 dfc5dbd685f39833eccf69569245f6c3db0650a4ad8ebd8aa4021d180a126480
```

The gated inventory contains2214 regular source files: the2212 original
backend files, one private source marker, and NEW4. The original16 test modules
are byte-identical, retaining119 top-level test functions and520 assertion
ASTs. The public documentation was written AFTER the gates, outside that
source tree; it is not retroactively included in source pre/post equality.

Static Git-object comparison to published
`4f86df95dfe8e4ebb60f41e1a8229ee633c7d009` confirms unchanged `backend/card_data/`,
`knowledge/`, `persistence/`, `decks/`, the three data-report/sync scripts,
the original16 test modules, and the relevant pinned knowledge/face/export
fixtures. This establishes those declared dependencies' continuity only.
It does NOT claim that the entire4f86 source was executed by this cohort.

## Actual Execution

On2026-10-16 UTC, the parent executed one conditional, sequential V3.1 run:

| Phase | UTC | Actual Result |
| --- | --- | --- |
| Negative preflight | 20:10:20-20:10:22 | exit0, qualified |
| Strict collection | 20:10:23-20:10:34 | exit0, exact833 ordered nodes, no test phases or SQL |
| Whole17-module cohort | 20:10:35-20:11:31 | exit0,833PASS,4170warnings,47.79s pytest |

All2499 setup/call/teardown records passed. There were no failures, errors,
skips or expected-failure exclusions. Collection and cohort retain the exact
ordered identity list, SHA256:

```text
8d2a8ed0ab76f1a7c0cdeb2f814b8e4416c480c727d69b798984f8272dd09458
```

The unchanged work bounds were120s preflight,120s collection and900s cohort,
with one shared15s cleanup allowance per phase. No retry was made.

## What NEW4 Proves

- A copied built-in deck containing a nonexistent card genuinely fails the
  CLI gap report. Mocked official404 remains missing after attempted sync;
  no fabricated canonical cache/knowledge row appears.
- A separate copied built-in containing real Farewell genuinely begins
  unsynced, passes after real in-process CLI sync plus complete rulings intake,
  then repeats offline with zero requests and preserves rows/opaque metadata.
- Shipped, expansion and fixture-stored deck names, case aliases and real
  DFC face aliases join complete official RAW to cache, knowledge and rulings.
  The155-card pinned corpus has443 rulings;35 authentically empty ruling
  lists are verified complete, not treated as missing.
- Actual offline seed and public hydration reconcile canonical text, faces,
  colors and reviewed derivations with retained provenance/raw hashes.
  The seed snapshot and later knowledge snapshot contain17 legitimately
  different printing IDs. Canonical alias/name matching is required;
  false cross-snapshot printing-ID or absent seed oracle-ID equality is not.
  Each output retains its own authoritative printing ID. Legacy empty
  single-face seed layout means normal for canonical comparison, while exact
  seed bytes and exact emitted offline layout remain required.

The seed SHA256 remains
`9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037`.
The full knowledge RAW snapshot SHA256 remains
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
No RAW, seed, production file or original16 test was rewritten.

## Whole-Module Roster

```text
tests/test_knowledge_models.py
tests/test_knowledge_domain_boundaries.py
tests/test_knowledge_json_boundaries.py
tests/test_repository_unicode_names.py
tests/test_knowledge_ingest.py
tests/test_knowledge_ingest_fixture_fidelity.py
tests/test_knowledge_sync_task12.py
tests/test_knowledge_cache_recovery.py
tests/test_knowledge_rulings_corpus.py
tests/test_phase1_stored_deck_corpus_cli.py
tests/test_knowledge_gap_report_fields.py
tests/test_knowledge_gap_report_cli_corpus.py
tests/test_knowledge_gap_report_face_cache.py
tests/test_knowledge_gap_report_face_cache_repository.py
tests/test_task13_seed_loader_migration.py
tests/test_oracle_corpus_report.py
tests/test_phase1_final_data_acceptance.py
```

## IO and Closure

The preimport native guard retained all three SQLite constructor-alias
controls, socket/process/provider denial and finite owned SQL/ASGI bindings.
The cohort recorded553 real SQL connections:305 memory and248 owned-file;
547 engines disposed, zero fixture connections closed by the runner, and
zero unexpected denials. The one original HTTP test retained one startup/
shutdown lifespan and exactly three expected responses: completenessGET200,
suggestGET200 and match-startPOST200. There was no external API access.

All2214 source files and the qualified runtime's3674 regular files,4 links and
429 directories matched their full pre/post inventories. Controller, owner
and job counts returned to zero. Recorded scoped closure was CLEAR_SCOPED;
the actual bounded fuser observer exited1 with empty streams and was reaped.
The parent verified process closure and released its SQL slot at20:11:31Z.

## Evidence and Limits

Private evidence is retained on NFS under:

```text
diagnostics/ci/phase1-final-data-ACTUAL833-V3_1-20261016-dgaOwDiG
```

The archive includes exact source/harness, all three phase receipts/logs,
ordered nodes, JUnit, source/runtime inventories and closed test-database
byte snapshots. Archival reads bytes only; SQLite is never opened on NFS.
The public patch contains only this document and NEW4, no private harness,
runtime dependency tree, credentials or database data.

Historical V2's831PASS/2FAIL remains separate and immutable. Its guard rejected
the reconnect factory, but the runtime class attributes were not logged, so
its actual namespace is UNKNOWN. V3 pure controls validate both narrowly
allowed namespaces with exact node/source/body binding; they do not invent
that missing observation. The initial V3 stale supervisor-root rejection
was found statically before execution; its freeze and pure ledgers remain
separate. The V3.1 one-literal correction has a1P2F-to-3PASS pure root invoice.

This result is not live-cache migration, arbitrary-user-deck coverage,
Task1.3 literal-scope waiver, complete Phase1 acceptance, browser/native
acceptance or AI-strength/performance qualification.
