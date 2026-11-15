# AI deferred-payment forecasting

`backend/ai/deferred_payment_policy.py` forecasts from the actor's masked
decision view. It applies actions to planning copies, follows priority passes,
cleanup and untap, and uses the existing effect-payment choices. It does not
assign outcomes, force phases or replenish mana.

The policy distinguishes safe, losing and uncertain continuations. It filters
known losing new commitments and resource use that destroys a proved existing
payment. It can select a checked financing action when unanswered passes lose
and that action proves survival. Target hints allow Stifle to counter the
actor's own payment trigger. Heuristic and learned proposals share the policy.

Own submitted deck metadata provides only an upper bound on possible
acquisitions. Visible owned copies are subtracted without reading hidden
instances or their order. A basic land drawn during a waiting upkeep payment
cannot be played before that payment. Unknown acquisitions, rejected
continuations and exhausted forecasts retain uncertainty.

Forecast passes mutate an owned planning copy using `validate_action` and
`take_action`. Declaration passes and candidate actions retain
`checked_action`, including attack and block checks.

The regression scenarios cover funded and unfunded obligations, tapped sources,
floating and restricted mana, cumulative debts, financing actions, Stifle,
temporary resource control, copied obligations, loss prevention, a winning stack,
hidden-order invariance and learned proposals. Controlled positions do not
establish natural-game strength or support for every financing or copy family.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_ai_deferred_payments.py tests/test_ai_ordered_payment_forecast.py
```

## References

- [GitHub roadmap issue2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
