# Native Lethal-Timing Increment Notices

The Forge Team/Card-Forge contributors authored the native engine, AI, test
helpers and complete card programs. Pinned upstream revision:
`61e9442c433711a82258daca3236f936a1d6f70e`,
<https://github.com/Card-Forge/forge>.
Retain [Forge's GPL v3 license](../../LICENSE) and the repository's
[third-party notices](../../../../../THIRD-PARTY-NOTICES.md).

The incremental patch and new controls/build/reproduction scripts are
GPL-3.0-or-later, modified 2026-11-06. Only the private copied
`forge.ai.ability.DamageDealAi` production body changes. The upstream tree,
qualified runtime, prior ff89 shadow, original quality cohort and original
branch diagnostic remain unchanged. `upstream-preimage.sha256` pins the whole
original body; the builder requires zero-fuzz patch application and exactly
one emitted class. Original source attribution remains in that copied body.

Every file under `canonical/` is a complete, byte-identical upstream native
card program. `canonical.sha256` pins them. Native paths relative to upstream
are `forge-gui/res/cardsfolder/<first filename letter>/<filename>` except
`urzas_armor.txt`, whose first letter is also `u`. Tests use native database
birth (`AITest` / `Card.fromPaperCard`), without ability/Oracle/AI metadata
rewrites. Life totals, zones, libraries, phase and untapped lands are explicit
constructed positions, not naturally reached game histories or expert labels.

Natural case00 reproduction is separate: unchanged canonical imported decks,
seed, original compiled probe, Default AI and qualified PublicNameController,
no Monte Carlo, filtered hands, cheat shuffle or forced outcomes. This narrow
increment is not a claim of broad tactical correctness, all-cost fairness,
save compatibility, coupled profile qualification or application readiness.
