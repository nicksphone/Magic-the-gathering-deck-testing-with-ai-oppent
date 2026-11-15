# Deferred upkeep payments

Summoner's Pact creates its fixed-mana payment obligation when it resolves,
after the immediate search finishes. The delayed ability goes onto the stack at
its controller's next upkeep and can be countered.

Pay and decline use native mana payment and the existing loss handler,
including loss prohibitions. The obligation and paused choice survive snapshot
restoration. Copies use their own controller, and exiling the source does not
cancel an existing obligation.

The compiler supports decimal and W/U/B/R/G/C mana tokens in the complete
terminal pay-or-lose clause. X, hybrid, Phyrexian, incomplete and trailing
unknown payment clauses remain unsupported. The search route requires an exact
complete colored-creature search prefix.

The test scenarios cover search continuations, payment and decline, copies,
countering, restricted mana, spell tax, loss prevention, AI choices, public
projection and atomic invalid-choice rejection.

See [AI payment forecasting](AI-deferred-payment-20261110.md).

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_deferred_upkeep_payment.py
```
