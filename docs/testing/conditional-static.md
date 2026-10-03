# Conditional Static Resource Effects

## Supported Scope

The shared static predicate reader evaluates supported graveyard-card thresholds,
distinct graveyard card types, permanent counts, empty hands, life thresholds,
colored permanents and basic land types against live state. Conditional self/team
P/T and complete keyword-grant clauses use that reader, as do supported attachment
and combat clauses. Only immutable parsed instructions are cached; resource and
controller changes are evaluated again on each query.

The canonical fixture contains 30 cards. Exercised ability families include
Threshold, Metalcraft, Delirium and Hellbent, plus life/color/land conditions.
Tokens do not count as graveyard cards; distinct normal types exclude supertypes
and subtypes and include Kindred. Supported compound clauses retain their common
condition across coordinated stat, keyword and attack-requirement instructions.
This is clause coverage, not certification of every ability on those cards.

Factory keyword inference now recognizes printed keyword-list entries rather
than every mention in Oracle text. An activated flying grant is not intrinsic
flying; a conditional flying grant is not active without its predicate. Protection
from each/all colors expands into the five qualities, and conjunction parsing no
longer splits the words `color` or `sorcery` internally.

Ward costs travel through the effective keyword layer, including conditional
grants, multiplicity, ordinary family removal, ability loss and resolution-effect
timestamps. Printed cost capitalization and dynamic X notation remain distinct
from lowercase keyword keys. Already-created Ward triggers retain their captured
cost when a source later taps or loses the grant.

## Validation

Canonical fixtures are normalized and byte-compared with saved fresh Scryfall
responses. The official 2026-09-25 Comprehensive Rules text is retained with the
batch evidence. No production card text or stats are invented.

The initial 72-case canonical probe reproduced 46 failures and 26 passes. Failed
and repaired focused runs are retained, including attachment punctuation, duplicate
Ward instances, dynamic-cost capitalization and a misplaced test-only assertion.
Tests cover both seats, resource activation/deactivation, controller changes,
snapshot parity, AI entry projection, cached names-only HTTP starts and SQLite
restore. Frontend boundary tests/build and Chromium exercise existing payment and
human workflows; six additional browser cases exercise conditional creatures.

The rules-only final full suite passed 5,211 tests (470 warnings, 960.72 seconds).
Two explicit seat-balanced BO1 matrices passed: Dimir Control/Tempo/Tokens/Ramp
(12 samples, 375.551 seconds), and Mono Red Aggro/Burn/Midrange (6 samples,
122.386 seconds). Each sample runs twice; there were no reported anomalies,
timeouts or determinism failures. These 18 samples / 36 executions are not
independent balance observations or expert-play evidence.

## Request Lifecycle Regression

New Chromium acceptance exposed a production storage-lifecycle defect: the
FastAPI session dependency returned an unclosed session. Repeated reads and
rejected requests could retain connections until garbage collection, eventually
exhausting SQLAlchemy's pool and blocking actions and subsequent reads. A retained-
reference, single-connection-pool regression reproduces the leak on rejected/error
paths. The dependency now yields inside a Session context. Success commits remain
explicit, rejected/uncommitted work rolls back, and request cleanup releases the
connection independently of garbage collection. Read-only requests are covered too.

The initial three-case lifecycle probe had two failures and one pass. The expanded
four-case old-source probe had three failures and one pass; the repaired four-case
probe passes 80 requests with retained session references and a single-connection
pool. The repaired 228-check API/lifecycle/conditional selection passed. Five fresh uninstrumented
Chromium repetitions passed all six conditional-card cases (30 cases total) after
the lifecycle fix. Before that fix, fieldset-aware clicks, explicit reload waits,
bounded Node polling and fresh connections did not by themselves stabilize the run.
One instrumented run passed but is not used as proof of stability. Failed logs
retain the actual QueuePool timeout, not merely the debugger timeout symptom.

The browser driver now observes native ancestor-fieldset disabled semantics,
waits for a new document after reload, polls authoritative state with a bounded
independent read, and verifies actual priority changes before the next reload.
Browser game mutations still occur through real UI controls; no rule/payment
assertion is weakened. The rules matrices preceded the lifecycle fix; rules/AI
source bytes are unchanged, and the dependency is specific to HTTP requests.

The complete lifecycle-fixed Chromium harness passed, including the six new cases,
process-restart recovery, sideboarding, natural AI BO3 and both human controller
modes. Frontend lint, runtime contracts, syntax checks and production build pass.
Final lifecycle-inclusive backend acceptance passed: 5,215 tests, 530 deprecation
warnings, 923.83 seconds. Production engine/storage source bytes match that tested
copy. This is 178 additional tests beyond the previous 5,037-test milestone.
Interrupted preliminary full runs and failed browser attempts remain separate
from completed gates; the broader product plan is not declared finished.

Canonical responses, failing/repaired source copies, test logs, browser evidence
and source snapshots are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/conditional-static/20261003T211845Z/`.
Archives are content-compared and SHA-256 verified before disposable local copies
are removed. The original database/dependencies and pre-existing untracked user
plan are preserved; tests did not use the live database. Dependencies were reused,
so this is not a fresh-install or network-security release certification.

## Known Limitations and Next Upgrades

Only complete recognized predicates and instruction bodies are implemented.
Unrecognized conditional static/combat bodies remain diagnostic gaps, not assumed
true. This is not complete devotion, characteristic/type-changing layer,
replacement-effect, arbitrary-card or expert-AI support. Basic-land predicates
currently consult type-line metadata; global land-type-changing layers need their
own acceptance work. Static AI entry projections do not forecast payment, future
draws, entry choices or adversarial responses.

Fresh matches use corrected keyword inference. Historical opaque snapshots can
contain incorrect keyword flags from the former substring inference; safely
reconstructing all activated/copy/override provenance is not established. Start a
fresh match when checking these mechanics. The deferred alpha-UI redesign is not
part of this backend batch.
