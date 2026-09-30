# Aftermath Casting and Stack Departure

[Wizards' Amonkhet release notes](https://magic.wizards.com/en/news/feature/amonkhet-release-notes-2017-04-14) define Aftermath as permission to cast that half from the graveyard, a prohibition on casting it from any other zone, and an exile replacement whenever a spell cast from the graveyard leaves the stack. Its ordinary timing and costs still apply.

The engine exposes the Aftermath half as a graveyard legal move with its printed cost. It uses the shared selected-face, target, mana, AI materialization and human action paths. A cast records its graveyard origin in the stack payload so snapshot restoration and suspended choices retain the exile requirement.

Shared spell-departure handling applies the exile requirement before restoring the physical card's combined identity. Resolution, countering and failure of all targets use the same operation. An explicit move toward hand or library is also replaced with exile by this operation; general Oracle handlers that return spells to hand or put them into a library remain separate outstanding work. Copies never move the physical original. Ordinary countered split halves return to the graveyard with combined characteristics.

Canonical Scryfall fixtures cover Spring // Mind and Refuse // Cooperate. Commit // Memory provides a sorcery-timing check; this does not certify Memory's shuffle effect. Regressions cover:

- Graveyard permission, printed costs, instant/sorcery timing, and rejected hand/exile casts.
- Unpayable costs rejected without state mutation.
- Draw-two resolution, countering, all-illegal targets, and owner-correct exile.
- Stack snapshots and resumed draw/dredge choices before physical departure.
- A copy resolving while its physical original remains on the stack.
- AI action materialization, Control decisions using an available draw half with an empty hand in its main phase or the opponent's end step, and a human browser control casting Mind from the graveyard.

Aftermath is no longer classified as a missing mechanic by deck preflight. An empty known-gap report still does not certify every Oracle clause. Other Aftermath card effects, external graveyard permissions and their interactions require additional fixtures; Fuse remains unsupported.
