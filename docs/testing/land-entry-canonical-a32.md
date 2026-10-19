# Canonical Land Entry Fixtures

This test-only component migrates the named-positive inputs in
`backend/tests/test_land_entry_choice.py` to complete, pinned official data.
It changes no production rule, shared factory, action, resource, seed, choice,
or original assertion. The nine original tests and all 54 assertion ASTs remain.

## Admission and Provenance

`backend/tests/fixtures/land_entry_a32/SOURCES.json` binds complete Sacred Foundry,
Lightning Bolt, and Island objects from `knowledge_profiles/seed155-scryfall.jsonl`
and complete Font of Agonies from `damage_life_printed_79`. Existing official
intake provenance, full-file hashes, object hashes, identities, and field counts
are checked before materialization. No new intake, reduced Oracle reconstruction,
or live cache is used. In particular, Font retains its entire activation as well
as its life-payment trigger.

The test-local helper supplies complete rows to the real `MatchFactory` before
physical/sideboard capture. The original 60/60 decks, row quantities, shuffle
seeds, and stock remain intact. Additional Bolt and Font participants use full
native factory-born cards with the original opaque IDs, owners, controllers,
zones, and constructor runtime defaults. No captured Island is retagged, and no
stock, private fact, or printed record is cleared or resealed. These extra runtime
participants are not claims of paid Bolt/Font casting or Font activation support.

## Evidence

Before migration, both whole modules produced 37 PASS / 15 FAIL in 4.50 seconds:
all nine originals passed, while new birth/consumer/snapshot checks exposed the
partial inputs. Independent complete-RAW and coherent-corruption controls passed.
The exact same 52 identities then passed in 5.52 seconds, with no failure, error,
or skip. The 43 new cases observe actual factory birth, original first consumers,
full retained physical/value records, 60/60 stock, IDs, RNG state, and real
snapshot restoration. Typed expectations come independently from official RAW,
not from the migration helper or the game's characteristic parser. Controls
reject coherently corrupted live and retained Oracle, costs, colors, creature
traits, keywords, and artwork.

Both runs used the unchanged existing pre-import guard: all SQLite aliases,
socket/child/provider and application startup were denied, with nine actual
negative controls and zero unexpected I/O. Source and pinned FRESH runtime
bytes, modes, ownership, links and modification times were equal before/after
each run; FDs matched, and no child, extra thread or database remained. The
declared whole-module ceiling was 200, with outer/test 900 seconds and TERM+15.
This document is post-gate documentation, not part of the executed source input.

This is a bounded pure fixture component, not whole-backend, application/native,
Phase1, RC, or literal-zero signoff. Unresolved synthetic/protocol literal scope
elsewhere is not waived.
