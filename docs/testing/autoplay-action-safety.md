# Checked Live Autoplay Actions

## Contract

Live autoplay normalizes AI intents into the existing typed action contract and
then uses the same copy-on-write `checked_action` boundary as human submissions.
Legal-move presentation hints are not engine parameters. Chosen targets, costs,
ordered selections, source zones and card faces survive normalization; it does
not infer missing choices or convert a malformed action into a priority pass.

Rejected AI decisions return HTTP 422 with `illegal_ai_action`, acting seat and
action type. The coordinated endpoint rolls back the whole request, including
earlier ticks, RNG, costs, logs, continuation state, revision, retry receipts and
database writes. The frontend's existing error path pauses autoplay rather than
repeatedly retrying an invalid decision. A rejection is a diagnostic to fix, not
a draw, concession or successful turn.

The existing own-main land-development policy is retained. Its color preference
may fall back to an already offered land when the preference is malformed; it
cannot invent a card ID, source zone or extra land drop. The selected land still
passes typed and engine validation.

The heuristic trajectory teacher uses the same intent conversion before the
training adapter validates and executes the action. This prevents presentation
hints from rejecting otherwise valid casts. Exports remain heuristic, not expert
supervision; incomplete supported-choice coverage is still explicit.

## Validation Scope

Fixtures exercise both seats, malformed action shapes, unknown actions, stale
card references, illegal targets before mana payment, incomplete choices, later-
tick rejection, whole-state/database preservation and idempotent accepted casts.
Existing land-development, combat-window, input, recovery, fixed-mana and training
gates are included in qualification. Controlled canonical Bolt positions exercise
actual heuristic cast export and the immutable shard writer/validator.

Four seeded Strong AI games use the existing canonical built-in decks: Burn
versus Mono Red Aggro and Tempo versus Dimir Control, with each pair's seats
reversed. Completion checks action acceptance, not optimal play or matchup balance.
The test limit is 1,200 ticks per game; a timeout is a failure, not a winner.

The final composed gate passed 259 tests across nine modules, including all four
seeded match smoke cases. Frontend lint and production build also passed in the
isolated checkout. Evidence is archived on RCHFiles under
`autoplay-action-safety/parent-20261005/`. This is not a full-suite or post-change
whole-browser qualification; the ten-case Cathar run used the preceding source.

## Known Limitations and Next Upgrades

- This contract covers the live API autoplay endpoint and trajectory teacher.
  Legacy analytics/replay loops still need explicit shared-boundary parity;
  passing these tests does not certify all simulation entry points.
- Rules legality is bounded by implemented semantics. Typed actions and accepted
  games do not certify arbitrary Oracle text or seasoned-player decisions.
- Copy-on-write adds validation work. Combat search latency remains a separate
  measured optimization task; increasing a request deadline is not that fix.
- Interactive match-start unsupported-mechanic warnings remain outstanding.
