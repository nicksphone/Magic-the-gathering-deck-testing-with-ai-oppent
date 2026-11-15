# AI simultaneous payment ordering

A forecast must not certify survival merely because payment abilities have not
yet reached the stack. An unresolved simultaneous-trigger order or replacement
choice remains uncertain.

The unresolved-choice check precedes the absence-of-payment check. An
established winner is considered first. This does not add automatic ordering,
change payment authority, or change AI scoring and search depth.

The regression scenarios compare funded obligations with obligations that cannot
all be paid after ordering. They retain caller-state and RNG preservation checks.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_ai_ordered_payment_forecast.py tests/test_ai_deferred_payments.py
```
