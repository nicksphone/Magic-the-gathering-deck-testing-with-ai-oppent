# Battle copying and entry requirements

Printed defense is a copiable characteristic; live defense is represented by
counters on the battlefield. Copying an existing permanent does not create an
entry event or intrinsic entry counters. A zero-defense Siege without a relevant
outstanding triggered ability goes to its owner's graveyard.

Battle support also requires entry counters, protector assignment, counter
transitions, defeat handling, transformed casting, combat and consumer behavior.
A zero-counter check alone does not establish the complete lifecycle.

## Printing provenance

The Battle fixture is an unmodified Scryfall card object with both faces from
[the public source](https://github.com/daveycodez/sylvan-librarian-cloudflare/blob/0fe1f8979f8a70870459e72feeb64ab0dc7be7f9/engine/builder/src/fixtures/invasion_of_zendikar_mom_194.json).

The fixture identity is Git blob
`be7cd9340fa4bffe920a931db319a829459170df`, SHA-256
`1e49bb006e579e3a88052ab773f5974f761e4a8fedd6fda669768d92f2b82d74`.
[Repository provenance](../../backend/tests/fixtures/battle_full_printing/PROVENANCE.json)
records its source and face identities. A partial fixture is not a substitute
for the complete printing.

See the [model/copy foundation](battle-lifecycle-foundation-20261110.md),
[entry handling](battle-entry-native-20261110.md) and
[counter/defeat handling](battle-defeat-native-20261110.md).

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_battle_characteristics.py tests/test_battle_entry.py tests/test_battle_defeat.py
```

## References

- [2026-11-06 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020261106.txt)
- [March of the Machine release notes](https://magic.wizards.com/en/news/feature/march-of-the-machine-release-notes)
