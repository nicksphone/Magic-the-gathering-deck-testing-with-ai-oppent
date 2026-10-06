# Creature Token Descriptor Types

Isolated baseline: frozen all-six composition copied from
`mtg-next-composed-gate-wASfmI`, with authoritative audit test files copied from
`mtg-next-ui-qualified-vFitDo`. Battlefield source hashes match between those
two inputs. No parent/main edits or running-gate writes.

## Product Scope

New `rules_engine/token_descriptors.py::creature_token_descriptor` separates
leading printed colors, trailing Artifact/Enchantment card types, and remaining
creature subtypes. It emits name/types/type_line/colors for the existing token
handler. `oracle_effects.py::_infer_clause_effect` changes only four lines in
the generic P/T creature-token descriptor block to merge that specification.
No handler, quantity, payment, state, serializer, API, AI or frontend change.
No card-name dispatch; fixed stats and keywords stay in existing compilation.

This is disjoint from Sagan's ordinary instruction / trigger-text projection
ownership: `spell_resolution_text`, clause splitting, instruction/trigger
parsing and event collection are untouched. Apply the four-line oracle delta
against the composed source; report any conflict rather than replacing his
file. Plain creature tokens stay Creature/Token, not implicitly Artifact.

Supported here: the existing fixed-numeric-P/T creature-token clause with
leading printed colors and trailing Artifact/Enchantment modifiers. This does
not certify legendary/named/copy/token-double-face descriptors, arbitrary
quoted abilities or every token grammar. Existing fallback behavior remains
for clauses outside this descriptor grammar; no coverage flags are expanded.

## Independent Fixture Adaptation

The test-only `human_flow_fixture_server.py` delta moves Hangarback's two
counters AFTER entry initialization. Original frozen bad fixture and its
reports remain archived unchanged. No count/type/effective-view/privacy/
restart assertion changes and no historical snapshot repair. This is an
explicit diagnostic board position, not a natural ETB or played-game claim.

## Qualification

Canonical raw fixture/provenance covers Hangarback Walker, Myr Sire, Blade
Splicer, Talrand, Shock, Tower, Anthem and Island. All records were extracted
unchanged offline from parent hash-pinned Scryfall bulk; complete38690-row scan,
IDs/Oracle IDs/file hash preserved; no network or Oracle changes.

Nine new checks include both seats and real checked selected Tower sacrifice:
two-counter Thopter and fixed Phyrexian Myr artifact-creature families retain
exact subtype/name, Artifact/Creature types, flying/empty keywords, colorless
colors, 1/1 base and 2/2 Anthem effective stats. Checked Blade Splicer casting
and ETB creates a colorless 3/3 Phyrexian Golem with effective first strike;
Talrand plus checked Shock creates a blue 2/2 flying Drake without Artifact.
Queued and resolved snapshots survive serialize/restore; checked roots remain
immutable. Existing dynamic-death/boundary/compatibility controls also pass:
112 passed in2.53s (initial run3.09s).

Unchanged human-flow16 assertions, with ONLY explicit fixture ordering adapted:
actual App and checked HTTP, both seats, 210 PASS /2 RED assertions,54.289s,
strict exit1. Hangarback's actual selected sacrifice, death LKI/count/Artifact
metadata, effective 2/2 flying HTTP/UI views, refresh and backend restart pass.
Shark explicit X and actual Renewed optional Apply/Decline pass; actor-private
hand/choices, root purity and stale actual-UI409 after restart pass.

Remaining two REDs are Renewed normal cast gaining8 instead of6 life. That
ordinary-spell projection bug is separate and Sagan-owned, not hidden or fixed
here. No Krosan Tusker compound-clause, full shared browser, blanket card corpus,
AI policy or historical qualification claim.

```sh
MTG_TOKEN_DESCRIPTOR_EVIDENCE=/tmp/owned-token-receipts \
/path/to/external/backend/.venv/bin/python -m pytest -q \
backend/tests/test_canonical_token_descriptors.py \
backend/tests/test_dynamic_death_quantity.py \
backend/tests/test_dynamic_death_quantity_boundaries.py \
backend/tests/test_dynamic_death_quantity_compatibility.py
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/external/frontend/node_modules \
node frontend/tests/browser-human-flow-audit.mjs
```

Product, fixture-only and qualification patches are archived separately, plus
an exact combined patch. Source/receipts/private browser evidence are verified
on mounted NFS; no live SQLite or user game evidence is used.
