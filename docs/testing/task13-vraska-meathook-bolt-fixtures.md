# Three Positive Fixture Inputs

This bounded test-only batch starts from `18de7aad2cca77e682abbf0ab4a15825645302d3`.
It supplies existing complete pinned RAW before native capture for one Vraska
input, one Meathook cast input, and the HTTP shield test's Bolt in both seats.
It does not change rules, shared canonical helpers, RAW fixtures, golden guards,
or acceptance scope.

## Print And Pose

- `test_loyalty_destruction_scope_diagnostic.py`: the canonical Vraska alone
  uses the existing hash-pinned `vraska_full/fixtures/vraska-scryfall-raw.json`
  (66 fields). A small local adapter normalizes the entire object and uses a
  private quantity-eight, seed-zero Factory before replacing only the original
  battlefield pose. The three separate diagnostic primitive tests are unchanged.
- `test_meathook_etb.py`: the real cast input uses full row 103 (64 fields) from
  existing `fixtures/knowledge_profiles/seed155-scryfall.jsonl`, with the same
  local before-birth pattern. Seed lookup, original seed 209, X=2, generic scene
  creatures, actions and assertions stay intact.
- `test_shield_counters.py`: Bolt reuses `browser_positive83_canonical.card` and
  its full row 57 (66 fields). The original `allocate_object_id()` executes once
  at the same constructor-argument boundary. Both original player branches and
  all HTTP/persistence actions remain. The RAW printing UUID differs from the
  old normalized seed printing; carried Oracle/mana/type/name agree. No old
  complete-print provenance is claimed.

The two local adapters accept no original state, allocate no original game ID,
and mutate no original RNG. A truthy display-only normalizer operand avoids
placeholder-art writes; the original `image_uri=None` pose remains separate.
All 24 original test definitions and 125 original assertion ASTs are retained.
None of the three modules belongs to the original protected-function golden.

## Evidence Boundary

The four new native fidelity cases are authored but UNEXECUTED locally while
the separate native/game lease is held. They import the real `canonical_cards`
fixture into this test module only (no global plugin or direct fixture call).
They delegate actual RAW file reads, normalization, Factory and post-init,
inspect current physical/copiable records and final pose, and stop at the first
consumer: Vraska's initial snapshot, Meathook's checked cast, or Bolt's persist.
The Bolt spy patches the defining persistence-helper module before the old
test's local import, and checks state invariance after its intentional allocation.

These early-stop witnesses are not paid-birth, rules, HTTP/SQLite, SourceScope
identity, AI or outcome certificates. Original native tests must still execute
unchanged in fresh complete hosted CI. Locally executed AST/RAW metadata checks
are inert source/data checks only, not substitutes for that semantic gate.
This narrow repair does not close Task 1.3's remaining scope or Phase 1 acceptance.
