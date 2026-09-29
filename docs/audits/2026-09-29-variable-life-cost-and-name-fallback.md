# Variable life cost and name-fallback boundary (2026-09-29)

Status: open. Three strict expected-failure tests pin a real-card defect; no gameplay repair is included in this audit.

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
