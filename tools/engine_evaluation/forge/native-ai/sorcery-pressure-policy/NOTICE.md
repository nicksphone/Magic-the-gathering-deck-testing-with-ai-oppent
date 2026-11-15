# Native Forge Attribution And Fixture Provenance

The Forge Team/Card-Forge contributors authored the engine, native AI, test
helpers and original complete card programs:
<https://github.com/Card-Forge/forge>, revision
`61e9442c433711a82258daca3236f936a1d6f70e`.
Retain [Forge's GPL v3 license](../../LICENSE) and the repository's
[third-party notices](../../../../../THIRD-PARTY-NOTICES.md).

The copied DamageAiBase preimage is the qualified native source. DamageDealAi
is the current separately qualified lethal-timing source, not a relabelled old
body. Original attribution is retained in copied source; the two-source
fallback-pressure modification, new controls/build/test scripts and notes are
GPL-3.0-or-later, written2026-11-06. Parent seven-class bytes and every previous
test source/verifier remain unchanged. Only copies under this new directory
are edited; build output remains in a new private local root.

All files in canonical/ are full byte-identical native programs, including
every Oracle field, ability, subability, trigger and AI metadata. For each
filename the pinned native path is
`forge-gui/res/cardsfolder/<first filename letter>/<filename>`.
`canonical.sha256` pins all22 complete files; the test runner compares each to
the native source before execution. Cards are born via AITest/Card.fromPaperCard.
No shortened rules, name-specific production condition, fabricated target,
counter assignment, forced cast or forced winner is used. Libraries contain
eight canonical Runeclaw Bears per player in explicitly constructed positions.

The predecessor chain2 and lethal26 Java sources are compiled unchanged in the
private test output; their private check methods are invoked without changing
their assertions. The fixed original8/chain2 declarations and verifier files
are not rewritten for the candidate prefix. This is bounded native controlled
evidence, not a natural-game or application certificate.
