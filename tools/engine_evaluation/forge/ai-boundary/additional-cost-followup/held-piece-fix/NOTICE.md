# Known Held-Piece Increment Notices

Forge Team/Card-Forge authors the native engine, AI, cost and mana code, ComboPlan
and AITest helpers: https://github.com/Card-Forge/forge at
`61e9442c433711a82258daca3236f936a1d6f70e`.
Retain original notices, the [GPL v3 license](../../../LICENSE), and
[third-party notices](../../../../../../THIRD-PARTY-NOTICES.md).
This original narrow patch, scripts and added controls are GPL-3.0-or-later.
The patch applies to parent E/final source ff89fd32, retaining its previous fixes.
Only ComputerUtilMana.java changes; ComputerUtil.java and ComputerUtilCost.java
are rebuilt byte-identically to carry the complete four-class shadow bundle.
The per-card held-piece condition preserves ComboPlan.holdsKillPiece exactly,
using its public native semantic helpers, after the observer predicate admits
the card. No native helper, card program or rule is replaced.

Tests use the full native programs in the preceding canonical directory and
the existing immutable earlier canonical directories, with byte comparisons
before execution. See [the original provenance](../NOTICE.md). Generated hands,
decisions and RNG data remain private evidence, not repository fixtures.
