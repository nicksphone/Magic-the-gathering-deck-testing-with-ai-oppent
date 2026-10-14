# Autoplay fixture identity at birth

Source-only base: `77917d6c16125addede6858727fde3e51651fad9`.
The original `test_autoplay_seeded_games.py` created a real Factory state and then
overwrote `state.id` with an unrelated controller's ID. Factory capture had already
recorded its own `game_id`. Strict snapshot validation correctly rejects the mismatch.

The test-only correction passes `game_id=match.state.id` into the same Factory call
and removes only the subsequent ID assignment. Deck inputs, seed expression,
controllers, AI settings, tick bounds and both original assertion ASTs are unchanged.
No facts are cleared, patched, reinitialized or weakened; no production file changes.

## Bounded proof

A new whole five-case pure module uses actual canonical `_deck`, MatchFactory and
private serde. Four cases cover both original deck pairs and both orientations by
executing the original fixture function body up to a trusted controller-assignment
seam. That seam checks captured identity, actual snapshot roundtrip and stock/card
count equality, then stops before AI construction, persistence or HTTP. It is source
birth-stage projection, not the original HTTP test or a played episode.

Before correction: four identity failures, one deliberate-corruption rejection pass
in 6.79 seconds. After correction: all five pass in 6.99 seconds. Both runs preserved
source bytes; SQL, sockets, child creation, gameplay and chooser calls were denied
before source imports. Standard HTTP-client library definitions were allowed only as
existing engine import prerequisites; physical network denial stayed unchanged.
Two earlier collection-only harness failures (wrong pytest root, then an overly strict
HTTP-library import denial) remain separate records and are not product failures.

The original whole four-case HTTP/autoplay module has NOT been run under this scope.
No full-game RNG trajectory, AI-strength, hosted-CI or all-464-failure closure claim
is made. The corruption control still proves post-birth ID mutation rejects a private
snapshot. Future HTTP qualification requires its own reviewed finite contract.

## Subsequent whole-module physical qualification

On 2026-10-14, the parent ran both complete modules once against immutable
`77917d6c16125addede6858727fde3e51651fad9` plus these two test-only postimages.
Actual JUnit: **9 passed, zero failures/errors/skips**, 70 warnings, 206.30 seconds;
native pytest and the physical runner both exited0 and qualification was true.
This is four original natural Strong HTTP game cases plus the five birth controls,
not a sum of separate earlier gates. The original two deck pairs and both
orientations completed within the unchanged1200-accepted-tick bound per case
(20 per request, maximum60 requests). No forced winner or original assertion change.

The earlier pure-only section above describes its historical scope; the original
four HTTP cases are now independently qualified by this subsequent whole9 run.
Production code was unchanged. All3226 source input entries and3678 HF dependency
entries were byte-fixed;156 generated owned runtime files were classified separately,
not reported as unchanged original source. Six existing DB/backup/lock files had
empty direct fuser output with exit1; journals were absent. All16 observed native
connections were closed, with zero open handles, jobs, new threads, owned runtime
FDs or unexpected events; the parent and known observed processes were absent.
The parent archived the closed attempt and recorded SQL lease release. A separate
post-closure readonly integrity check passed for the default DB and four backups;
that check is not part of the nine pytest cases.

The physical boundary was privateNET/IPC, readonly host/dependencies, owned scratch
writes and finite owned SQL paths. It is not an all-child native-alias prevention
certificate. This is bounded natural-game legality/completion smoke, not A/B
strength evidence, full BO3, complete backend/hosted CI, or closure of all464
historical sideboard-facts failure rows. No private gameplay inputs or logs ship
with this three-path public increment.
