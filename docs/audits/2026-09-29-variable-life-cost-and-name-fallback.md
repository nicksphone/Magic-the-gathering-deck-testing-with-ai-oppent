# Variable life cost and name-fallback boundary (2026-09-29)

Status: bounded repair implemented. The three strict expected failures are now positive regressions; the evidence below records the pre-repair defect.

## Evidence

- The local Scryfall-sourced `cardknowledge` row for Toxic Deluge gives `{2}{B}`, Sorcery, and Oracle text: "As an additional cost to cast this spell, pay X life. All creatures get -X/-X until end of turn." The tests use those printed characteristics, not an invented ability.
- `backend/rules_engine/costs.py` only recognizes a numeric additional life cost (`PAY_LIFE_RE`), so its legal move advertises zero life to pay.
- `backend/rules_engine/action_validation.py` accepts an announced `x_value` only if the mana cost contains `{X}`. A checked Toxic Deluge cast with `X=2` is rejected, while a cast with no announced X is accepted.
- When its unsupported Oracle clause reaches the fallback in `backend/rules_engine/oracle_effects.py`, the substring `deluge` in the name produces `draw_cards` with amount 1. A direct `build_spell_spec` probe returned that effect and `used_fallback=False`, so existing unsupported-effect diagnostics would miss the wrong behavior.
- `backend/tests/test_variable_life_cost_audit.py` contains three strict xfails. `pytest -q --runxfail` reproduces all three failures; normal focused pytest reports exactly three xfails. The previous complete suite passed 1,124 tests before these audit tests were added.

## Repair gate

1. Model announced X separately from mana cost, including X in additional costs and effects. Require an explicit bounded X choice; reject negative, missing, or unaffordable values before any mutation. Expose the range to human and AI controllers.
2. Pay the chosen amount through the shared life-payment event, with no event for zero. Preserve payment-trigger order, life-total locks, and snapshot/restart behavior. Casting-cost payment must be atomic if any other component fails.
3. Implement the actual all-creatures `-X/-X` continuous effect through the existing layer/state-based-action model, with turn-end expiry. Check both players' creatures and zero-toughness deaths; do not replace the effect with a one-card handler.
4. Remove or narrowly constrain name-based effect guesses when authoritative Oracle text exists. A parser miss must be visible as unsupported, not silently mapped by a shared word in a card name. Test other name-collision families and canonical Memory Deluge to avoid regressions.
5. Turn the three xfails green with engine, HTTP/UI, AI, snapshot, and deterministic replay coverage. Until then, flag this wording as unsupported in deck diagnostics and do not treat its simulation results as rules-correct.

This is a general semantic-contract problem, not a Toxic Deluge-only fix. The audit does not certify other variable costs or global continuous effects.

## Repair outcome

- The cost model recognizes the supported `pay X life` additional-cost wording. Checked casts require an explicit X; affordability is checked before payment. The shared payment event fires for positive X, and X=0 remains legal without a payment event.
- A reusable all-creatures temporary power/toughness handler applies to creatures present when the spell resolves, on both sides, and expires at cleanup. State-based actions handle creatures reduced to zero toughness.
- AI estimates a useful X from current creature toughness, life risk and friendly losses rather than spending all available life. This heuristic is bounded tactical support, not optimal-play certification.
- When Oracle text is present but not understood, a card-name substring no longer silently substitutes an unrelated effect. Existing blank-text compatibility guesses remain.
- Focused engine, snapshot, HTTP and Chromium human-action regressions now check these paths. A three-game seeded BO3 replay completed without timeout or drift, but did not exercise this card and is not balance evidence. Other variable-cost clauses, combined costs and continuous-layer dependencies remain to be certified.
