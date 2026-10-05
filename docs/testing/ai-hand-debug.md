# Read-Only AI Hand Debugging

## Contract

Set `MTG_DEBUG_HANDS=1` when starting the local backend, then enable **Reveal AI
hands (debug)** above the battlefield. The flag must be exactly `1`; absent or
other values return 403 from `GET /matches/{id}/debug/ai-hands`.

The endpoint holds the existing match read lock and returns AI seats' card views,
match revision, game number and turn. It does not mutate state, expose human
hands/library order, modify ordinary hidden-hand responses, or supply extra
information to the AI. The UI ignores cancelled/stale requests and hides data
from other matches or games. Disable this flag outside trusted local debugging.

## Executed Evidence

- Eight isolated API tests cover server opt-in, either/both/no AI seats, snapshot
  immutability and unchanged normal redaction. Together with six canonical Cathar
  HTTP cases, the focused run passed all 14 checks.
- Frontend response-contract tests validate identifiers, revision, AI seat keys
  and card views. Frontend tests, lint and production build passed.
- `browser-ai-hand-debug.mjs` inspected an explicitly completed live match through
  the real LAN UI. Default-off, reveal, mana costs/card details and hide passed;
  all writes were blocked and the match revision stayed unchanged.
- Completed-game controls distinguish paused AI between-game advancement from
  complete-series gameplay. Its composed browser follow-up is tracked separately.

Archived evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/debug-ai-hands/`.
The script requires an explicitly selected ended match; never use it to automate
actions in a user's active game.

## Historical Decision Finding

Game 3's saved state was advanced only through passes matching its actual log.
The first 754 lines matched exactly: turn 19, Player B precombat main, life 9,
five untapped Forests and two untapped Swamps. Storm the Festival was legal and
payable; Ugin needed eight mana and was not payable. The production policy with
the actual Master/Ramp-versus-Tokens configuration chose pass. The observed log
then passed both main phases and lost during the next attack.

This proves one missed affordable deployment, not that every earlier decision
was wrong or that casting it guaranteed survival. Game 2 did cast Storm; retained
logs do not establish its hand at every decision. A generic planner fix is being
qualified separately. No fabricated cards, hidden-library inspection or forced
matchup win rate is part of this debugging feature.
