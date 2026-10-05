# Affinity Cost Determination

Affinity is evaluated in application code through the shared cost-modifier
pipeline. Cast legality, checked payment and production AI affordability use
the same reduction. Printed mana costs and mana values are not rewritten.

## Supported behavior

- Intrinsic affinity for supported permanent types, tokens, artifact creatures,
  basic land types, Gates, Towns, snow lands, historic permanents, outlaws,
  creature subtypes, Foods, Equipment and Auras.
- Whole unconditional controller-scoped spell grants: all spells, artifact
  creature spells, enchantment spells, creature/planeswalker spells and
  instant/sorcery spells. Each applicable instance adds its own discount.
- Current controlled battlefield objects, not hand/graveyard/opponent objects;
  effective card types and supported land-type effects determine eligibility.
- Discounts reduce generic mana only, after increases. Colored, colorless and
  snow requirements remain payable normally. Activated abilities do not receive
  spell affinity discounts.
- Cost requirements are determined before mana abilities and additional-cost
  sacrifices, using the existing announced-payment pipeline.
- Domain uses the same effective land-type view: supported type additions and
  replacements change distinct basic land types without changing printed data.
- Printed changeling supplies creature subtypes through the shared subtype view,
  including outside the battlefield; later ability loss does not erase that
  type-layer result. A later granted keyword alone is not a printed CDA.

Conditional, next-spell and exile-trigger affinity grants remain unsupported
and are explicitly reported as `unsupported affinity clause`. A supported
affinity line does not certify the rest of a card's Oracle text or all Magic
layer interactions.

## Evidence

Canonical Scryfall fixtures retain complete card records and SHA-256 provenance
under `backend/tests/fixtures/affinity/`. No competitive decks or card text were
invented or rebalanced. Rules reference: [Comprehensive Rules, effective
2026-09-25](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
702.41 and casting cost determination 601.2f-h.

Focused suites exercise both seats, cost/controller/zone boundaries, colored
mana, static-grant stacking, type changes, atomic HTTP rejection, persistence,
and actual production AI selection and payment. Qualification counts and
remaining release gates are recorded in `plan.md`; narrow tests are not
arbitrary-card correctness or seasoned-player AI certification.
