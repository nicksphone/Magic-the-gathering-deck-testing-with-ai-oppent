# Checked combat-response forecasting

## Implemented Scope

Master and Master-plus reuse the existing public-board, checked-action combat
forecast after blockers are declared, not just in precombat main. A candidate
spell or ability resolves through the same rules engine as live play, then the
declared combat resolves through effective stats, damage allocation and effects.
The planner uses current resources and instructions; it has no card-name special
case for a devotion pump or fixed pump.

Single-creature target alternatives preserve the materializer's controller
preference and are individually validated. A larger blocked creature no longer
automatically displaces an unblocked recipient with a winning line. Already
winning combat preserves the extra card. An unresolved choice, unrecognized
effect or hidden-zone change does not establish a proved outcome.

The bounded forecast remains conditional on unanswered play, not proof that an
opponent cannot respond. It currently runs with an empty stack, an active-player
action, at most sixteen candidate actions, three friendly creatures and two
opposing creatures. Defensive responses, larger-board search, first-strike
response windows and announced counter/removal branches are not completed here.
This is a reproducible decision improvement, not expert-AI or balance evidence.

## Acceptance Checklist

- [x] Reproduce thirty original-source failures with the corrected fixture.
- [x] Exercise fixed and live-devotion pumps in both seats and six archetypes.
- [x] Execute each selected winning line with checked payments and real damage.
- [x] Choose the smaller unblocked recipient over a larger blocked alternative.
- [x] Preserve authoritative snapshots while deciding; reload before decisions.
- [x] Decline a forced response when underfunded, nonlethal or undeclared.
- [x] Do not spend a pump when the declared attack already wins.
- [x] Reject certainty from draw/unknown-choice/unsupported-effect projections.
- [x] Verify HTTP autoplay commits the cast and restored games finish combat.
- [x] Record before/after decisions and checked outcomes for twenty-eight boards.
- [x] Finish fresh-cache backend suite.
- [x] Finish frontend lint, runtime boundary tests and production build.
- [x] Finish full Chromium and repeated seat-balanced archetype matrices.
- [x] Refresh Graphify, archive verified evidence and publish the milestone.

Forty-four new focused checks pass, including both HTTP seats; the earlier
five-module selection passes 239 checks before the final eight additions.
Twenty-eight actual Master decisions produce zero checked wins in the original
source and twenty-eight in the changed source. Traces include hand, available
mana, public attackers/blocks, the action/reason and final life/winner. These
constructed boards are not competitive decks or a win-percentage measurement.

The complete Chromium harness passes all current casting/choice/recovery tests
and natural AI, human-vs-AI and human-vs-human BO3 flows. Two independent corpus
selections each complete twelve seat-balanced BO1 samples, repeated twice per
sample: default expansion templates (412.761 seconds) and explicitly selected
Tempo/Dimir Control/Tokens/Ramp built-ins (424.643 seconds). Neither reports an
anomaly, timeout or determinism failure. The second selection uses an archived
evidence-only wrapper; the runner, production decks and live database are not
modified to select that corpus.

The final isolated backend suite passes all 5,405 tests with 543 deprecation
warnings in 985.12 seconds. Current backend source is byte-identical to the
full-suite, both matrix and retained browser checkouts. Live local API and
frontend health checks return HTTP 200; these are not a network-deployment or
visual-layout audit.

Failed development runs, canonical decision inputs, full source, browser
artifacts and final checks are preserved with verified archive checksums under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-combat-response/20261004T011956Z/`.
The preceding devotion milestone contains the consistent private live-database
backup. No SQLite database runs on NFS. Publication and cleanup receipts are
stored alongside the evidence; the user's untracked plan remains unstaged.

Development failures are retained: the first fixture funded mana before a step
transition, which correctly emptied it. Funding was moved into the response
window before rerunning the original-source baseline. An intermediate targeting
test insertion was repaired before the final acceptance and source capture.
No production card, deck, damage value or matchup result was invented or changed.

## Known Limitations and Next Upgrades

Remove unconditional defensive post-block passing through a separately tested
response policy. A checked both-seat probe still observes a blanket pass that
trades the defender's 2/2; a legal fixed pump kills the attacker and retains the
blocker. Whether spending that card is strategically best requires resource and
future-pressure valuation, not a blanket "always save the blocker" rule. Expand
bounded search to known counter/removal interactions,
first-strike windows, larger boards and more variable payoff families without
reading hidden cards or assuming unknown effects are harmless. Keep these open
until legal decisions, costs, effective outcomes, replay and recovery agree.
