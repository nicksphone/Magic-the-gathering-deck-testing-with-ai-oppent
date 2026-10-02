# Offline match admission

## Contract

Live starts, sideboarding and diagnostic games use the same local hydrator.
Admission never calls Scryfall or writes card-cache/knowledge records. Local
placeholder art may be generated in the disposable image cache. Authoritative
match snapshots and idempotency receipts are still persisted normally.

The hydrator reads cached metadata, provenance-checked local Scryfall knowledge,
and the tracked shipped-deck Oracle seed. Canonical knowledge must contain a
card object with matching row name and Scryfall ID; manual tags, malformed JSON
and mismatched profiles do not become invented cards. Front/back name aliases
resolve the canonical multiface record, preserving both faces and deliberate
face choice. Exact names take precedence over aliases. Alias SQL patterns escape
wildcards and restrict candidate rows rather than loading the whole corpus.

Missing type lines, printed creature power/toughness, printed planeswalker
loyalty, special-layout face data and unresolved legacy split-color metadata
fail local admission with structured `422 card_data_unavailable`. Canonical
local data repairs recognized stale split colors and missing layouts in memory,
without rewriting the cached row. Art-series, tokens and emblems are separately
rejected as non-playable deck objects.

`/cards/completeness` uses the same data view and adds readiness, source labels
and image status. Empty queries do not scan all knowledge; query size is bounded.
Readiness is **not** Oracle semantic certification, a supported-card guarantee,
format legality or a promise that all rulings were downloaded. Empty Oracle
text on a canonical vanilla creature is valid; missing rulings stay unverified.

## Explicit synchronization and storage

Single-card and bulk sync accept an explicit `force` refresh. Existing local
art no longer bypasses incomplete metadata checks. A network failure can return
the existing incomplete cache; callers must inspect readiness afterward.
Explicit synchronization remains synchronous, not a bounded background job.

SQLite receives a nullable printed-loyalty column via the existing additive
metadata migration. Canonical bulk normalization, local materialization and
serialization preserve zero and nonzero loyalty. No rules are implemented in
SQL. A verified online backup of the live database was archived on RCHFiles
before applying this migration; running databases remain local.

## Regression coverage

`tests/test_offline_match_hydration.py` forbids network access during cold shipped
deck starts, compares live/diagnostic hydration, checks idempotent starts and
snapshot face restoration, and verifies no cache writes for bulk-only cards or
rejected decks. It also covers malformed provenance, canonical vanilla text,
printed loyalty, repeatable legacy-schema migration, front/back aliases, explicit
land-face play, SQL wildcards, query bounds and sync refresh forwarding.

`tests/test_split_card_casts.py` checks stale face recovery without cache writes.
`tests/test_knowledge_ingest.py` checks read-only bulk-face hydration and HTTP
admission. The dropped-response browser recovery fixture no longer pre-seeds
Island into the cache; it exercises the real cold local setup path.

The Grizzly Bears and Bala Ged Recovery/Sanctuary fixtures retain actual Scryfall
payloads and retrieval provenance. Existing proliferation/counter fixtures supply
the other canonical cards. Tiny fixture decks and direct engine probes test
contracts, not tournament deck legality or matchup strength.

## Acceptance evidence (2026-10-02)

- Fresh tracked-source copy plus this milestone's edits, its own SQLite/cache,
  existing pinned Python interpreter: `python -m pytest -q` passed **2,526** tests
  in 185.04 seconds. Existing deprecation warnings remain (283 reported).
- Focused offline hydration, split casts, cache/image, knowledge, input and
  release-card contracts: **139 passed**. Superseded failures are retained, not
  presented as final passing runs. Two release fixtures now declare their valid
  transform layout; missing-layout canonical repair has separate regressions.
- `npm run lint`, `npm run test:unit` and `npm run build` passed.
  `bash frontend/tests/run-browser-ci.sh` passed its sequential Chromium suite
  (103 scenario assertions), including cold dropped-response starts, process
  restart, sideboards and natural AI/human BO3. DOM-driven fixture controls do
  not certify the alpha layout, real-pointer usability or a new UI design.
- `scripts/regression_matrix_replay.py --matches-per-pair 1 --max-decks 4
  --best-of 1 --max-ticks 1600` covered six pairs, both seat orders: **12 logical
  games / 24 repeatability executions**, zero reported determinism failures,
  timeouts or classified anomalies. Aggro/Tempo/Tokens templates were selected;
  this small smoke matrix is neither full-corpus coverage nor a strength/balance
  measurement.
- A read-only live readiness GET for Island, Bala Ged Recovery, Elspeth and
  Contentious Plan returned 200 and local-ready metadata (0.184 seconds in one
  request). This is a connectivity sample, not a latency benchmark. Services
  remained bound to `0.0.0.0:9999` and `0.0.0.0:5173`.

Evidence, canonical fetch payloads, superseded failures and verified disposable
checkout archives are stored on RCHFiles under
`codex-storage/mtg-deck-testing-lab/diagnostics/offline-match-hydration/20261002T011249Z/`.
The cold pre-migration live database backup is separately retained under
`backups/20261002T004313Z-before-loyalty-cache/`. Running SQLite and dependencies
stayed local. No fresh dependency installation or optional PostgreSQL/deployed
HTTPS certification was performed.

## Known Limitations and Next Upgrades

- Asynchronous bounded sync progress, cancellation and quotas remain unfinished.
- Cache readiness cannot prove complete Oracle clauses, replacement/layer
  fidelity or professional AI decisions. Unsupported mechanics still require
  golden fixtures and explicit coverage diagnostics.
- Canonical local metadata can expose remote art URLs; it does not download all
  artwork or verify rulings. Offline fallback art remains available.
- The optional PostgreSQL path, fresh dependency installation and broad network
  deployment are not certified by SQLite fixture tests.
- Alpha UI redesign is deliberately deferred until backend milestones finish.
