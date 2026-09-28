# Life-payment trigger boundary (2026-09-28)

Status: open, reproduced with a strict expected-failure real-card regression. This is not a general payment-event implementation.

## Rules evidence

- [Wizards' Magic Arena Sylvan Library developer diary](https://magic.wizards.com/en/news/mtg-arena/dev-diary-sylvan-library) explicitly discusses Font of Agonies triggering separately for separate life payments. The supported trigger must use the amount of each payment, not an end-of-action life-total delta.
- [Wizards' Through the Omenpaths release FAQ](https://magic.wizards.com/en/news/mtg-arena/through-the-omenpaths-release-faq) explains that a permanent's leave trigger arising while casting a spell is put on the stack after casting finishes and resolves before that spell. The same timing checkpoint matters for a life payment during casting or activation.
- Font of Agonies and Cruel Sadist Oracle text was checked against Scryfall's exact-name card API. No test card or ability was invented.

## Reproduction

`backend/tests/test_life_total_lock.py::test_font_of_agonies_triggers_after_cruel_sadist_life_payment` activates Cruel Sadist's real pay-1-life ability while controlling Font. Life falls from 20 to 19, but the stack contains only the Sadist ability; the expected Font trigger above it is absent. `pytest --runxfail` reproduces the failure; ordinary focused pytest reports one strict xfail.

The complete isolated backend suite passes 1,115 tests with exactly this 1 strict xfail. Frontend code was unchanged for this audit; its previously run lint/build/unit and Chromium gates remain green.

## Source boundary

- `backend/rules_engine/costs.py` subtracts life in activated and additional costs without recording a payment event. `backend/rules_engine/entry.py` does the same for supported pay-2-life land entry.
- `backend/rules_engine/engine.py` performs activated/additional payment before `add_to_stack`. `backend/rules_engine/stack_engine.py` appends the spell or ability and emits cast triggers immediately. Emitting a payment trigger directly from the cost helper would put it below the spell/ability and can mishandle ordering with other triggers created during the same cast or activation.
- `backend/rules_engine/events.py` does not recognize a `life_paid` event or infer a supported amount-based pay-life trigger. Existing gain/loss events cannot substitute: paying life is neither damage nor life loss from an effect.

## Repair gate

1. Record each successful positive life payment as its own amount-bearing event at the shared payment boundary; a prohibited or zero payment emits none. Avoid aggregating separate payments.
2. Defer triggers created during a cast/activation until that action completes, preserve APNAP and controller-selected ordering, then place them above the spell or ability. Apply the same timing to supported land-entry payment without exposing priority mid-entry.
3. Add a reusable trigger clause for supported amount-based pay-life wording, with Font's blood counters as the real-card fixture. Do not special-case its card name in payment logic.
4. Turn the strict xfail green and cover activated cost, additional cost, shock-land entry, multiple separate payments, life-total lock, snapshot restoration and an intervening response before the trigger resolves.

This boundary needs a cost-transaction and trigger-staging design review before an engine patch; a direct `emit_event` at each subtraction would be a misleading partial fix.
