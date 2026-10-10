# Human BO3 Between-Games Readiness

Baseline: `710999231ee0b39f8e0498d584294c3629ee1120`.
The remote browser job `114185239397` passes recovery, sideboard swapping and
natural AI BO3, then stops at the human series transition. The UI correctly
requires each human seat to confirm its sideboard; the driver previously
clicked Next Game without those confirmations.

The driver now selects each unfinished human seat through the existing UI,
clicks Confirm No Swaps, waits for its committed revision and verifies applied
status. Only then does it use the current revision to wait for the next game.
Already-confirmed humans and AI seats are not reconfirmed. No application,
backend, original game assertion, timeout or step bound changes.

Four regressions execute the actual driver's between-games branch: human versus
AI, both human seats, one already confirmed and both already confirmed. An
intentionally stale first GET proves a sideboard revision cannot count as the
next-game receipt. On the old driver three cases fail and one passes; after the
correction all four pass. This is branch-sequencing evidence, not natural-game
or mounted-browser qualification.

The complete configured frontend tests, lint and build terminate successfully
on 2026-10-10 at 10:25:33 UTC. The original 41 test entrypoints remain an exact
prefix, with this regression appended as the 42nd. The frontend lock,
dependency definitions, App and Controls are unchanged before/after execution.
Evidence is archived with the publication under RCHFiles. The complete current
browser, protected backend CI, HTTPS and other release gates remain required.
