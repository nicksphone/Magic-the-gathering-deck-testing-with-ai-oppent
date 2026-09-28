# Life-payment trigger boundary (2026-09-28)

Status: bounded repair implemented. The real-card expected failure is now an ordinary regression; general pay-life wording and nested replacement timing are not certified.

## Rules evidence

- [Wizards' Magic Arena Sylvan Library developer diary](https://magic.wizards.com/en/news/mtg-arena/dev-diary-sylvan-library) explicitly discusses Font of Agonies triggering separately for separate life payments. The supported trigger must use the amount of each payment, not an end-of-action life-total delta.
- [Wizards' Through the Omenpaths release FAQ](https://magic.wizards.com/en/news/mtg-arena/through-the-omenpaths-release-faq) explains that a permanent's leave trigger arising while casting a spell is put on the stack after casting finishes and resolves before that spell. The same timing checkpoint matters for a life payment during casting or activation.
- Font of Agonies and Cruel Sadist Oracle text was checked against Scryfall's exact-name card API. No test card or ability was invented.

## Reproduction

Before the repair, `backend/tests/test_life_total_lock.py::test_font_of_agonies_triggers_after_cruel_sadist_life_payment` activated Cruel Sadist's real pay-1-life ability while controlling Font. Life fell from 20 to 19, but the stack contained only the Sadist ability. The strict expected failure preserved that reproduction.

That historical audit ran 1,115 passing tests and one strict xfail in an isolated backend copy. Later verification belongs to the repair, not the original audit.

## Source boundary

- `backend/rules_engine/costs.py` and `backend/rules_engine/entry.py` formerly subtracted life without recording a payment event. They now use a shared positive-payment operation that emits an amount-bearing event; zero and prohibited payments do not emit one.
- `backend/rules_engine/engine.py` now stages payment triggers until a played land enters or a cast/activation reaches the stack. This keeps the trigger above the spell or ability and uses the existing APNAP and controller-ordering machinery.
- `backend/rules_engine/events.py` recognizes `life_paid` and amount-based "put that many ... counters on this ..." wording. Existing gain/loss events are not substituted: paying life is neither damage nor life loss from an effect.

## Verified repair boundary

1. Record each successful positive life payment as its own amount-bearing event at the shared payment boundary; a prohibited or zero payment emits none. Avoid aggregating separate payments.
2. Defer triggers created during a cast/activation until that action completes, preserve APNAP and controller-selected ordering, then place them above the spell or ability. Apply the same timing to supported land-entry payment without exposing priority mid-entry.
3. Add a reusable trigger clause for supported amount-based pay-life wording, with Font's blood counters as the real-card fixture. Do not special-case its card name in payment logic.
4. Turn the strict xfail green and cover activated cost, additional cost, shock-land entry, multiple separate payments, life-total lock, snapshot restoration and an intervening response before the trigger resolves.

Focused tests now cover the listed payment paths, separate amounts, human trigger ordering, a snapshot, life-total lock and real Withering Boon target restrictions. Generic type-qualified counterspell recognition was repaired as part of that fixture. The full-suite result is recorded in the README and changelog.

A live FastAPI regression also checks that legal moves offer the creature spell as Withering Boon's target and that the action response reports the paid life and Font trigger above the spell. This covers public HTTP serialization, not a full browser or arbitrary-card counterspell matrix.

Effect-driven multi-land entries now stage payment and ETB triggers across the pre-entry choices, including a snapshot and one four-trigger human ordering fixture. Still open: alternate Oracle wording, competing replacement effects, nested replacement choices during resolution, and broader seeded replay coverage. Trigger staging does not by itself make multi-part cost payment atomic on every failure path.
