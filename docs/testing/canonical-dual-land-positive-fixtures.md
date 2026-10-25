# Canonical Dual-Land Positive Fixtures

This test-only migration covers four existing functions in
`backend/tests/test_mana_system.py`: two Hallowed Fountain resource cases,
the Stomping Ground R/G payment query, and the Battlefield Forge W query.
The qualified Fountain-only function's full-RAW birth implementation is unchanged.

Complete official Hallowed Fountain RAW is retained in
`fixtures/knowledge_profiles/seed155-scryfall.jsonl`, line44 (63 fields).
Stomping Ground and Battlefield Forge are in
`fixtures/mana_canonical_76/official-bulk13.jsonl`, lines1/5 (63/64 fields).
The existing hash-pinned readers validate complete objects and use production
normalization before the real Factory creates physical cards and stock identity.
No shortened Oracle, invented printing or post-birth name/type repair is used.

The other three functions reuse existing `mana_canonical_76.mana_game`, binding
the original seat-one physical slots53/52 before the seeded/native shuffles.
The 120-card resource context, original actors/IDs, controlled untapped battlefield
poses and all175 original assertion expressions are retained. All37 original test
node identities remain; intentional synthetic/negative cases are unchanged.
No production, schema, rules or shared-helper behavior changes.

These are trusted established-board fixtures, not legally played entry episodes.
They do not certify paid shockland entry, Battlefield Forge pain-payment behavior,
complete card support, AI strength, global Task1.3 completion or release readiness.

The prior Fountain-only candidate passed the whole37/111-phase module in a
separate parent-owned run (7.248s; externally closed2026-10-25 01:44:26 UTC).
That result is not a pass claim for this separate four-function candidate.
The separate four-function batch subsequently passed the whole module:37 ordinary
passes and111 phases in7.359s, with all12 native denials expected and no unexpected
native I/O. Source/runtime inputs were unchanged; parent physical closure completed
2026-10-25 02:11:09UTC. Independent static review found no important findings.
Complete hosted CI on the published branch remains required before merge.
