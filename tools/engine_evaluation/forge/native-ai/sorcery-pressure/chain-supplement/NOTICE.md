# Provenance

Forge Team/Card-Forge contributors authored the native engine, AI, helpers and
complete card programs, upstream
`61e9442c433711a82258daca3236f936a1d6f70e`,
<https://github.com/Card-Forge/forge>.
Retain [Forge's GPL v3 license](../../../LICENSE) and the repository's
[third-party notices](../../../../../../THIRD-PARTY-NOTICES.md).

This new test class, runner/verifier, declaration and notes are separately
GPL-3.0-or-later, written2026-11-06. Native production and the original frozen
eight-case source/classes remain unchanged. No shortened rules, custom AI
metadata, forced cast, winner or fabricated fixture result is used.

The three complete byte-identical native card snapshots are:

| Snapshot | Native Path Relative To Pinned Forge |
| --- | --- |
| `lava_spike.txt` | `forge-gui/res/cardsfolder/l/lava_spike.txt` |
| `mountain.txt` | `forge-gui/res/cardsfolder/m/mountain.txt` |
| `runeclaw_bear.txt` | `forge-gui/res/cardsfolder/r/runeclaw_bear.txt` |

Cards are born using native `AITest` / `Card.fromPaperCard`. Starting phase,
zones, life and eight canonical library Bears per player are declared test
poses, not a filtered natural hand, legal60-card game or expert play label.
The runner compares canonical bytes and verifies pinned native/source/class
origins. All copied upstream source used in private cause evidence retains
its original attribution; no such copy is compiled as a production override.
