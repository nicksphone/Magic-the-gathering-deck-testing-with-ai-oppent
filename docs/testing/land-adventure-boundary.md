# Land Faces and Adventure Permissions

This milestone extends the canonical face model without treating every two-face layout as the same mechanic. [Wizards' Adventure release notes](https://magic.wizards.com/en/news/feature/throne-eldraine-release-notes-2019-09-20) distinguish a resolving Adventure from one that is countered or fails for illegal targets. [Wizards' modal-face notes](https://magic.wizards.com/en/news/feature/zendikar-rising-release-notes-2020-09-10) describe choosing a face to play or cast. The implementation covers the bounded cases tested below; it is not general rules certification.

## Implemented Boundary

- Modal land faces are separate `play_land` actions with the normal main-phase, stack-empty and land-count constraints. They consume no mana and do not use the stack. The selected face's name, type, text and mana identity persist on the battlefield and in snapshots. Unconditional "enters tapped" wording is applied at entry.
- Adventure spell faces use their own timing, costs and target surfaces. A successfully resolving Adventure enters exile and grants its caster a snapshot-persistent permission to cast only the normal face while it remains there. Countering it or making its single announced target illegal sends it to the graveyard without that permission. Casting from exile consumes the permission. Ownership and controller are kept distinct, including when a caster uses a card owned by the other player.
- Ordinary spell casts retain announced target choices for a single-target legality recheck just before resolution. If that target is illegal, the spell does not execute its effect. Divided damage and simple separate-clause targets have bounded paths; compound multi-target and replacement-sensitive rechecks remain separate work.
- Simple clause-derived effect sequences recheck separate announced targets at resolution. For the canonical Meager Meal Adventure, all illegal targets send the spell to the graveyard without permission; one legal target resolves only its own effect and exiles the spell with permission. Its "up to one target creature" clause may be omitted without choosing a creature automatically. This is not coverage for a compound effect that uses two targets in one clause.
- A copy of that separate-clause Adventure offers independent retarget choices for its announced creature and player targets. The original spell keeps its announcements; the copy's effects resolve on the stack without granting a reusable exile permission. Copies whose targets become illegal resolve only their legal clauses. Wizards' release notes say an Adventure copy is exiled as it resolves and then ceases to exist as a state-based action; the engine currently models that outcome by not creating a persistent copy card in exile.
- Human UI shows legal land-face buttons alongside spell-face controls; Adventure exile plays use the existing non-hand card controls. The AI retains selected face identities and land color scoring reads the selected land face.

## Checks

`backend/tests/test_land_and_adventure_faces.py` uses read-only canonical fixtures for Bala Ged Recovery / Bala Ged Sanctuary, Riverglide Pathway / Lavaglide Pathway, Bonecrusher Giant / Stomp and Brazen Borrower / Petty Theft. It covers tapped entry, both Pathway colors, land-count enforcement, temporary-exile permission, Adventure success/counter/missing-target paths, delayed casting after snapshot, permission consumption, caster-versus-owner rights, flash timing and AI action materialization. The fixture file is not imported into the gameplay cache.

`backend/tests/test_multi_target_adventure.py` uses a minimal fixture extracted from the local Scryfall-backed Oracle cache (`oracle_id` `0296d57e-e5b9-456f-bb21-eb584adefb4c`). It verifies Meager Meal's two effects, target loss and player hexproof after casting, optional target omission, zones/permissions and snapshot continuation.

The same fixture also tests copying Meager Meal, choosing new targets for both clauses across a snapshot, independent original/copy resolution, partial resolution after a target leaves, and an opponent controlling the copy without taking the original's exile permission. A focused AI decision test chooses friendly recipients for both beneficial clauses. The Chromium fixture exercises the two human choices through the API.

`frontend/tests/browser-human-actions.mjs` exercises the production Battlefield/Controls components and the isolated production API action route. It now includes Meager Meal's separate player and creature selectors and verifies both announced targets and resolved effects. The browser fixture server is loopback-only and refuses to run from the live checkout; see [harness setup](human-actions-browser.md).

## Still Open

- Conditional and optional tapped-land entry, replacement ordering, other land-face permission combinations and broad modal-face coverage.
- Compound multi-target effects and copies, target changes during replacement choices, split/fuse/aftermath semantics, explicit copy-zone presentation and long-session exile identity edge cases.
- Full Oracle semantics for the canonical fixture cards, tactical AI decisions about when to preserve a spell face rather than play its land face, and full-game/BO3 browser acceptance.
