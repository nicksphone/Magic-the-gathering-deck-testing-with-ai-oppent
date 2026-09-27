# Land Faces and Adventure Permissions

This milestone extends the canonical face model without treating every two-face layout as the same mechanic. [Wizards' Adventure release notes](https://magic.wizards.com/en/news/feature/throne-eldraine-release-notes-2019-09-20) distinguish a resolving Adventure from one that is countered or fails for illegal targets. [Wizards' modal-face notes](https://magic.wizards.com/en/news/feature/zendikar-rising-release-notes-2020-09-10) describe choosing a face to play or cast. The implementation covers the bounded cases tested below; it is not general rules certification.

## Implemented Boundary

- Modal land faces are separate `play_land` actions with the normal main-phase, stack-empty and land-count constraints. They consume no mana and do not use the stack. The selected face's name, type, text and mana identity persist on the battlefield and in snapshots. Unconditional "enters tapped" wording is applied at entry.
- Adventure spell faces use their own timing, costs and target surfaces. A successfully resolving Adventure enters exile and grants its caster a snapshot-persistent permission to cast only the normal face while it remains there. Countering it or making its single announced target illegal sends it to the graveyard without that permission. Casting from exile consumes the permission. Ownership and controller are kept distinct, including when a caster uses a card owned by the other player.
- Ordinary spell casts now retain announced target choices for a single-target legality recheck just before resolution. If that target is illegal, the spell does not execute its effect. Multi-target, divided and replacement-sensitive rechecks remain separate work.
- Human UI shows legal land-face buttons alongside spell-face controls; Adventure exile plays use the existing non-hand card controls. The AI retains selected face identities and land color scoring reads the selected land face.

## Checks

`backend/tests/test_land_and_adventure_faces.py` uses read-only canonical fixtures for Bala Ged Recovery / Bala Ged Sanctuary, Riverglide Pathway / Lavaglide Pathway, Bonecrusher Giant / Stomp and Brazen Borrower / Petty Theft. It covers tapped entry, both Pathway colors, land-count enforcement, temporary-exile permission, Adventure success/counter/missing-target paths, delayed casting after snapshot, permission consumption, caster-versus-owner rights, flash timing and AI action materialization. The fixture file is not imported into the gameplay cache.

`frontend/tests/browser-human-actions.mjs` exercises the production Battlefield/Controls components and the isolated production API action route. Its land-face and Adventure scenarios follow the earlier eight action paths. The browser fixture server is loopback-only and refuses to run from the live checkout; see [harness setup](human-actions-browser.md).

## Still Open

- Conditional and optional tapped-land entry, replacement ordering, other land-face permission combinations and broad modal-face coverage.
- Multiple target legality, target changes during replacement choices, split/fuse/aftermath semantics, copies of Adventure spells and long-session exile identity edge cases.
- Full Oracle semantics for the canonical fixture cards, tactical AI decisions about when to preserve a spell face rather than play its land face, and full-game/BO3 browser acceptance.
