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

The printed nonstarting-player permission with one named counter followed by
exiling a hand card is also recognized generically. Gemstone Caverns is the
canonical fixture. Its counter is assigned after new-object initialization and
before entry events. The follow-up exile selection is mandatory when cards
remain and survives restoration; it is an instruction, not an additional cost.
An otherwise empty hand therefore does not prevent entry. Normal land play
does not receive the opening counter.

Other conditional permissions, entry choices, reveal actions and mulligan-time
abilities are not implemented here. Leyline of Transformation remains an
explicit negative fixture with a finish-only warning. Unsupported-card
identities are not disclosed in the public log.

## Conditional Mana and Human Controls

A bounded printed tap ability replacing one fixed mana with any color when the
permanent has a named counter reads its current counters. Automatic payment,
manual validation/tapping, AI battlefield-source analysis and serialized views
share this output function. A luck counter changes Gemstone Caverns from
colorless to the five colors, not six interchangeable choices. Removing the
counter immediately restores the colorless output.

Land piles use authoritative color options and separate same-name lands with
different outputs and amounts. Bulk taps filter eligible sources by the chosen color
before counting. The summary labels alternative colors as shared-source
options, not independent mana. This is not a complete interpreter for land
abilities with activation costs, spending restrictions, dynamic quantities,
other conditions or tap-trigger side effects.

AI currently chooses supported free entries by hand-retention ordering. This
does not evaluate harmful symmetric effects, optimal entry ordering or matchup
strategy and is not evidence of seasoned play.
The mandatory exile heuristic chooses a low-retention hand card; entry versus
keeping the land has no deeper matchup or long-horizon search yet.

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
  for a second-seat entry, with stale mulligan controls suppressed, and covers
  conditional entry, mandatory exile and a colored land tap.

Latest verification (2026-09-30): 1,737 isolated backend tests, frontend
lint/build/unit contracts and the full Chromium harness pass. A six-series,
13-game seat-balanced BO3 smoke reports no timeout, anomaly or determinism
drift; its decklists do not exercise conditional opening entry, which is
covered by the canonical fixtures and HTTP/browser paths above. This is not
statistical balance or expert-AI evidence.

One diagnostics-enabled full run segfaulted while printing a timeout stack.
Two fresh uninstrumented full runs passed (1,736 before the extra cache case,
then 1,737 on the final source). The diagnostic crash's root cause is not
established. The live Control/Ramp regression still takes minutes; repeated
stack projections and long-decision responsiveness need investigation.

Rules reference: [Comprehensive Rules](https://magic.wizards.com/en/rules),
sections 103.6 and 609.3. Canonical examples:
[Duskmourn release notes](https://magic.wizards.com/en/news/feature/duskmourn-house-of-horror-release-notes)
and [Edge of Eternities release notes](https://media.wizards.com/2025/downloads/EOE_Release_Notes_R8Z03VaANE/EN_MTGEOE_ReleaseNotes_20250718.pdf).
