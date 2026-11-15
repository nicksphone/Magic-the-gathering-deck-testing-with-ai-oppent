# Battle entry and protectors

Defense uses the counter preparation and commit pipeline, including replacement
choices and counter-placement prohibitions. Entry preparation binds the object
reference, owner, prospective controller, printed defense and intrinsic ability
presence. A paused entry cannot silently rebind to changed characteristics.

Protector assignment occurs before enter-the-battlefield triggers are published.
State-based actions repair an invalid protector after relevant type or control
changes. Token construction propagates printed defense, and generic topdeck
permanent entry includes Battles.

The test scenarios cover ordinary casting, doubling and halving replacements,
ordered choices with restore, Solemnity's type scope, prospective creature
ability loss, entry copies, token copies, batch and immediate returns, protector
repair and stale entry data. Direct packets and mixed-type positions are
explicit test controls.

See [mixed-type and known-absence semantics](battle-mixed-entry-native-20261110.md)
and [counter/defeat handling](battle-defeat-native-20261110.md).

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_battle_entry.py
```

## References

- [current official PDF](https://media.wizards.com/2026/downloads/MagicCompRules%2020261106.pdf)
