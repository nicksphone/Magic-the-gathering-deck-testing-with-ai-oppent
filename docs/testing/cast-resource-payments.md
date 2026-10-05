# Casting Resource Payments

## Candidate Contract

One shared layer validates explicit delve, convoke and improvise against a locked
total cost. Generic substitutions do not satisfy colorless or snow requirements;
convoke can also satisfy a creature's matching color. Summoning sickness does not
prevent these taps. No substitution produces mana or changes printed mana value.
The implementation follows sections 702.51, 702.66 and 702.126 of the
[Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf).

Legality and actual payment share a resource-plus-mana witness search. Selected
permanents cannot also tap for mana, and selected objects are reserved against
consuming mana abilities. Explicit empty choices preserve resources and require
ordinary payment. A missing choice uses automatic witness selection, which is
not a tactical resource-valuation policy. All rejected external actions use the
existing copy-on-write transaction and do not mutate authoritative snapshots.

The strict API accepts `resource_payment` with `delve`, `improvise`, and `convoke`
lists. Each convoke row contains `card_id` and `pay_as` (generic or a color).
The hand controls expose automatic/manual payment and deliberate color choices
for either human seat. Resource candidates have a runtime-validated contract.
Stack snapshots retain actual mana spent and the selected resource receipt;
ordinary public responses do not expose raw private stack payloads.

## Evidence

- Nineteen unmodified Scryfall card responses, request and hashed provenance are
  retained in `backend/tests/fixtures/cast_resources/`. These are canonical cards
  in constructed payment positions, not invented cards or modified decks.
- 67 dedicated checks pass (63 core/actual-cast cases and four HTTP/SQLite cases).
  The expanded overlapping selection passes 439 checks, including existing
  additional costs, activation payments, kicker, discounts, variable and
  restricted mana. Earlier selections are not additive totals.
- Both-seat real-cast cases cover all three keyword families and Hogaak's
  convoke-plus-delve cost without spending mana. Rejections check full state and
  database preservation; paid stack snapshots survive SQLite restore.
- Six scripted Chromium flows pass for deliberate Dig Through Time, Siege Wurm,
  and Reverse Engineer payment, selected resources, actual mana spent and reload.
  Receipt inspection uses disposable fixture endpoints, not public payload
  exposure. These flows are included in the default browser harness.
- Frontend unit checks, lint and build pass. Full frozen qualification remains
  separate; this is not a released feature or arbitrary-card rules certification.

Initial tests caught an incorrect private helper invocation in the test driver;
it was corrected to pass the existing cost-modifier arguments. Later actual-cast
checks found the separate hybrid validation path lacked resource context; that
shared path now receives the same selected resources and card face. The initial
browser probe incorrectly expected private stack payloads in public views; its
inspection now uses an isolated fixture receipt route without widening production
visibility. No rules checks were weakened to make these tests pass.

## Remaining Acceptance

- Complete the exact-source full backend and complete browser gates.
- Connect resource tapping/graveyard departure to shared event-aware operations,
  with cost trigger staging, APNAP ordering and recovery. Canonical Emmara and
  Tormod data is retained for this next stage but is not evidence of working
  trigger behavior.
- Validate ordered compound costs and newly available resources during mana
  activation or additional-cost payment, and full graveyard-cast permissions.
- Extend granted spell keywords and continuous color-layer fidelity; the current
  layer reuses existing type/color accessors and printed casting keywords.
- Add AI opportunity-cost choices for defenders, mana producers, graveyard
  payoffs and future resource needs, then evaluate natural decisions and their
  hands/boards across unchanged canonical decks. Witness selection is not expert
  resource selection; no desired winner or balance percentage is enforced.
