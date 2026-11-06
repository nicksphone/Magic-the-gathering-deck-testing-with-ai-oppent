# Native AI Candidate Notices

The Forge Team/Card-Forge contributors authored the original native game engine,
AI, controllers, native test helpers, and card programs:
https://github.com/Card-Forge/forge, revision
`61e9442c433711a82258daca3236f936a1d6f70e`.
The native source's original GPL header is retained in the compiled copy.
Retain [Forge's GPL v3 license](../LICENSE) and the repository's
[third-party notices](../../../../THIRD-PARTY-NOTICES.md).

The patch, new test controls, and build/qualification callers are separately
GPL-3.0-or-later. Modification date: 2026-11-06. The sole native source change is
the candidate-identity visibility gate inside
`forge.ai.ComputerUtil.hasAFogEffect`. Its local modified source also carries a
dated modification notice. No second native production body, caller API,
original helper, native card program, or qualified runtime directory is edited.

`ComputerUtil.preimage.sha256` pins the complete original Java source. The patch
must apply with zero fuzz to a new owned copy; the builder refuses any other
preimage and permits exactly one emitted production class:
`forge/ai/ComputerUtil.class`.

The three files in `canonical/` are complete byte-identical original native
card programs, including all native Oracle fields:

| Local File | Native Path Relative To The Pinned Forge Tree |
| --- | --- |
| `future_sight.txt` | `forge-gui/res/cardsfolder/f/future_sight.txt` |
| `telepathy.txt` | `forge-gui/res/cardsfolder/t/telepathy.txt` |
| `spore_frog.txt` | `forge-gui/res/cardsfolder/s/spore_frog.txt` |

The other five full card programs are retained unchanged in the preceding
[audit's canonical fixtures](../ai-boundary/NOTICE.md). The qualifier compares
all eight programs to native source before running. Real native cards are born
through upstream `AITest`/`Card.fromPaperCard`, not shortened substitute rules.
Board insertion, printed starting loyalty, tapped mana sources, concealed
permutations and chosen visibility-grant permanents are explicitly constructed
test poses, not natural game histories or expert play labels.

This candidate is not deployed, not a replacement qualified application build,
and not a claim of compatibility with existing native saves. The parent save
qualification remains against the unchanged current native runtime. Later
composition requires its own build identity and compatibility qualification.
