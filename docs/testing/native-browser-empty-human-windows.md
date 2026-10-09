# Native Browser Empty Human Windows

Updated: 2026-10-09 UTC. Base: `0483ef0cce578d71cb177cb3c626f1d895b9555c`.
This repairs acceptance automation, not application gameplay or AI policy.

## Cause And Correction

The original native actor loops waited for AI actors but sent every human window
to their manual policy. In player-versus-AI matches, the App deliberately
auto-advances an empty human window when the public legal response supplies
`can_auto_pass: true`. Beginning that mutation clears the offered controls.
The old helper could therefore read a blocking select after it had disappeared.

Both native helpers now retain the existing AI path, then wait for an observed
native revision change only when the mode is `player_vs_ai` and the public flag
is exactly `true`. Human-versus-human, actionable, missing and nonboolean flags
remain manual. The helpers record the public actor, flag and before/after
revision. They do not substitute a pass action or retry an uncertain mutation.

The selected-value readback returns false for an absent select. A present select
must still contain exactly the requested values; an absent select cannot satisfy
even an empty selection. Unrelated errors and existing deadlines remain fatal.

App/backend production, native driver, episode order, decks, controller roles,
pacing, strategy and the original acceptance assertions are unchanged.

## Observed Evidence

- The lasting actual-source regression runs in `npm run test:unit`. Before the
  correction its 50 checks report eight mismatches: four empty-human actor gates
  and four missing-select reads. Afterward all 50 checks pass. These are
  extracted-source protocol controls, not browser games.
- The complete configured `npm test` chain passes with the new regression
  included, using the existing pinned Python runtime and a native startup hook
  denying both SQLite aliases, sockets and child processes inside Python
  fixtures. Four native denial controls pass; the pre-existing parent database
  hash is unchanged. The first missing-interpreter and custom-wrapper invocation
  setup failures are preserved separately, not counted as application failures.
- `npm run lint`, `tsc -b --noEmit` and the AST-only `graphify update .` finish
  with exit zero. No dependency installation or application production change
  is part of this increment.
- The separate controlled built-App boundary run on the base plus exact helper
  postimages passes four cases in 16.675s: both seats, empty and actionable
  blocking windows. Empty windows make a real autoplay request with revision 0
  and observe HTTP 200/revision 1. Actionable windows retain revision 0 with no
  autoplay for 600ms, then deliberately select a blocker and submit the exact
  typed block action, observing HTTP 200/revision 1.
- Boundary runtime/source equality and native process, port, database-handle
  closure were verified. Its SQL lease was released at
  `2026-10-09T03:09:46.428917Z`.

The boundary run manually exercises the App, not the corrected actor loop.
Natural runtime evidence for that loop still requires the original complete
50-episode/94-assertion acceptance run, including both human seats and BO3.

## Preserved Histories And Limits

The original full run completed 49 declared episodes and failed during the
human-seat-2 AI episode. It is not a full pass. Its lost-select trace does not
establish a CDP interception failure or the final uncertain request's outcome.

Failed NEW boundary setup, fixture and navigation attempts remain archived
separately. Their corrections do not weaken the driver or original cohort.
The final NEW fixture navigates once from a blank page after registering saved
match storage; it does not suppress invalid interception IDs. No boundary-only
server, native policy or fixture setup is included in this parent increment.

Evidence root: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`.
Frozen boundary: `parent-integration/browser-boundary4-0483-qualified-m6MYmw-20261009/`.
Original failure: `parent-integration/browser50-a53-terminal-failure-20261009-ycNo7v/`.
Parent regression/checks: `parent-integration/native-browser-empty-window-integration-20261009/`.

This does not certify full browser acceptance, competitive AI, arbitrary cards,
LAN deployment, clean-machine operation or overall release completion.
