# Capacity-aware combat intents and projections

## Implemented

Declaration ordering follows restrictions/requirements before locked payment and
block commitment (CR 509.1b-g), checked against the
[official Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf).
The added Benalish Hero fixture is the actual Scryfall response with its Oracle
ID and source URI retained, not a fabricated card or competitive deck.

- Bounded blocker search enumerates direct attacker-to-blocker groups, including
  one creature blocking several attackers when its effective ability permits it.
  Shared evasion, minimum groups, declaration limits, maximum requirements and
  optional-payment affordability filter candidates before combat evaluation.
- A 4,096-visited-node budget aborts the entire search rather than calling a
  partially explored result optimal. The existing wide-board fallback now reuses
  blocker capacity and avoids redundant direct declarations across attacking bands.
- Every final AI block declaration is legalized, including ordinary untaxed boards.
  The rules operation exposes direct declarations separately from post-payment
  departures and band-expanded resolved blocks. Alone restrictions are checked
  before payment; a later sacrifice does not retroactively invalidate the group.
- Combat projections advance through actual combat steps. Explicit damage choices
  use the existing live public-board allocation policy; unknown noncombat choices
  remain unknown rather than being silently skipped. Unknown opponent block
  forecasts are not interpreted as passing.
- High-life face-damage chump pruning no longer discards planeswalker/battle
  defense merely because the defending player's life total is safe.

## Acceptance Checklist

- [x] Both-seat canonical multi-block, banding, alone, requirement and payment
  fixtures; independent pair-subset enumeration checked against actual legal actions.
- [x] Actual Strong/Master decisions resolve lethal multi-attacker defense;
  explicit damage allocation and planeswalker protection have separate regressions.
- [x] HTTP declarations and SQLite snapshot restoration preserve multi-block groups.
- [x] Final-source isolated backend suite: 3,104 passed (328 deprecation warnings),
  including all 44 intent tests and sacrifice ordering through the AI finalizer.
  Frontend lint/unit/build and complete Chromium flows passed, including natural
  human-vs-AI, human-vs-human and AI BO3 and both-seat multi-block cost controls.
- [x] Six pairings across four template decks, one seed per pairing in both
  seat orders: twelve logical games, each repeated twice, with zero timeouts,
  determinism failures, drift labels or reported anomalies. This small sample
  tests repeatability and stalls, not competitive balance.

Eighteen actual decisions per revision were recorded on identical canonical
boards across both seats and Strong/Master/Master+. All twelve lethal
multi-block/damage-choice cases changed from a defending loss to survival.
Six planeswalker cases retained three loyalty instead of one. Current decisions
all passed checked actions and completed combat projection. Full hands, boards,
actions and post-combat snapshots are retained with the runner and baseline
source, rather than inferring quality from match win rates.

Verified evidence, failed/superseded runs, raw card response, before/after
runner and source copies are archived on RCHFiles under
`diagnostics/combat-intents/20261003T010700Z/`. The final-source full suite and
matrix are distinguished from earlier passing runs in `VALIDATION.md`.

## Known Limitations and Next Upgrades

The small-board search is bounded to four attackers and five blockers; larger
boards use a heuristic, not an optimal policy. Multi-target fallback does not
guarantee globally optimal cumulative damage/resource trading. Opponent damage
allocation is forecast using the live policy, not adversarial minimax. Unknown
trigger/replacement choices and hidden-zone changes still limit projection.
Face-only chump pruning can miss death/damage payoffs. General conditional costs,
granted requirements, arbitrary layers and strategic multi-turn planning remain
unfinished. Passing these checks is not expert-level AI or balance certification.
