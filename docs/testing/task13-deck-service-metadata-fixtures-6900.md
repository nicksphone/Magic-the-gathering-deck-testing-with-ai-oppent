# Task 1.3: DeckService metadata positive fixtures

Base: `6900e9d1dd0bf5589a0c32b6c12cd05effc02e87`. This is a bounded
test/data-only migration, not full Task 1.3 or Phase 1 acceptance.

`test_deck_service_metadata.py` keeps its in-memory repository, three original
test names, deck quantities, curve/color assertions and deliberately unknown
`Missing Oracle Card`. Its negative test is byte-identical. Eight of nine
original assertion ASTs are identical; the sole authorized operand change is
the first split-face name from `Fire // Ice` to the actual printed `Fire`.
The new fidelity test independently checks both full ordered `Fire`/`Ice`
faces at the production service output, including Oracle fields and identity.

Positive rows now use complete official objects and the existing
`ScryfallSyncService._normalize_payload`, not handwritten card attributes.
Only root display-image selection is overridden. The normalizer receives a
truthy local display operand to avoid placeholder I/O during fixture creation.
The in-memory row's opaque `id` aliases the actual public Scryfall UUID; no
database identity or row is created. Ordered face data, legalities and all
other normalizer fields are retained without factual overrides.

The shared `canonical_positive_fixtures.py` is unchanged. Fire // Ice reuses its
pinned full RAW response; Island, Mountain, Secure the Wastes and Dryad Arbor
reuse the pinned seed155 objects/provenance. The new helper adds only Memnite
and Kazandu Mammoth // Kazandu Valley. Their two exact-name Scryfall GETs
returned HTTP 200 before offline testing. Complete response bodies, URLs, UTC
times, headers, byte counts and SHA-256 are retained in
`tests/fixtures/deck_service_metadata_6900/PROVENANCE.json`. There were no art,
rulings or other intake requests. Minimum request-start spacing was 0.5 s.

## Observed qualification

- Original module plus new fidelity module RED: 11 failed, 4 passed, 2.26 s.
  All three original tests passed; actual service-entry captures exposed
  fabricated identities, text, types and incomplete/invented faces.
- Same two whole modules GREEN: 15 passed, 2.55 s.
- Final four whole modules: 35 passed, 3.91 s. These are the two above plus
  `test_deck_analysis.py` and `test_canonical_positive_fixture_fidelity.py`.
  The 15 tests are included in 35, not additional independent evidence.
- Each run used a precollection native audit hook, seven exercised denial
  controls, all SQLite aliases denied, socket/child/provider denied,
  `--noconftest`, no filters, and an outer 300 s TERM / 15 s KILL bound.
- Unexpected I/O attempts: zero. Existing source and 2,946 runtime regular-file
  hashes were equal before/after each run. No database was created; the unused
  import-created engine was disposed. FD sets matched, with no children or
  extra threads. RED created nine owned placeholder SVGs; GREEN/final reused
  these warm media files and added none. These are separate runtime assets,
  not public source changes or cold-cache claims.

No production, schema, UI, AI, shared fixture loader, parent worktree or Git
index was modified. No native browser/game, SQLite connection or provider was
used. Full Task 1.3's literal repository-wide requirement remains open without
a user waiver; this packet addresses only this module's positive card facts.
