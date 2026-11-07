# Native Forge Attribution

Forge Team/Card-Forge contributors authored the engine, AI, AITest helper and
the complete native card programs copied here from revision
`61e9442c433711a82258daca3236f936a1d6f70e` of <https://github.com/Card-Forge/forge>.
Retain [Forge's GPL v3 license](../../LICENSE) and the repository's
[third-party notices](../../../../../THIRD-PARTY-NOTICES.md).

The new diagnostic harness and runner are GPL-3.0-or-later. They adapt the
existing canonical controlled-position harness pattern, without modifying it.
All five files in canonical/ are full byte-identical upstream native programs,
including Oracle text, abilities, subabilities, triggers, costs and AI metadata.
`canonical.sha256` and the runner compare them before model initialization.
No natural private hand or RNG history is a test fixture. These are explicit
constructed positions, not full natural games or a reproduction claim.
