# Native Additional-Cost Follow-Up Notices

The native engine, AI, controllers, mana/cost implementation, ComboPlan and test
helpers are Forge Team/Card-Forge work:
https://github.com/Card-Forge/forge, revision
`61e9442c433711a82258daca3236f936a1d6f70e`.
Retain original source notices, [Forge's GPL v3 license](../../LICENSE), and the
repository [third-party notices](../../../../../THIRD-PARTY-NOTICES.md).
These original tests and the offline launcher are GPL-3.0-or-later.

The seven `canonical/` files contain complete, byte-identical native card programs
with full native Oracle fields from the pinned tree:

| File | Native Path Relative To Forge |
| --- | --- |
| `craw_wurm.txt` | `forge-gui/res/cardsfolder/c/craw_wurm.txt` |
| `jace_beleren.txt` | `forge-gui/res/cardsfolder/j/jace_beleren.txt` |
| `skirge_familiar.txt` | `forge-gui/res/cardsfolder/s/skirge_familiar.txt` |
| `swamp.txt` | `forge-gui/res/cardsfolder/s/swamp.txt` |
| `darkness.txt` | `forge-gui/res/cardsfolder/d/darkness.txt` |
| `tendrils_of_agony.txt` | `forge-gui/res/cardsfolder/t/tendrils_of_agony.txt` |
| `forest.txt` | `forge-gui/res/cardsfolder/f/forest.txt` |

All seven are compared to native sources before offline execution. Actual native
cards are created by AITest/Card.fromPaperCard; no substitute Oracle, cost,
keyword, source script or rule is installed. Printed starting loyalty, tapped
source state and native reveal callbacks are explicitly controlled poses, not
natural game histories or strategy labels.

Only new files in this folder are authored. No production, previous test/patch,
profile, native-match or other documentation is edited. Current parent final
shadow ff89fd32 is only read. This is not app/save qualification or full fairness.
