# Split Card Casting Boundary

[Wizards' split-card release notes](https://magic.wizards.com/en/news/feature/modern-horizons-2-release-notes-2021-06-04) distinguish the chosen half's stack characteristics from the combined card outside the stack. This implementation uses Scryfall-backed Fire // Ice and Incubation // Incongruity fixtures for the bounded behavior below; it does not certify every split-card effect.

## Supported

- A `layout=split` card offers one legal cast move per affordable half. Each half has its own timing, cost, targets, Oracle text and name on the stack. The half not chosen cannot supply cast effects or target requirements.
- Combined card types and mana cost remain available outside the stack. After a half resolves, the physical card returns to its combined identity in the graveyard. Snapshot restore retains the chosen stack half.
- Fire's printed "one or two targets" divided-damage wording exposes players, creatures and planeswalkers and rejects more than two recipients. Ice taps its legal target and draws a card. Human controls select either half; AI action materialization carries the selected face. Battle damage recipients remain outside this bounded test.
- A cached card with face data but missing layout is refreshed once from verified local Scryfall bulk data when available, with a remote sync fallback. An intact cache is reused.
- [Aftermath halves](aftermath-boundary.md) have graveyard-only casting permission at their printed cost and are exiled when they leave the stack. Countered ordinary halves restore the combined card in the graveyard.
- Split cards retain combined colors outside the stack and use only the chosen half's colors while cast. Absent Scryfall face-color metadata remains distinct from explicit colorless metadata, so a half can derive colors from its own mana cost. Legacy split rows with erroneous empty face colors are refreshed from canonical data. A protection fixture confirms Ice is blue rather than red/blue and can tap Master of Waves.

## Not Yet Supported

- Fuse (casting both halves as one spell) and its combined cost/target interactions. Deck preflight marks Fuse as known unsupported using canonical Toil // Trouble face text.
- Other split-card Oracle clauses and unusual permissions are not certified. A successful face choice does not imply the full effect of that half is implemented.

`backend/tests/test_split_card_casts.py` covers legal moves, costs, mixed timing, target cap, stack/snapshot/zone identity, offline cache backfill, AI action materialization and unsupported-mechanic warnings. The isolated Chromium harness casts both Fire and Ice through human controls.
