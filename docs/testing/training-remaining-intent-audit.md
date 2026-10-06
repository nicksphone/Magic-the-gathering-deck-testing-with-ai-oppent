# Remaining Non-Mana Intent Audit

Tests/report only. No production changes or training-competence claim.

## Frozen source and results

The isolated copy contains the current parent's integrated six-family guard,
including cast and activated abilities. Its 887-file backend source manifest
was identical before/after copying:
`c02019bbdb63a0f9c8cb57a459d030ef03af04d211a66d627db72d2bde860bf3`.
`training/environment.py` remains
`65b9013f13e2ea3d45241896b3707443c50845e0021bd23899522a151b144aba`.
This qualifies that exact copy, not subsequent parent/main changes.

Two serial gates, no skips, xfails or deselection:

- Remaining families plus separate canonical cycling: 34 FAIL / 24 PASS,
  50 warnings, 64.14 seconds, exit 1.
- Misplaced chosen-parameter aliases: 16 FAIL, 16 warnings, 24.52 seconds,
  exit 1.

These are diagnostic RED baselines, not green release qualification. Forty-eight
consumer tests reach their sole `lookup_intent` rejection expectation and fail
with DID NOT RAISE. Strict `lookup` and actual HTTP reject each payload; HTTP
returns 422 with complete in-memory/controller/database dump unchanged. No test
requires the unsupported request to be accepted or executed first.

The first construction run (34 FAIL / 22 PASS, 35.89 seconds) is also preserved.
Its two extra failing positive controls used Shark Typhoon. Final controls use
Hollow One's supported fixed cycling; the genuine Shark regression is retained
as two separate tests, not hidden or marked expected failure.

## Canonical families

Both seats use real existing fixture records, including original Oracle fields:

| Family | Canonical card | Chosen schema fields | Actual control |
| --- | --- | --- | --- |
| Loyalty | Daretti, Scrap Savant | ability_index=0, targets={} | loyalty 3->5, explicit private Opt discard then draw one |
| Equip | Bonesplitter | target_card_id | attaches to selected Grizzly Bears, not second creature |
| Crew | Smuggler's Copter | crew_card_ids | only selected Grizzly Bears taps; Vehicle becomes Creature |
| Cycling | Hollow One | x_value=0 | pays two, discards source, draws one |

Whole actual legal views plus independently declared chosen actions normalize
to strict lookup's identical encoding; inputs/root remain unchanged. Episode
aliases round-trip chosen action IDs. In-memory continuation/replay and actual
HTTP execution/DB restart verify outcomes. Daretti's private pending discard
boundary is restored/replayed; the other seat gets no private prompts.
Separate byte-equality tests permute opposing hidden hand/library identity and
order without changing actor observation/action/prompt input. Malformed supported
index/target/crew-list/X controls reject through both lookup routes and HTTP.

Unknown/source_zone keys, nonnull and null, are dropped for all four families.
Additional wrong-level chosen fields are also dropped: loyalty target_card_id;
equip targets object/null; crew targets object/null; cycling nested targets.x_value
or null. The variable cycling probe uses actual Shark Typhoon, with offered
top-level X=2 versus incorrectly nested requested X=7. It does not execute the
unsupported request or claim that nested form is supported.

## Narrow proposal, not implementation

Extend only `TrainingEnvironment.lookup_intent`'s public model guard:
AbilityAction for activate_loyalty, EquipAction, CrewAction, CycleAction for their
discriminants. Reject unsupported keys, including null, BEFORE complete_action.
Retain existing six-family semantics; do not alter helper, schema, API or engine.
Qualified display fields from these actual producer views are:

- Loyalty: card_name, ability_label, ability_delta, activation_costs,
  ability_x_cost, ability_x_sign, target_hints.
- Equip: card_name, mana_cost, targets. Here targets MUST retain the qualified
  candidate-list shape; an object/null is an unsupported authoritative alias,
  not presentation metadata. A bare key allowlist would leave four RED cases.
- Crew: card_name, crew_value, suggested_crew_card_ids, activation_costs,
  crew_candidates. Never use a suggested list to infer omitted crew_card_ids.
- Cycling: card_name, mana_cost, activation_costs. Top-level x_value is schema
  input. Variant cycling metadata is not qualified by this bounded audit.

## Independent canonical engine gap

Canonical Shark Typhoon's printed `When you cycle this card` trigger creates no
Shark at X=2, both seats. In-memory and actual HTTP routes pay four, discard,
draw one and survive restart, but neither creates the required 2/2 Shark.
The current cycle matcher recognizes named card references, not this-card
references; canonical field bytes were not rewritten to fit the parser.
Two ordinary RED regression tests preserve this separately. This is not caused
by the intent consumer and is outside this task's production scope.

No exhaustive non-mana coverage is claimed: ninjutsu, combat declarations,
foretell, transform, mechanic/trigger/replacement choices and other discriminants
remain unaudited here. No live/main/parent source writes, external network,
expert-data claim or neural-training qualification.
