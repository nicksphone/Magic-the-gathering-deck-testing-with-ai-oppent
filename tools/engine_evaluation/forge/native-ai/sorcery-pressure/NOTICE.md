# Provenance

Forge Team/Card-Forge contributors authored the native engine, AI, test helpers
and complete card programs. Upstream revision:
`61e9442c433711a82258daca3236f936a1d6f70e`,
<https://github.com/Card-Forge/forge>.
Retain [Forge's GPL v3 license](../../LICENSE) and the repository's
[third-party notices](../../../../../THIRD-PARTY-NOTICES.md).

The new test, declaration, runner and verifier are GPL-3.0-or-later, written
2026-11-06. They do not change any native production body or any older control.
The seven-class prefix is the parent's separately qualified composed artifact;
this family merely checks and uses its immutable bytes.

All files in `canonical/` are complete byte-identical native card programs:

| Snapshot | Path Relative To Pinned Native Tree |
| --- | --- |
| `lava_spike.txt` | `forge-gui/res/cardsfolder/l/lava_spike.txt` |
| `mountain.txt` | `forge-gui/res/cardsfolder/m/mountain.txt` |
| `runeclaw_bear.txt` | `forge-gui/res/cardsfolder/r/runeclaw_bear.txt` |

`canonical.sha256` pins the snapshots and the runner compares them with native
source before execution. Cards are born through native `AITest` /
`Card.fromPaperCard`, with no Oracle, ability, cost or AI-metadata substitutions.
The starting zones, life totals, tapped state and phase are deliberate test
poses, not filtered natural hands, a constructed full-game outcome or expert
annotations. Only selected native casts are paid and resolved; no artificial
cast or winner is used to make a test pass.
