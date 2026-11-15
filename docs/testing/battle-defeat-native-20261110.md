# Battle counter removal, defeat and zero-defense handling

Gameplay counter removal is distinct from counters ceasing to exist on a zone
change. Source-counter costs, remove-all effects and resumable counter moves use
the shared removal path. A positive-to-zero defense transition collects defeat
only when the Siege intrinsic ability is present. Zone resets do not trigger it.

Counter moves preflight both objects and placement prohibitions, bind source and
recipient references and counts before a choice, and commit once after restore.
Direct effect, cost and type positions are test controls rather than claims of
paid card histories.

Triggers retain their source incarnation and zone-change sequence. Delayed
creators retain creation provenance; missing legacy provenance remains unknown.
A zero-defense Siege considers staged, cleanup-deferred, pending-order,
published, copied and resolving triggers. Activated, foreign, old-incarnation
and malformed frames do not hold it on the battlefield. Zero-defense non-Siege
Battles do not have that exception.

The state-based departure batch handles zero-defense Battles alongside lethal
creatures, including replacement and death events. Battle attachments become
unattached. Counter-cost snapshots retain their explicit zero slot; remove-all
clears empty real-counter slots and stale counter timestamps without removing
internal damage markers.

Siege self-entry wording is recognized by the shared matcher. Retained trigger
references are not restricted to graveyard triggers when search or shuffle
continuations use them.

[Transformed casting](battle-transformed-cast-native-20261110.md) is a separate
part of defeat resolution.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_battle_defeat.py tests/test_battle_combat.py
```

## References

- [November6 official rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020261106.pdf)
