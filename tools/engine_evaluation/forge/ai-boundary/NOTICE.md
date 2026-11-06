# Attribution And Fixture Identity

The Forge Team/Card-Forge contributors authored the native game engine,
controllers, AI, native test helpers and card programs used here:
https://github.com/Card-Forge/forge, revision
`61e9442c433711a82258daca3236f936a1d6f70e`.

The original sidecar regression and launcher are GPL-3.0-or-later. Retain
the upstream notices, [Forge GPL license](../LICENSE), and repository
[third-party notices](../../../../THIRD-PARTY-NOTICES.md).

`canonical/` contains complete, byte-identical native card-program sources,
including their complete native Oracle fields, not shortened test definitions:

| Local File | Native Path Relative To Pinned Forge |
| --- | --- |
| `craw_wurm.txt` | `forge-gui/res/cardsfolder/c/craw_wurm.txt` |
| `jace_beleren.txt` | `forge-gui/res/cardsfolder/j/jace_beleren.txt` |
| `forest.txt` | `forge-gui/res/cardsfolder/f/forest.txt` |
| `fog.txt` | `forge-gui/res/cardsfolder/f/fog.txt` |
| `experimental_frenzy.txt` | `forge-gui/res/cardsfolder/e/experimental_frenzy.txt` |

The launcher compares every file to its native source before execution. Actual
cards are created by the native `Card.fromPaperCard` path via upstream `AITest`,
not by compiling substitute definitions. Only the constructed board, native
loyalty counters, visibility/memory controls and concealed permutation are test
setup. The Jace pose sets its printed three starting loyalty counters because
direct test-zone insertion does not execute its entry replacement.
