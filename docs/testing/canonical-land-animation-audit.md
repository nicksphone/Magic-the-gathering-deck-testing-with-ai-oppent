# Canonical Land Animation Audit

## Baseline And Intake

Tests-only source archive of published commit
`55ebc8c6cba982300f85289bdbe3d114fa29b2e5`. All 1,673 captured original
files were verified against their Git blob IDs before testing. No moving
parent source, database, dependency tree, AI policy, engine, or model was edited.

Four complete official Scryfall responses were fetched before the initial
offline gate: Mutavault, Celestial Colonnade, Island, and Flicker. Their raw
SHA-256, Oracle/Scryfall identities, request URLs, timestamps, and response
headers are in `fixtures/canonical_land_animation_audit/provenance.json`.
Requests were bounded to 1 MiB each, with at least 550 ms sleep after each
response, and fail on HTTP errors. API documentation pages returned 403;
the official Scryfall FAQ supplied the rate-limit reference. Documentation
retrieval failure is not presented as successful live documentation access.

Positions use full canonical data and real checked actions, seed 7627,
both seats, retained lands and native same-turn land plays. They are constructed
positions, not natural-game or AI-quality evidence. No animation is injected.

## Terminal Results

Initial whole audit: 60 cases, 24 passes, 36 failures, zero skips/xfails/errors,
exit 1, 8.73 seconds. Separate whole native-mana control module: eight passes,
exit 0, 2.11 seconds. The deferred color assertion was then strengthened to
use the existing effective-color query and preserve printed colors, rather
than prescribing mutation of the physical card's printed color field.
Initial source and ledgers remain preserved.

Final whole two-module audit: 68 cases, **32 passes / 36 ordinary failures**,
zero skips/xfails/errors, exit 1, 9.11 seconds. These are 68 distinct checks;
initial/follow-up executions are repetitions, not additional coverage.

| Surface | Cases | Pass | Fail |
|---|---:|---:|---:|
| Extracted ability, canonical cost, actual affordability, metadata | 4 | 4 | 0 |
| Desired non-noop compiled effect | 4 | 0 | 4 |
| Desired public legal animation, retained/newly played | 8 | 0 | 8 |
| Desired checked payment/resolution/layer/roundtrip | 8 | 0 | 8 |
| Desired sickness, attack/mana and native cleanup | 8 | 0 | 8 |
| Desired resolved-animation source incarnation after actual Flicker | 4 | 0 | 4 |
| Actual native land entry and same-turn tracking | 4 | 4 | 0 |
| Atomic unfunded/wrong-priority/wrong-actor rejection | 12 | 12 | 0 |
| Actual private HTTP, root/SQL purity, persistence restore | 8 | 4 | 4 |
| Actual unanimated native mana controls | 8 | 8 | 0 |

All eight HTTP requests returned controlled 422 `illegal_action`, with whole
root/RNG and memory-SQLite contents unchanged. Actor legal views and responses
exclude the AI opponent's canonical held Flicker. Native cache eviction and
SQLite persistence restore reproduce the complete snapshot. Four funded cases
fail their desired 200 expectation; four unfunded controls pass. This qualifies
rejection/privacy/restore, not successful animated restart or a cold server.
The fixture uses no application lifespan and verifies any existing owned default
DB bytes are unchanged; it never deletes that DB or widens the foreign DB fence.

Twenty failures are **activation-prerequisite blocked**. No cleanup, colors,
all-creature-subtype, keyword, combat, or incarnation defect is independently
established by those unreached assertions. Negative controls certify atomic
rejection, not every later eligibility check: unsupported-effect admission may
mask those checks. Native unanimated mana controls independently execute.

## Concrete Root Cause

`oracle_effects.extract_activated_abilities` extracts ability index 1 and the
correct `{1}` / `{3}{W}{U}` costs. `activated_cost_available` returns true.
`build_ability_spec` then routes the exact extracted instruction through
`infer_effect_from_oracle`, which returns `noop` with an empty payload for both
modern self-animation bodies. `move_generator` filters that noop, so
`checked_action` rejects with `Action is not currently legal` before payment.
The authoritative engine branch also refuses unsupported activated effects.

Current nearby animation logic handles targeted counter-based 0/0 land
animation, not these self-animation instructions. Keeping canonical data or
extracting a payable ability does not supply the missing executable effect.
Both cards' `known_unsupported_mechanics` results are empty; that is a classifier
coverage gap, not support. Nested metadata explicitly reports execution unknown.

## Proposed Shared ABI, Not Implemented

1. A pure `compile_self_land_animation(state, source, instruction)` returning
   a complete typed specification or unsupported. Recognize generic self
   references and the entire land-retention/duration/body instruction, including
   prefix and suffix duration; never dispatch by card name or discard unknown
   clauses. Delegate from the shared Oracle compiler before clause splitting.
2. A generic resolver that reuses existing real activated-cost/stack execution,
   `add_type_effect`, `set_base_stats`, and `add_keyword_effect`. Bind the actual
   announced source's incarnation and zone-change sequence in the specification;
   refuse to affect a departed/reentered object. Do not infer identity at
   resolution or relax cost/priority/ownership checks.
3. Review the layer seam before production: all creature types are a type effect,
   not a fabricated Changeling keyword; Colonnade needs a color effect in the
   existing `card_color_symbols(card, state)` flow, not printed-color overwrite.
   The existing `creature_types(card)` consumer lacks state-aware animation
   overlays. Proposed optional `state` compatibility and source-bound subtype/
   color records need caller and serializer review, not an unapproved model edit.
4. Reuse timestamp/incarnation-bound records and native cleanup. Existing
   cleanup expires type, keyword and base-stat effects, and battlefield departure
   clears type effects. Their adequacy for new subtype/color records is unproven.
   The post-resolution Flicker test is blocked; departure/reentry while animation
   is pending is an additional future qualification requirement, not claimed here.

Potential production ownership spans the Oracle compiler, a generic resolver,
type/color/subtype queries and serialization review. That requires explicit
parent/layer-owner coordination. No shared helper, product patch, schema change,
AI change, permission flag, fake draw, or forced animation event was added.

Rules context was checked from the [official rules page](https://magic.wizards.com/en/rules)
and its [September 25, 2026 document](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt):
302.6 for sickness, 400.7 for object changes, and 613.1d-g for distinct type,
color, ability, and power/toughness layers. This audit covers two families only,
not all manlands or all layer combinations, and conveys no trained competence.
