# Conditional graveyard self-copy

The complete generic instruction compiles to a dedicated effect without a
card-name branch. Four graveyard card types are required at announcement, and
permanent targets come from the original activating controller's own graveyard.

Resolution retains source and target incarnation references, allows a source
control change, and does nothing when either object has left and returned.
Becoming a copy does not emit an artificial entry event. Mana payment,
responses, prohibitions and atomic rejection retain their normal paths.

The characteristic record retains the current base, ordered copy effects,
validated current cache and copy-owned printed backups. Untouched legacy
records remain compatible. Unknown old copy/form history and missing old
copiable metadata are not reconstructed or invented. Active extended copies
remain unknown to the conservative inventory.

Temporary copies expire at cleanup without discarding later underlying form
changes or unrelated counters. The test scenarios cover later copy effects,
bestow, cold restore, malformed records, real responses and copied-creature
combat. Explicit form/permanent-copy controls do not claim causal spell
execution.

Automatic payment prefers an alternative free payment that preserves a nonmana
activation's source when the resource comparison rates it at least as useful.
It retains the original plan when the source is necessary or the alternative
rates lower. This preference does not add a card-name scoring branch.

The [source-characteristic notes](graveyard-source-inventory-20261110.md) and
[Battle copying requirements](battle-copy-native-gap-20261110.md) describe
related boundaries. The [evidence input-boundary correction](native-profile-input-boundary-20261110.md)
records a historical tooling incident separately from gameplay behavior.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_conditional_graveyard_self_copy.py tests/test_creature_entry_copy_remaining4_fb775.py tests/test_self_creature_change_fb775.py
```
