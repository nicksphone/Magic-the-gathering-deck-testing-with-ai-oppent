# Split Card Casting Boundary

[Wizards' split-card release notes](https://magic.wizards.com/en/news/feature/modern-horizons-2-release-notes-2021-06-04) distinguish the chosen half's stack characteristics from the combined card outside the stack. This implementation uses Scryfall-backed Fire // Ice and Incubation // Incongruity fixtures for the bounded behavior below; it does not certify every split-card effect.

## Supported

- A `layout=split` card offers one legal cast move per affordable half. Each half has its own timing, cost, targets, Oracle text and name on the stack. The half not chosen cannot supply cast effects or target requirements.
- Combined card types and mana cost remain available outside the stack. After a half resolves, the physical card returns to its combined identity in the graveyard. Snapshot restore retains the chosen stack half.
- Fire's printed "one or two targets" divided-damage wording exposes players, creatures and planeswalkers and rejects more than two recipients. Ice taps its legal target and draws a card. Human controls select either half; AI action materialization carries the selected face. Battle damage recipients remain outside this bounded test.
- A cached card with face data but missing layout is refreshed once from verified local Scryfall bulk data when available, with a remote sync fallback. An intact cache is reused.

## Not Yet Supported

- Fuse (casting both halves as one spell), Aftermath graveyard casting/exile, and their cost/target/zone interactions. An Aftermath half is correctly unavailable from hand or exile; graveyard casting is still absent. Deck preflight marks both mechanics as known unsupported using canonical Toil // Trouble and Commit // Memory face text.
- Other split-card Oracle clauses and unusual permissions are not certified. A successful face choice does not imply the full effect of that half is implemented.

`backend/tests/test_split_card_casts.py` covers legal moves, costs, mixed timing, target cap, stack/snapshot/zone identity, offline cache backfill, AI action materialization and unsupported-mechanic warnings. The isolated Chromium harness casts both Fire and Ice through human controls.
