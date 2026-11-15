# Attribution And License

Forge rules, card programs and Default AI are the work of the Forge Team and
Card-Forge contributors: https://github.com/Card-Forge/forge, pinned revision
`61e9442c433711a82258daca3236f936a1d6f70e`. ComputerUtil retains its complete
`Copyright (C) 2011 Forge Team` and GPL-3.0-or-later header. See [LICENSE](LICENSE).
This is a small derivative correction, not an independently authored engine.

The exact preimage also includes the previously qualified identity/known-mana
changes. It comes from combined parent `0c04d1b1`, not pristine upstream; those
prior corrections and their attribution remain unchanged. The incremental patch
adds only the generic activation-restriction gate in `hasAFogEffect`. Full source
before/after is supplied in `preimage/ComputerUtil.java` and
`source/ComputerUtil.java`, with hash lists and a zero-fuzz builder.

The eight complete canonical card programs retain Forge's original program
contents; no Oracle, ability or card-name behavior was rewritten. New controlled
fixtures/build tools are original GPL-3.0-or-later integration work. They are not
natural-game transcripts or expert policy labels. Generated actor/RNG evidence
remains private and is not distributed as a repository fixture.
