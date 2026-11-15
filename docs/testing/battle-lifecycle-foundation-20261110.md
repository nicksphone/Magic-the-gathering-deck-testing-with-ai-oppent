# Battle model and copy foundation

The model separates printed defense, live defense counters and protector
identity. Defense-aware copy history retains physical card faces and ordinary
version-1/version-2 compatibility. Snapshots reject missing or contradictory
version-3 metadata instead of guessing characteristics.

The bounded AI inventory accepts printed-defense and protector fields only at
their ordinary `None` defaults and keeps Battle metadata and version-3 history
unknown. Visible planning copies retain the fields; hidden-card replacements
keep them opaque.

Model and copy behavior are distinct from
[entry](battle-entry-native-20261110.md),
[counter/defeat handling](battle-defeat-native-20261110.md),
[transformed casting](battle-transformed-cast-native-20261110.md), combat,
and public consumer behavior.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_battle_characteristics.py tests/test_battle_metadata_consumers.py
```
