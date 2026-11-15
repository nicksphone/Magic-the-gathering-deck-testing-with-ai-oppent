# Battle entry with mixed types and known-absent defense

A retained ordinary or non-Battle back-face descriptor whose defense is known
to be absent uses zero when the object gains Battle. Legacy Battle metadata
missing defense remains unknown and cannot be treated as known zero.

Numeric entry receipts use version 1. Known absence uses a nullable version-2
receipt bound to the retained characteristics, owner, controller, zone and exact
object reference. Snapshot restore and paused replacement choices reject forged
or stale receipts.

Battle/Land type-derived abilities distinguish printed land-ability loss from
true all-ability loss and restoration. Direct packets and declared type inputs
are test controls rather than paid card histories. The entry scenarios also
cover casting, entry copies, replacement and prohibition effects, batch returns,
tokens and protectors.

The known-absence rule follows rule 107.2; the land-ability and Battle-intrinsic
distinction follows rules 305.7 and 310.

See [Battle entry](battle-entry-native-20261110.md) and
[the model/copy foundation](battle-lifecycle-foundation-20261110.md).

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_battle_entry.py tests/test_battle_characteristics.py
```

## References

- [November6 official rules PDF](https://media.wizards.com/2026/downloads/MagicCompRules%2020261106.pdf)
