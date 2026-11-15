# Noncolor creature target restrictions

The correction adds a reusable single-creature noncolor modifier to target
metadata and applies the state-aware color reader in the common predicate.
There are no Doom Blade name checks or printed-fact rewrites.

Unknown colors, unrelated text, card/spell domains and compound domains remain
outside the grammar. This change does not redefine mana payment, color layers
or AI policy.

The regression scenarios cover black and multicolored-black rejection,
colorless indestructible creatures as legal human targets, mixed-board hints,
materialization and payment, supported color conversion and a response that
restores black before the pending spell resolves. They check current and
restored state, caller state, RNG and offered moves.

Controlled board and mana setup is distinct from paid birth, natural games or
universal color-layer coverage.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_noncolor_targets.py
```

## References

- [official monitoring event categories](https://docs.python.org/3.12/library/sys.monitoring.html#events)
