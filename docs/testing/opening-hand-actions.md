# Opening-Hand Battlefield Actions

The engine now offers a durable action window after all players keep and before
the first turn. Players act in starting-player order and may use multiple
supported actions in their preferred order or finish without using them.
These are not casts: they spend no mana, use no spell stack, and do not consume
the turn's land allowance. The existing typed mechanic-choice controls serve
either human seat; the same authoritative queue serves AI and replay.

## Supported Boundary

Printed, unconditional single-paragraph permission to begin with the card on
the battlefield is recognized generically, using either its name or "this
card". No card-name exception is used. The canonical fixtures include Leyline
of Anticipation, Sanctity, Vitality and the Void. Normal battlefield entry
timestamps and events are emitted; any staged entry triggers wait until the
first upkeep priority window. This is not certification of every possible
pregame trigger interaction.

Conditional permissions, additional costs/counters, entry choices, reveal
actions and mulligan-time abilities are not implemented here. Gemstone Caverns
and Leyline of Transformation are explicit negative fixtures: they remain in
hand with a finish-only warning, rather than receiving an incorrect partial
entry. Unsupported-card identities are not disclosed in the public log.

AI currently chooses supported free entries by hand-retention ordering. This
does not evaluate harmful symmetric effects, optimal entry ordering or matchup
strategy and is not evidence of seasoned play.

## Evidence

- `backend/tests/fixtures/opening_hand.json` preserves real Scryfall named-card
  data fetched on 2026-09-30, including Scryfall and Oracle IDs. No fabricated
  card text is used. Hand/board fixtures and the dense sandbox HTTP deck are
  constructed test states, not legal competitive lists.
- Engine tests cover both starting seats, ordering, decline, unsupported
  clauses, AI archetypes and snapshot restoration.
- HTTP tests cover names-only cached hydration, action legality, rejection
  without memory/database mutation and restoration from SQLite.
- Chromium uses the real Controls component and production action endpoint
  for a second-seat entry, with stale mulligan controls suppressed.

Rules reference: [Comprehensive Rules](https://magic.wizards.com/en/rules),
section 103.6. Canonical examples: [Duskmourn release notes](https://magic.wizards.com/en/news/feature/duskmourn-house-of-horror-release-notes).
