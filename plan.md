# MTG Deck Testing Lab Finish Plan

Updated: 2026-10-16 UTC. This is the execution index, not a release certificate.
The complete previous plan and its evidence remain in
[historical plan](docs/history/finish-plan-through-b81862a.md). Historical pass
counts belong to their exact source revisions; they do not certify current HEAD.

## Goal And Constraints

The user-facing delivery is one app with one launcher and one interface; internal
services may remain separate. Target Linux first, then Windows and macOS. Browser
acceptance includes Chrome, Brave and Firefox. Chromium-only evidence does not
certify all three browsers, and these priorities do not reduce Gates 1--3 or the
five-phase AI/data plan.

Finish a reliable two-player Magic deck tester with real rules, human and AI
pilots, custom and built-in decks, BO3 play, reproducible simulation, canonical
card knowledge and measured seasoned-player AI across deck styles. The original
full rules/arbitrary-deck ambition remains open beyond a bounded local beta.

- Rules, legality, costs, layers, replacements, combat and stack live in code.
  SQLite/PostgreSQL are replaceable storage, never gameplay stored procedures.
- Use complete verified card data and provenance. Never fabricate Oracle text,
  force match winners or tune toward an arbitrary 50/50 matchup expectation.
- Unsupported mechanics must be visible, not silently approximated as supported.
- Work in isolated sources/local SQLite; keep main/live/user data unchanged
  until a separately validated deployment. Archive verified evidence to RCHFiles.
- Test actual actions, choices, responses and restarts; parser recognition and
  passing characterization tests are not proof of correct gameplay.
- Preserve baseline failures, setup errors and timeout ledgers. No hidden skips,
  expected failures or weakened assertions to make a release gate look green.

## October 16 Canonical Death And Layered Toxic

The composed death/artifact and keyword/reset declaration passes all 278 ordinary
cases in 14 whole modules, including every earlier 54/224 identity and all 63
original functions' 240 assertions. Complete official fixtures replace shortened
real-card inputs. The generic toxic correction counts printed numeric instances
before layer removals/grants; damage consumes the final counts instead of adding
removed abilities back. Source/runtime preservation and actual owned-resource
closure are independently checked. See
[the exact composition and remaining limits](docs/testing/phase1-canonical-death-keywords-current.md).

The published `db4e0758` frontend and browser jobs have separately completed
successfully. Its backend job was still running when this record was written;
that older CI result is not transferred to the new production change. Passive
browser diagnostic contracts pass 406 cases in 11 whole modules, without changing
application requests, recovery actions or timing bounds. Earlier abort causes,
physical vendor acceptance and the remaining Phase 1 fixture scope stay open.

## October 16 Final Data Acceptance

The data-acceptance declaration now passes all 833 ordinary cases across 17
whole modules, with no failures, errors, skips or expected-failure exclusions.
All 829 earlier identities remain, plus four new end-to-end checks for missing
built-in names, real CLI sync and idempotence, canonical corpus/rulings joins,
and actual offline/public hydration. Full source and dependency inventories
remain unchanged during execution, and owned database/controller resources
close normally. The preceding failed run is preserved separately. See
[the exact source and execution boundaries](docs/testing/phase1-final-data-acceptance833.md).

This closes the outstanding final data-run gap, not the literal Task 1.3
fixture cleanup, complete Phase 1, whole-current-backend CI or release gates.

## October 16 Response Recovery And Activation Fixtures

The ordered replay-capture correction is published as `7fddf697`; its hosted
frontend job passes build, lint and all frontend unit commands. The browser job
has a separate held-response failure with an unknown abort cause. The recovery
harness now selects the response stage directly, retaining all original actions,
payloads, deadlines and checks except four explicitly adapted stage operands.
Four whole protocol modules pass 129 cases; actual browser CI remains required.
See [the exact boundary](docs/testing/browser-response-stage-recovery.md).

Hosted Chrome on `e2ecb3d4` now passes the original lost/held response scenarios
before stopping at the read-ahead fixture. Its legacy flattened-row adapter
requires power/toughness fields that the full canonical Saga correctly omits.
The branch now reuses the core tests' canonical loader; all 25 branch/core cases
pass, with every original browser assertion unchanged. This is not a captured
HTTP status or a completed browser gate. See
[the exact fixture correction](docs/testing/browser-read-ahead-canonical-birth-e2ec.md).

Three partial activation fixtures now use complete verified records. All five
original tests and fourteen assertions remain, and both whole modules pass ten
cases. Unsupported Oona activation remains rejected; this data migration does
not implement that ability or complete Phase 1. See
[fixture qualification](docs/testing/human-activation-canonical-7f.md).

The remaining named AI allocation fixtures now retain full canonical facts.
Native entry-counter preparation, not a printed-stat override, gives Phantom
Nishoba its intended effective 7/7 from printed 0/0 and seven counters. Three
whole modules pass all 14 cases, preserving the original allocation assertions
and AI calls without production changes. This does not certify the card's
separate damage-replacement behavior or complete Task 1.3. See
[the canonical pose](docs/testing/allocation-canonical-7f.md).

## October 16 Canonical Copy-Entry Integration

Canonical counter fixtures, retained printed/copiable characteristics and
explicit human/AI copy-entry choices are now composed in the integration tree.
Genuine copied permanent spells and the validated loyalty-return route retain
their actual source frames and reserve a detached token identity only once.
An independent review exposed a missing exact-type reference guard after a
passing 1,801-case composition; its two-line correction has a separate meaningful
RED and 756-case component pass. The final current declaration actually passes
all 1,837 ordinary cases across 67 whole modules in 506.04 seconds, including
every earlier 1,801 identity and the new 36 strict-reference controls. Source,
runtime and owned-resource closure are independently checked. See
[the source and acceptance boundaries](docs/testing/canonical-copy-entry-current.md).

This is still Phase 1 work alongside UI integration, not a completed phase or
release. Remaining handwritten-data scope, full hosted acceptance, physical
browser checks and the original AI/data and release gates remain open.

## October 15 Operator And Extraction Corrections

Published parent `92a59e11` separately completes all three CI jobs, including
28,357 passed backend calls and 82 recorded setup skips, with zero failures or
errors. The 81 passed subtest reports are not additional unique nodes. This is
the published parent, not CI for the changes below. See
[the complete terminal record](docs/testing/current-92a-complete-ci.md).

The existing launcher now identifies which service failed and its numeric exit
status without printing private configuration or subprocess output. Ctrl-C,
child arguments, lock release and shutdown behavior remain unchanged. This is
operator error reporting, not UI redesign or service-readiness qualification.
The existing file-only CI stage now runs its new 14-case regression module;
the same target passes locally without a Caddy binary environment binding.

Training extraction retains explicit matchup labels and valid action indices
using the existing prior consumer's normalization. It does not infer labels,
change AI weights or promote measured data. Seven whole integrated modules
pass **185 cases in 7.72 seconds**, with source/dependency hashes unchanged and
no unexpected I/O. Initial fixture setup errors and the superseded new test's
private-preimage dependency remain separate historical records. See
[operator diagnostics](docs/testing/operator-startup-diagnostics.md) and
[extraction acceptance](docs/testing/task33-extracted-context.md).

The README now documents the existing Phase 1 knowledge CLI, its stored-deck
coverage and its image/rules limitations. This documentation does not complete
the outstanding Phase 1 acceptance or the original release and AI gates.

## October 15 Knowledge And End-Step Acceptance

The real stored-deck knowledge workflow now passes 61 cases in three whole
modules, 6.53 seconds, with no failures/errors/skips. It rejects missing
mainboard/sideboard knowledge, ingests complete official records, and repeats
without requests or row changes. A minimal report correction deduplicates
casefold-equivalent names while retaining first spelling and distinct faces.
The unchanged baseline's 153-versus-151 failure is preserved. See
[the data/CLI component](docs/testing/phase1-stored-deck-corpus-current.md).

The generic ownership-conditioned end-step draw passes 122 cases in thirteen
whole modules, 460.61 seconds, with no failures/errors/skips. It checks the
condition at collection and resolution, retains actual copied-trigger control,
and reuses draw replacements/continuations. Separate existing abilities are
preserved; unsupported compound tails do not receive partial rewards. See
[the rules component](docs/testing/end-step-ownership-draw-current.md).
A subsequent strict mixed each/own regression exposes the preceding dispatch
priority defect. The corrected fourteen-whole-module cohort passes all 162
cases in 476.36 seconds, retaining every earlier case and adding 40 controls.
The compiler, predicate, draw resolver and registry remain unchanged; no-domain
cards retain the full prior branch chain. This closes that measured edge, not
all-card or browser acceptance. Earlier 122-case results remain historical.

After both corrections are integrated, the seven complete launcher/context
modules separately pass all 185 cases in 7.45 seconds. These are independent
cohorts, not a summed single execution. Only the earlier published `92a59e11`
has full hosted CI so far; the new integrated commit still needs that run.
Phase 1 and the full release are not declared complete by these checks.

## October 14 Public Numeric Sideboarding

Sideboarding now retains complete fixed-bound removal coverage and pairs
each verified public observation's printed cost with that same card's types.
Malformed, unknown, variable, stale and cross-record evidence cannot supply
a cheap target; missing cost is not zero. Only `_profile`, `summary_for` and
`_fit` change, without policy-weight, legality or private-state access changes.

The original 24 numeric cases plus eight malformed-receipt controls pass one
32-case cohort in 419.06 seconds. The same 234 existing neighbor nodes and
10 subtests pass in four separate whole-module cohorts, not a single summed
acceptance run. Original failures, timeouts and instrumentation corrections
remain archived. These are controlled correctness results, not natural BO3,
expert strength or completed measurement matrices. See
[the numeric coverage scope](docs/testing/sideboard-whole-numeric-profile-coverage.md).
Complete current hosted backend and original release/AI gates remain open.

## October 14 Restart And Ownership Fixtures

Five whole modules pass all 137 original cases, with 126 warnings in
89.27 seconds and zero failures/errors/skips. All 188 original module
assertions, 18 worker assertions and native worker timeouts remain intact.
Fixtures pass IDs before Factory capture or use the existing adopter;
ownership controls use genuine opponent-born stock instead of changing its
owner. The worker's producer statement changes explicitly, not its old
assertions or guards. The unchanged baseline's 12 failures remain archived.
See [the exact component scope](docs/current-residual137-fixture-acceptance.md).
This is not a new full hosted backend or combined release certificate.

Separately, three original source-contract modules plus 21 new inverse
controls pass all 54 pure cases in 1.55 seconds. Exact approved public
source deltas reconcile historical operands; unrelated mutations still
reject, and production/repository code is unchanged. The baseline's three
stale-source failures and two zero-execution harness stops remain separate.
The HTTP-bearing fourth module has not run in this cohort. See
[the finite source-contract scope](docs/testing/interface-source-contract-current-delta.md).
The 137-case and 54-case results are not a combined 191-case execution.

## October 14 Remaining Fixture Integrity

Six whole modules now pass all 249 ordinary cases, with 82 warnings in
52.15 seconds and zero failures/errors/skips. All 285 original assertions
and both real serializer workers remain unchanged. Four HTTP callers retain
Factory-born identities; intentional hidden-stock counterfactuals start
explicitly uncertified, while the Adventure attacker uses complete canonical
stock before birth instead of a renamed physical card. Gameplay, shared
helpers and canonical source files are unchanged. See
[the exact component scope](docs/current-valueerror249-fixture-acceptance.md).

Separately, five whole private-choice/optional-land modules pass all 61
original cases, with eight warnings in 330.10 seconds. All 177 old assertions
and original workers remain intact. Three fixture producers retain valid
birth identities; a separate 20-case pure projection is not an 81-case
integrated or HTTP result. The baseline's 20 identity failures and earlier
guard setup errors are preserved. See
[the private-choice fixture scope](docs/testing/http-bridge-factory-birth.md).
Neither component is a combined 310-case execution or a complete release gate.

The complete earlier hosted `f1fdfd0e` backend run separately accounts for
all 28,333 nodes: 28,152 passed bodies, 99 failed bodies and 82 setup skips,
with no metadata errors. Later component repairs do not retroactively turn
that historical failure into success. Latest whole hosted backend acceptance,
private-choice fixtures and the original release/AI gates remain open.

## October 14 Cost And Sideboarding Fixtures

Eight cost/activation modules pass one actual 795-case cohort, with
107 warnings in 99.99 seconds and zero failures/errors/skips. All 371
original assertions and gameplay rules remain unchanged; eight explicit
HTTP callers retain valid Factory-born fixture identities through the
existing adopter. The unchanged baseline's 18 failures remain separate.
See [the exact scope](docs/current-cost-activation795-fixture-acceptance.md).

Separately, the original seven AI-sideboarding tests plus four genuine
producer controls pass one 11-case run in 14.45 seconds. The fixtures use
checked paid actions and real terminal recording instead of injected winners;
the actual human loser chooses play/draw explicitly. Four reviewed live
swap-count expectations follow the existing three-card limit, while legacy
pure planner checks retain four. This is controlled-unit correctness, not
natural-game AI strength. See
[the sideboarding scope](docs/testing/ai-sideboarding-current-fixtures.md).
These independent results are not a summed integrated acceptance. Complete
hosted backend, all-browser deployment and original release/AI gates remain open.

## October 14 Casting And Observation Fixtures

Four casting modules now pass all 215 unchanged cases in 32.45 seconds,
with 82 warnings and zero failures/errors/skips. Existing fixture adoption
retains Factory-born IDs instead of overwriting captured identities; all
172 assertions and 48 unrelated bodies remain intact. A separate eight-case
pure projection also passes, not counted as part of the 215-case run. See
[the casting scope](docs/testing/cast-http-fixture-birth-adoption.md).

Separately, all 24 canonical self-entry cases plus nine serializer protocols
pass in one 33-case run. The witness now uses complete canonical serialized
observation records, matching the existing omission of an empty optional
knowledge dictionary. All 71 original gameplay/privacy assertions, including
the returned card's HAND zone, remain intact. See
[the observation scope](docs/testing/self-entry-public-return-witness.md).
These are separate measured cohorts, not a summed integrated result.
Current complete hosted backend and the original release/AI gates remain open.

## October 14 Saved-Match Follow-Up

The saved-match fixture repair now passes one actual four-whole-module cohort:
83 ordinary cases, 75 warnings, 16.15 seconds, zero failures/errors/skips.
The baseline's 12 failures were inconsistent fixture IDs captured before a
later serialized-ID overwrite. Intended IDs now enter before factory birth;
original assertions, corruption controls and gameplay production remain intact.
All 113 observed connections and owned processes close; 67 existing database,
backup and lock files are independently quiet. See
[the exact fixture scope](docs/testing/lazy-saved-match-fixture-birth.md).
Current complete hosted backend and original release/AI gates remain open.

## October 14 Current-Source Follow-Up

A fresh composition over published `45d4ef47` passes all 172 cases in six whole
modules, with 100 warnings in 106.59 seconds and zero failures/errors/skips.
All 156 old assertions, full snapshot equality and six actual cold-restart
workers remain intact; 154 observed database handles and owned resources close.
The separate optional CI runtime-version report passes 200 script cases,
preserving 707 old assertions without changing coverage or qualification.
These are separate measured results, not a summed integrated cohort.
See [the exact current-source scope](docs/testing/current-integrated-fixture172.md).
Complete hosted backend, all original release/AI gates and clean-OS/browser
trust remain open; the private synthetic trace is not published.

## October 14 Integrated Fixture Acceptance

One actual combined execution over `f102874ff` passes all 484 cases in eleven
whole modules, with 146 warnings in 425.74 seconds and zero failures/errors/skips.
All 371 original assertions remain; only fixtures and documentation change.
All 216 observed database handles and 118 recorded child waits close, and the
independent ownership/source/runtime checks pass.
See [the integrated scope](docs/testing/current-integrated-fixture484.md).
Complete hosted backend and the original release/AI gates remain open.

Native Firefox separately completes the unchanged 50 application cases and
seven natural BO3 games in 1,721.566 seconds. The outer supervisor retains a
diagnostic hold for one historical process-identity observation; it is not
silently relabeled as clean. Known physical resources close independently.
See [the application result and diagnostic boundary](docs/testing/firefox-native-application50.md).
Native Chrome/Brave and remote LAN/trust acceptance are not inferred.

## October 14 Checked Components

The next test-only fixture-binding batch passes all 354 ordinary cases in nine
whole modules, with 821 warnings and no failures/errors/skips, in 476.12s.
All 195 old assertions, canonical data and gameplay production remain unchanged.
The earlier nine SQL-policy failures are preserved; the corrected harness binds
the actual collected callers rather than separately imported module copies.
All 128 serializer children close, source/runtime pins match, and the independent
external receipt verifies 75 existing database/backup/lock files quiet.
See [the complete scope](docs/testing/current-fixture-binding-transitions.md).
Current full hosted backend CI and all remaining original gates stay open.

## October 13 Execution Checkpoint

The next three fixture repairs retain the original assertions and strict stock
validation: selected-mana HTTP/projection passes 55 cases, keeper/private-choice
acceptance passes 125 cases plus nine subtests, and selection/Suspend passes
177 checks including one private construction witness (176 public cases).
These separate source-specific results are not a summed backend result.
See [selected fixtures](docs/testing/current-selected-mana-fixture-acceptance.md),
[keeper birth](docs/testing/keeper-fixture-birth.md), and
[selection/Suspend birth](docs/testing/current-selection-suspend-fixture-birth.md).

A fresh combined declaration then passes all 356 public cases in nine whole
modules, plus nine separately reported subtests, in 460.28 seconds. It includes
the publication-shaped keeper header and excludes the private construction
witness. Source/runtime bytes are stable; all 184 serializer children and owned
database resources close. See [the composed acceptance scope](docs/testing/current-composed-fixture-acceptance.md).
The operator's public-copy 49 configuration cases and
12 standalone inventory checks also pass separately. No whole-CI, all-browser,
LAN trust or AI-strength completion follows from those component results.

The Linux foreground launcher now supports an optional validated RFC1918 IPv4
frontend bind while retaining default loopback and a loopback-only backend.
Native configuration checks pass both default and private-IP adaptation; the
unchanged full HTTPS/restart program also passes on the candidate default,
with 541 observed checks and the same complete check-label set as prior 547.
A subsequent complete native run on immutable `3f512cd0` uses an actually assigned
RFC1918 interface on THISHOST: all537 observed checks pass, with all71 original
check callsites retained through explicit endpoint/config/SAN operand rebindings.
Source3220+DIST3/package/system pins match before/end, both production-first
shutdowns verify and all135 known tasks plus owned SQL/listener resources close.
This is same-host native TLS, not remote LAN/browser trust or final-source proof.
User-selected LAN hostname, all-three-browser/manual trust and clean-machine
acceptance remain unqualified; see [the exact bind scope](docs/testing/linux-private-lan-bind-prep.md).

The counter-fixture and cold-restore component now passes 153 ordinary cases
across four whole modules on its exact `50f9e58b` plus test-only composition.
Both genuine cold HTTP workers and 38 snapshot children exit successfully;
source, database ownership and resource closure are independently checked.
Every original assertion remains intact. See
[the exact cold acceptance](docs/testing/current-counter-fixture-cold-acceptance.md).

The private reference bank now completes all 104 declared checked outcomes on
its recorded `a9431b12` epoch, with 810 additionally charged native calls and
unchanged source. The original 520-case, five-variant A/B comparison has now
executed on its recorded data epoch: 442 cases complete and 78 are unavailable,
including 72 per-root resource stops and six blocked endpoints. All 520 rows
and their original limits remain intact. This partial, unscored result is not
measured AI improvement or a completed benchmark. Neither reference completion
nor the older complete matrix transfers qualification to current HEAD.

The current test-only printed-source fixture correction now passes all 244
ordinary cases in sixteen whole modules, including eight genuine TestClient
lifespans, with unchanged source and installed packages. It retains every old
assertion and the genuine Factory stock guards; controlled synthetic fixtures
start UNKNOWN rather than erasing captured facts. The earlier 236-pass/eight
policy-failure result is preserved separately. See
[fixture birth qualification](docs/testing/controlled-basic-fixture-births.md).

The Linux operator now rejects runtime data nested below the served frontend
directory, closing a reproduced configuration exposure. Eight new file-only
settings controls and twelve unchanged inventory controls pass. This does not
transfer native HTTPS or LAN/browser-trust qualification; see
[the exact boundary correction](docs/testing/operator-dist-runtime-boundary.md).

An earlier combined backend acceptance passed 2,998 ordinary cases across 82
whole modules on its recorded composition. Its HTTP separately passed 18 cases/six cold restores,
and frontend test/lint/build and the complete zero-argument configured browser
program pass. The browser run finishes in 2,263 seconds under aggregate capacity
45 minutes, preserving every per-program deadline and assertion. Built
HTTPS/LAN and complete hosted CI remain required; the old c259 hosted
backend stops with disk exhaustion and no available test counts. The earlier
native matrix is terminal but incomplete (100 resolved, ten resource-limited
series, exit 3). The separate `2b9f3a60` full110 matrix is now terminal: all 110
series were attempted, with 104 resolved and six resource-limited. Its 258 game
entries include 252 winners and six timeouts. Source/runtime and actual resource
closure are verified, but the matrix is incomplete; no whole learned-profile,
current-source or measured-strength completion is inferred.

Latest bounded acceptance: the reviewed composition over `c2590095` passes
2,553 ordinary cases across 70 whole modules, and a separate natural BO3 run
completes six games in both seat orientations with nine actual different-card
sideboard swap units. Full integrated browser/HTTP and hosted CI, terminal
matchup data, measured quality comparisons and the original Gates 1--3 remain
required. See [the current evidence boundaries](docs/testing/current-c259-reviewed-composition.md).

The next reviewed composition over published `837bf513` passes 2,147 ordinary
cases in 54 whole modules, with zero failures, errors or skips and unchanged
source. It combines bounded profile play advice, private sideboarding, the
knowledge-report correction and reproduced inventory/observation CI repairs.
The prior published workflow actually finishes with 139 failed bodies;
frontend and browser pass. Current full hosted CI, final-source cold HTTP,
natural sideboarding and measured AI quality still require their own evidence.
See [the exact composition and failed histories](docs/testing/current-837-ci-repair-composition.md).

The resulting published `2eeb7f76` frontend job passes, while its browser job
exposes stale original-stock capture in a mirrored synthetic combat fixture.
The fixture-only repair preserves every browser assertion and the strict owner
validator; 21 pure cases and the unchanged actual browser scenario pass for both
seats. This is focused acceptance, not the full browser gate. See
[the exact fixture correction](docs/testing/browser-seat2-capture-fixture-current.md).

Published `7c5e933a` adds tested actual-allocation blocking and the source-bound
BO3 measurement runner. Its fresh 41-whole-module component passed 775 ordinary
cases with zero failures, errors or skips. Frontend and browser CI have completed
successfully in run38330804691; the protected backend is still running at this
checkpoint. See [combined component evidence](docs/testing/ai-bo3-block-composed-current.md).

Phase 2 is not unstarted: canonical profile derivation, persisted profile use,
cast inputs and checked blocking improvements are implemented. The specified
seed/seat-balanced A/B acceptance remains unfinished. Phase 3 runner code is
implemented, but protocol tests do not certify a played matchup matrix or learned
profiles. Complete matchup data, contextual priors, deliberate sideboarding and
Phase 4 strength measurements remain required. Commit counts are not a percentage
of either this AI plan or the three release gates.

The first current-source native attempt reached real canonical ingestion,
profiling and hydration of all 11 shipped decks, then stopped before games: the
shared runner compared canonical full double-faced card names against printed
front-name deck inventory. The reviewed correction preserves exact seed identity,
card quantities and readiness checks. A fresh source-bound equal-budget Strong
comparison then completed ten real games across both seat orientations; every
normalized gameplay line and outcome matched. Its 600-second per-BO3 budgets
were unchanged. The full 110-series matrix is now executing separately; it is
not yet a qualified data artifact. No winner, private trace or matchup data is
fabricated to close the gap.

The final reviewed contextual-prior, canonical-admission and learned-profile
protocol composition passes 933 ordinary cases across 45 whole pure modules.
A separate fresh checkout of that same final composition passes the whole
original 378-case public-mana module, including all six real
SQLite/autoplay/restore controls, with unchanged source and no policy violations.
Malformed context types, conflicting provenance, numeric overflow, asymmetric
learned samples, incomplete roster coverage and measured-source CLI output
mutation have explicit regression controls. No learned table is generated yet.
The original all-rules, arbitrary-deck, expert-AI and release requirements remain
open until their own acceptance evidence exists.

See [Phase 3 code and execution evidence](docs/testing/ai-phase3-groundwork-current.md).

The next composition, based on published `2f42a6eb`, passes 202 ordinary cases
in seven whole modules (13.94 seconds, zero failures/errors/skips). It adds a
sealed, terminal-only native training exporter, enables the unchanged Task33
canary in ordinary backend CI through an exact call-scoped guard, and verifies
24 canonical lethal/nonlethal scenarios on existing AI and rules. No active
matrix data is read or learned artifact generated. The full matrix remains a
separate running measurement on its retained preconsumer source epoch.
See [native intake contract](docs/testing/task33-native-training-adapter.md),
[ordinary canary scope](docs/testing/task33-ordinary-ci-canary.md), and
[canonical lethal checkpoint](docs/qualification/task41-canonical-lethal-gap.md).

The original five-plus-one first-strike example against seven life deals six,
not lethal damage; its literal position is preserved as a nonlethal control,
with six life as the actual-win sibling. Scenario positives do not replace the
plan's measured A/B or bounded-search acceptance. Sideboarding private-fact
capture is under implementation; completed-game coverage, actual selection,
legal between-game transitions and a real BO3 swap remain unfinished.

The reviewed measured-epoch update changes only two lineage hashes, preserving
the actual `7c5e933a` source base and every consumer function. Its composition
over published `fb3291f6` passes 367 ordinary cases in ten whole modules; the
whole 46-case builtin metadata-refresh SQLite/ASGI module separately passes.
Old and mixed measurement tuples reject through the default loader. This is
preparation for genuine terminal data, not a completed matrix, generated learned
table or A/B result. See [epoch admission](docs/testing/task32-measured-epoch-repin.md).

Fresh isolated installation on `03b601fc` passes the current 28-package backend
hash lock, dependency consistency, the 367-case component cohort and all 48
configured frontend test programs, lint and build. Separately, the unchanged
knowledge CLI on `fb3291f6` exits zero for its actual 149 requested names; all 155
seed identities are independently checked after real canonical/rulings/profile
ingestion in owned SQLite. No live database or deployed runtime changes.
See [exact install and knowledge scopes](docs/testing/current-clean-install-knowledge-acceptance.md).
Current whole backend CI, genuine matrix/data/A-B, sideboarding and all three
full release gates remain unfinished.

The reviewed interaction-hold increment fixes the observed stable tier-1
counter-waste cases without changing weights or granting legality. Its actual
current-source composition passes 591 ordinary tests across 22 whole modules
(88.29 seconds, zero failures/errors/skips). Only `_choose_action` changes;
all 136 other prior agent methods are unchanged. The additive guard requires
known RAW-complete vanilla/free-tap-mana bodies and a bounded stable public
context. Actual Forest-paid spells and Island counter payments are covered.
Unknown bodies, pressure and unsupported contexts preserve legacy behavior.
See [counter-policy bounds and histories](docs/qualification/task42-stable-counter-filter.md).
Sideboard private-fact transitions have separate scoped 285-case proof, but
current combined real-I/O, cold-restart and natural BO3 acceptance remain open;
no empirical A/B improvement is inferred from these scenarios.

## Current Candidate Qualification: 2026-10-12

Published `4ff6a814` passes frontend and browser CI in run38303109399;
its protected backend job is still executing at this checkpoint. The preceding
`f2d4622c` backend job is also still executing, not inferred to pass.
The data-layer increment adds deterministic tactical profiles and opt-in
`sync_corpus_cards --profile` without changing AI policy. Six whole component
modules pass85 ordinary cases plus10 subtests, including real repository
roundtrip and zero-update repetition across all155 shipped names using complete
official API data. Profile estimates are not measured strength or legality.
The next test/data-only increment verifies official rulings for all155 shipped
names: 443 rulings and35 verified empty lists, with all89 cases in seven whole
modules passing. Actual cache/knowledge persistence, new-session reads,
idempotence and malformed-ruling rejection are covered; live databases and
additional user-deck cards are not modified or certified by that component.
The next consumer increment connects validated match-frozen printed tags to
production AI and forwards anonymous per-decision usage into diagnostics. Its
15-whole-module component passes190 cases, including actual155-card repository
hydration, both-seat checked paid decisions, private cold/public-view controls,
and the original seeded Tempo/BlueControl master smoke completing naturally.
No numeric policy weights change. Full current hosted CI and HTTP/file-storage
acceptance remain separate; threat-aware numerical scoring, learned matchups,
deliberate sideboarding and measured quality phases remain open.
See [profile derivation](docs/testing/knowledge-profiles-current-derivation.md)
and [sync/persistence qualification](docs/testing/knowledge-profile-sync.md),
plus [shipped rulings](docs/testing/knowledge-rulings-shipped-corpus.md).
See [actual knowledge decisions and traces](docs/testing/ai-knowledge-repository-and-traces.md).

Published `3a7db1e2` now passes the complete configured frontend, browser and
protected backend CI workflow. Verified sanitized metadata accounts for all
26,173 nodes: 26,091 passed bodies, 82 setup skips, 15 separately passed subreports,
and zero failures, missing/duplicate phases or export errors. Preceding `7697eb2c`
also passes its full workflow. No protected input or raw backend logs were exposed.
Unpublished AI changes, additional cold HTTP episodes and unproved original
release requirements remain open. See [complete CI checkpoint](docs/testing/current-3a7-complete-ci.md).

The next AI increment repairs neutral draw utility and effective-indestructible
combat allocation without changing rules or policy weights. An independent
whole NEW36 cohort passes; three unchanged HTTP/combat modules pass all86 cases
in a separate isolated run. These are concrete behavior repairs, not a measured
expert-AI or full-horizon benchmark. Hosted qualification of the new increment
remains required. See [AI behavior evidence](docs/testing/ai-terminal-draw-and-allocation.md).

A fresh composition passes all395 cases in12 whole modules (84.26s), covering
native worker URI/scope, paid flashback/query/provenance, and hydration/foretell
fixtures. Production is unchanged; two malformed-cache predecessor cases now
explicitly assert rejection rather than recovery. See [URI scope](docs/testing/ci-interface-uri-scope.md),
[stack/query](docs/testing/ci-stack-query-provenance.md), and
[hydration/foretell](docs/testing/ci-hydration-foretell-contracts.md).

The controlled BO3 cold-read test no longer depends on uncommitted `gate.py`.
Its fresh three-whole-module cohort passes22 with all46 original assertions
unchanged; production/gameplay is untouched. [Cold worker scope](docs/testing/ci-bo3-cold-worker.md).

The older `73458804` protected backend now has complete sanitized terminal
phase records: 26,006 nodes, 25,324 passed calls, 66 failed calls, 534 setup
failures and 82 skips. Every setup failure is native SQLITE_FULL13; source
predates passed-snapshot cleanup. No newer-run success or physical-disk cause
is inferred. [Current diagnosis](docs/testing/ci-734-sqlite-full-diagnosis.md).

The next paid stack-provenance fixture batch independently passes all95 cases
with 295 original assertions preserved. Rules/classification and AI policy are
unchanged. [Fixture scope](docs/testing/ci-stack-provenance-fixtures.md).

Published `788e219a` retains the protected backend qualification requirement.
Its predecessor's scoped missing-source and consumer-epoch cohorts pass 212
and 67 checks; the explicit Favor worker-input cohort independently passes24.
The next pure capacity-policy fixture correction passes the same93-case whole
neighborhood with the disposable default file present and absent. Production
storage/backup/capacity policy is unchanged; shared startup failures remain open.
See [capacity fixture scope](docs/testing/ci-capacity-policy-fixture-portability.md).

The next exact complete creature-destruction loyalty grammar and fixture batch
passes an independent nine-whole-module /91-case check (21.28s), preserving all
106 original assertions, legal competing casts and AI/winner policy. At that
checkpoint, full-card Vraska remained explicitly unsupported; no partial
admission was substituted.
See [loyalty/Boon scope](docs/testing/ci-closed-loyalty-creature-and-boon.md).

The next test-only trigger/query fixture correction passes all 44 cases across
four directly affected whole modules independently. Exact trigger clauses and
both query-scope paths remain covered; no production or full-ability-resolution
claim follows. [Trigger and query evidence](docs/testing/ci-suspend-and-multiplier-fixtures.md).

The next conservative passed-startup-snapshot cleanup and animation-fixture
batch passes independent whole cohorts of 141 CI-script checks and 114 animation
tests. Gameplay, backup and capacity clocks remain unchanged; no hosted startup
cause is inferred. [Snapshot and animation scope](docs/testing/ci-snapshots-and-animation-fixtures.md).

The next reporting and explicit-keeper fixture increment passes 138 CI-script
checks and an independent 30-case whole SBA cohort. It repairs the reproduced
evidence-directory redirection without dropping records, and preserves real
human choices rather than inferring them. The startup cluster remains open.
See [current evidence and keeper scope](docs/testing/ci-session-evidence-and-keeper.md).

The isolated decision-quality loader now acquires all 48 declared interfaces,
but no gameplay or quality scoring is inferred. The test audit-hook lifetime
repair separately passes its 51-case whole component cohort and retains all
seven original parametrized SQL/socket canaries. See
[load boundary](docs/testing/decision-quality13-load-boundary.md) and
[canary finalization](docs/testing/guard-canary-finalization.md).

Published `8b1bffa2` passes frontend and browser CI. Its protected backend job
completed with failure: sanitized metadata records 25,997 collected nodes,
25,308 passed bodies, 73 failed bodies, 532 setup failures, 82 skips and two
missing call phases. These are not independent bug counts or complete coverage.
The next test-only paid-counterspell fixture repair passes its whole 48-case
cohort independently; the shared startup-backup cluster and remaining release
requirements remain open. See [current fixture evidence](docs/testing/ci-boon-paid-fixture-current.md).

Earlier published `d727e0d1` passes frontend and the whole browser job in
run38188006567. Its complete local zero-argument browser run also passes, with
all 2,020 tracked backend/frontend source files byte-equal to that commit.
The human two-target permanent picker and public original/copied stack targets
are corrected; the six-whole-module backend neighborhood passes all 218 cases.
Protected full backend CI remains active and is not qualified by these component
results. The original all-rules, arbitrary-deck, expert-AI and remaining release
requirements stay open. See [human target scope](docs/rc-distinct-permanent-targets.md).

At the previous `25ef55ea` checkpoint, frontend and whole browser CI pass in
run38175740307; protected backend qualification was still active. The reviewed
legacy restart follow-up now passes 113 pure controls and a distinct current-source
20-case whole HTTP cohort. It retains raw database comparisons, verifies the
actual owner-epoch transition and preserves the historical failed ledgers.
There are no production ownership/capacity changes or full-release claims.
See [restart evidence](docs/testing/legacy-restart-epoch-current.md).

Earlier `a3694abc` passes frontend and whole browser CI. Its backend
run38130914210 fails with an explicit runner disk-exhaustion annotation and no
result artifact, so no backend test count or pass is inferred. The next runner
correction uses built-in passed-test scratch reclamation without changing test
selection or gameplay assertions. Two new real pytest regressions and all128
CI-script checks pass; full hosted qualification remains required.
[Scratch retention scope](docs/testing/ci-backend-scratch-current.md).

Published `1f08a6ca` passes hosted runner-capacity admission, metadata-reporter
checks and frontend CI in run `38128147774`; full backend and browser jobs were
still running at that checkpoint. The finite SDK cleanup-budget correction retains all safety
guards and passes 126 script checks. The prior `ed3bf11f` pre-test admission stop
remains preserved, not relabeled as a gameplay failure.
[Infrastructure scope](docs/testing/ci-backend-sdk-timeout-current.md).

The next test-only combat fixture increment preserves all original assertions
and production restore guards. Its full component cohort passes 152 checks;
the parent's independent current-source whole cohort also passes all 152. The existing AI
consumer patch separately passes all 92 unchanged discard-history cases,
without a new production branch. The current trigger family already passes all
119 unchanged cases; two new paid-entry forwarding regressions pass separately.
Combined hosted qualification and all unproved
release requirements remain open.
[Fixture and evidence scope](docs/testing/ci-training-combat-fixture-current.md).

The next Fable test-only increment corrects two fixture KeyErrors by explicitly
injecting a forged private continuation, without restoring public disclosure.
All original assertions remain. Its distinct known-deck/Fable/linked-discard
whole group plus four new privacy controls passes 152 checks; no production or
duplicate AI change is made. Full combined CI remains open.

Published `b0880389` passes remote frontend and whole browser CI. Its protected
backend in run `38125893436` remains active, not qualified by component results.
The next reviewed accounting/declared-stack fixture batch has separate 217-pass
and 57-pass gates, and the private AI continuation consumer fix passes 107 checks
with all 82 original forecast tests unchanged. The combined source still needs
its complete CI result; this does not close measured expert-AI quality or any
unproved original release requirement.
[Exact follow-up scope](docs/testing/ci-accounting-stack-contracts-current.md).

Published `1a8e0869` passes the original whole remote frontend and browser jobs.
Its protected backend job `114341798370` in run `38095963507` completed with
failure. Complete sanitized metadata records 25,682 nodes: 24,733 passed test
bodies, 327 failed test bodies, 540 setup failures and 82 skips; no missing phases
or metadata-export errors. These are not independent bug counts. Capacity
admission and metadata-reporter checks pass, but backend qualification does not.
See [current CI diagnosis](docs/testing/ci-1a8-backend-terminal-current.md).
Reviewed scoped fixture/guard repairs now have separate passing component
cohorts; the privacy-safe diagnostic suite passes 124 checks. The next complete
protected CI must qualify their combined source. Shared setup failures and
unproved original release requirements are not marked complete by these runs.
The preceding `dfdd121e` backend run
failed with platform disk-exhaustion and runner-failure annotations and no
sanitized result artifact; no gameplay failure count is inferred. Capacity
remediation is not whole-suite qualification. Final combined built/HTTPS
acceptance and measured AI quality remain unfinished.
[Current acceptance](docs/testing/release-acceptance-status.md) and
[prior CI history](docs/testing/ci-dfdd-current-status.md).

Published `58ab2881` now passes the original whole zero-argument remote browser
job and frontend CI. All 45 ordered stage banners and 67 invocations complete,
with 497 passed checkpoints, not pytest tests. Both-seat cost branches,
recovery/restart, three natural BO3 modes and the original later
interactive/Officer/Cathar programs pass. Tamiyo P/G remains player-one-only,
human BO3 opponents use 60 Islands, and interactive API responses are
substituted. The host-reboot-interrupted local run has no terminal certificate
and is not relabeled as this remote result. Protected backend CI, other unproved opt-in native
acceptance, measured AI quality and all unproved original requirements remain
open. [Exact browser scope](docs/testing/browser-58ab-current-acceptance.md).

The original ten-case native Suspend HTTP module separately passes in 52.25s,
with both seats and two real cold restarts, unchanged assertions/clocks and
verified production-first closure. Its scoped source is `58ab2881` plus the
two-line fixture saved-match reload; seven new pure helper regressions also
pass. This closes that native cohort, not the full backend suite, strategic AI
or any unproved release requirement.
[Exact native scope](docs/testing/suspend-native-http-current-acceptance.md).

Earlier published `38e43cd5` passes the remote frontend job. Its browser run passes
recovery, sideboard swapping, copied Helix/Drain controls and natural AI,
human-vs-AI and human-vs-human BO3, then times out waiting for
`window.interactiveFixture` in the independent interactive-preflight program.
The complete fixture module is tracked, but its HTML entrypoint is absent;
Vite renders the normal app instead. No checkpoint inside that program passes.
The preceding `eb8d8805` cleanup failure remains a separate historical ledger;
the corrected cleanup now exposes the primary error without changing gameplay
assertions or clocks. [BO3 scope](docs/testing/human-bo3-readiness-current.md).
The independently reviewed entrypoint repair now passes the complete parent
44-entrypoint frontend chain, lint and build. It adds only a minimal wrapper
for the unchanged fixture plus packaging regressions; the original 43 entries
remain the ordered prefix. Actual native preflight, complete browser and
protected backend CI remain open.
[Entrypoint scope](docs/testing/interactive-preflight-entry-current.md).

The independently reviewed interactive-preflight cleanup correction preserves
the entire original gameplay body and all clocks. Its eleven regressions and
the parent's complete 43-entrypoint frontend chain, lint and build pass; all 42
original entrypoints remain the ordered prefix. Actual native preflight and
complete browser acceptance are still pending, not inferred from mock boundaries.
[Cleanup scope](docs/testing/interactive-preflight-cleanup-current.md).

The exact current combined-source HTTPS/authentication/media/restart invocation
passes all 547 observed check instances, including strict native H2 certificate
negatives, without changing the original deadlines. Source/dependency equality
and actual native closure are independently verified. This is loopback operator
qualification, not LAN deployment or complete browser/release acceptance.
[Current HTTPS scope](docs/testing/caddy-operator-current-acceptance.md).

The first bounded 13-style benchmark stops after 135 of 260 chooser calls at
the declared 64-native-evaluation root cap: 134 accepted rows and one incomplete
restore check. The separate second whole-matrix attempt executes 234 calls:
233 accepted rows, one incomplete row and 26 unexecuted rows, stopping at the
declared cumulative 2,048-native-action global quota, not its 256 root cap.
All 2,048 native entries and 369 cumulative chooser events retain exact earlier
prefixes and the same source epoch. A separately authorized third whole-matrix
attempt now accepts every original ordered row: 260/260 across all thirteen
styles, both seats and five declared variants. It charges 824 additional native
entries, bringing the retained ledger to 2,872 and chooser history to 629; no
counter resets or partial-row substitutions occur. This completes the mechanical
legality baseline, not objective horizons or measured seasoned-player strength.
Independent quality scoring and meaningful hidden-identity controls remain open.
[AI legality scope](docs/testing/decision-quality13-legality-current.md).

The latest complete-devotion precedence correction passes 2,029 cases in 51
whole pure modules, 282.17s, preserving every previous 1,995 ordered identity
and adding 34 regressions. All 1,941 declared source hashes remain unchanged.
The separate seven-whole-module declaration passes 206 cases, including all
original devotion tests and four actual HTTP/SQLite restore cases. The actual
browser defect, strict raw-body correction, initial harness failures and open
release gates are recorded in [exact scope](docs/testing/devotion-entry-precedence-current.md).

The latest reviewed complete-loyalty/typed-resource composition passes 1,995
cases across 50 whole pure modules, 276.49s, retaining the full ordered 1,882-case
prefix and adding 113 cases. Seven production files change; all old tests and
browser assertions remain unchanged. All 1,940 declared source hashes remain
stable during execution, and native I/O canaries, empty owners and empty threads
pass. This closes the observed native Chandra/Food defects, not all three release
gates. Complete current browser, strict HTTPS, protected-input CI and AI-strength
results remain required. [Exact scope](docs/testing/complete-loyalty-food-current.md).

The combined cost/Daretti, complete-modal, private discard and strict metadata
candidate passes 1,882 cases in 47 whole pure modules, 263.49s, retaining all
1,815 previous union identities plus 67 new cached-face-container checks. The
container correction first reproduces 42 failures and 25 passes, then passes the
same tests and the complete declared union. Source hashes and pre-import native
I/O-denial receipts remain stable. These are overlapping component scopes, not
the unfiltered backend suite.

The frontend snapshot passes all 40 original configured test entrypoints, lint
and build, with source/dependency byte continuity and native closure. The full
browser run fails at a stale private-discard metadata read after 146 passing log
checkpoints; later stages are unreached. A fixture-only correction now reads the
affected actor's offered legal move, retaining every original assertion, wait
and click. Six regression checks reproduce the failure and then pass. The normal
test chain retains its original 40-entrypoint prefix and adds this regression;
all 41 entrypoints, lint and build pass. The same 47-module backend union then
passes all 1,882 cases again in 253.70s with 1,932 source hashes unchanged.
Fresh complete browser, native HTTPS and current protected-input CI remain required.
Published `a24d3329` CI failed, with no backend metadata artifact available; its
backend failure cause remains under safe-metadata investigation. No raw private
trace or backend logs are published or downloaded for diagnosis.

See [exact scope and remaining gates](docs/testing/current-modal-daretti-release-candidate.md).
The original three gates, all thirteen AI styles, arbitrary-card rules and
independently measured seasoned-player strength remain unfinished. A scoped
playtesting milestone does not redefine the final objective.

## Latest Verified Milestones

2026-10-10 original native Suspend HTTP qualification: ten passes in 52.25s,
zero failures/errors/skips, three actual server processes and two cold restarts.
Source/dependencies and actual owned closure verify before fixture cleanup;
seven independent pure reload regressions pass. See
`docs/testing/suspend-native-http-current-acceptance.md` for scope and histories.

2026-10-10 remote whole browser qualification on `58ab2881`: original zero-arg
program, all 45 stage banners/67 invocations, 497 passed checkpoints and
successful job `114300811126`. This closes that previously failing original
browser cohort, not arbitrary-card, strategic-AI or overall release acceptance.
See `docs/testing/browser-58ab-current-acceptance.md` for explicit coverage limits.

2026-10-10 browser-harness follow-up over `9ce7e1fc`: the actual remote browser
job stops before seat two's discard-payment cast with a stale prior fixture.
Existing v2 identity/revision/idle checks now guard that program's fixture and
action handoffs. Eleven actual-script regressions reproduce eight failures and
then pass; the independent parent complete 46-entrypoint frontend chain, lint
and build exit zero. Every original action, assertion and clock remains intact.
Full native browser, protected backend CI, opt-in HTTP and AI-quality acceptance
remain required. See `docs/testing/browser-cost-handoff-current.md`.

2026-10-10 follow-up over `b7067d70`: the full browser reproduces a Tamiyo
cast-offer regression caused by legacy supertypes entering the strict typed
query. Three caller projections now preserve the actual selected-method view
and pass all 254 focused cases, including 34 new regressions. The independent
815-case native union now completes 805 ordinary passes and ten unchanged opt-in
HTTP skips, with exact original prefix, source/dependency equality and native
closure verified. Full browser, opt-in HTTP and protected CI remain separate
acceptance boundaries. See
`docs/testing/spell-type-caller-current.md`. No original gate, AI-quality label
or benchmark counter is reset.

2026-10-10 candidate over `c1057647`: typed Soulless Jailer selected-cost guards,
independent Reanimate life loss, scoped legacy audit canaries and Cathar's exact
frontend-origin launcher are applied. Whole frontend test/lint/build and bounded
canonical checks pass. The current 781-case native union finishes with 771
passes and ten original opt-in skips under a backup-call-only diagnostic
observer. Exact ordered nodes, source/dependency equality and native closure
are verified. Its preceding backup setup timeout remains unexplained;
whole-browser, opt-in child HTTP and protected backend qualification are pending. This does not
close Gates 1--3 or the unscored AI-quality corpus. See
`docs/testing/jailer-reanimate-and-cathar-current.md`.

- [x] Native cold-restart fixture portability: seven whole modules / 704 passes,
  702.88s, unchanged original node identities/assertions and actual complete
  SQL/ledger checks. All observed native/read-only children and database handles
  close; exact source and fourteen fixture postimages are verified. Active-job,
  protected-trace and full-release acceptance remain separate.
  [Scope and histories](docs/testing/ci-cold-native-restart-current.md).

- [x] Current copy/loyalty execution and public replay-context corrections:
  39 whole modules / 1,061 passes, 683.18s, original assertions and inputs
  preserved, source hashes and native resource closure verified. Protected
  trace delivery, complete remote CI, canonical Daretti and all original release
  requirements remain separate. [Scope and histories](docs/testing/ci-copy-public-parity-current.md).

- [x] Strict sideboard core entry/quantity validation and per-card inventory
  conservation: three whole modules / 49 passes on fresh isolated SQLite.
  Public quantities were already strict; internal coercion is now rejected.
  Seeded native interactive BO3 is qualified in the checkpoint below;
  the original full50 browser cohort now also completes natural series on
  `d65791a`. Other actions and policy-strength acceptance remain open.
  [Scoped acceptance](docs/testing/sideboard-quantity-current.md).
- [x] Shared creature self-tap readiness and effective haste query guard:
  eight whole modules / 277 passes. Separate unchanged canonical Scout/Atlas
  plus decline hook: 48 passes. Scope: [tap readiness](docs/acceptance/tap-source-readiness-20261006.md).
- [x] Private optional hand-land selection/decline, supported paid optional
  trigger costs, retained source self-pumps and generic hand-land ramp roles:
  27 complete modules / 800 passes, 390.20s, plus a separate whole-view audit
  of 25 passes. Frontend tests/lint/build pass. Scope:
  [shared composition](docs/testing/optional-paid-current-composition.md).
- [x] Unchanged supplemental bare-helper and actual paid-cast HTTP regression:
  eight passes, 18.78s; cold restart and atomic immediate sick-tap rejection.
  Scope: [HTTP supplement](docs/testing/activated-handland-paid-sickness-supplement.md).
- [x] Supported nontoken entry observers, unconditional global flash permission
  and deck-identity opening-quality metrics: ten whole modules / 293 passes,
  60.41s. [Current composition](docs/testing/observer-flash-simulator-current-composition.md).
- [x] Fixed source counter costs and supported complete targeted basic-land
  searches: 22 whole modules / 749 passes, 85.34s; separate prior-feature gate
  293 passes, 56.61s; frontend checks pass.
  [Current search composition](docs/testing/counter-targeted-search-current-composition.md).

These gates overlap. They are not one summed full-suite run, an expert-AI
measurement, live deployment, or universal MTG certification. The historical
plan links earlier hydration, face, actor, replacement, graveyard, combat,
knowledge, replay and frontend milestones without recertifying them here.

## Current Parallel Backend Batch

The workers use immutable published source, disjoint ownership and surgical
patches. Parent composition must preserve newer source and qualify interactions.

1. [x] Compound source counter costs: integrate fixed positive source +1/+1
   and charge removal with mana/tap costs. Preserve shared readiness, reservations
   and source references; reject unknown composite costs in full. Adapt obsolete
   unsupported-cost characterizations separately; retain genuine search failures.
2. [x] Generic creature observers: first distinguish already-supported cast
   clauses from missing nontoken entry admission. Preserve copied-spell behavior,
   ability suppression, controller predicates, optional choices and source LKI.
3. [x] Historical deck provenance: preserve existing IDs/template identities,
   verify historical event records and canonical import facts. Historical success
   is not current format legality or a promise that an old deck is competitive.
4. [x] Global as-though-flash permissions: implement generic continuous timing
   grants with controller, ability suppression, departure and prohibitions.
   Do not grant extra land plays, off-turn loyalty or override card restrictions.
5. [x] Targeted library-search compilation: complete anchored instruction
   grammar with explicit targets and existing filters; preserve canonical cards
   and reject unsupported suffixes without partial rewards.
6. [x] Targeted search resolution: separate original effect controller from
   library/choice owner; private fail-to-find, actual selected-card validation,
   destination/entry handling and genuine shuffle causality through restart.
7. [x] Compose the completed slices once, run affected whole-module and cross-
   family gates on captured unchanged source, fix failures, refresh docs/Graphify,
   archive verified evidence and publish the qualified milestone.

Checked items are complete only for the scoped families in their linked
acceptance reports. Conditional timing/observer grammar, arbitrary search/cost
clauses and broader source-departure/continuation episodes remain open. Catalog
provenance and canonical seed now have current scoped acceptance in
[catalog composition](docs/testing/catalog-canonical-seed-current-composition.md).
Full corpus, lifecycle and release acceptance remain unfinished.

## Next Backend Batch

### Current Evidence-Driven Priorities

- [x] Repair Ray's actual-resolution-controller and superseded temporary-control
  cache bugs; retain physical announcing provenance separately from the actual
  popped copied-spell frame. Current composition passes 199 pure checks, then
  322 checks across 17 whole isolated-SQL modules and 12 dedicated HTTP cases.
  The eight actual desired copy cases pass unchanged. Preserve delayed-trigger
  priority, counterability and immutable historical ledgers. The later corrected
  Ray149 v6 gate passes all 149 checks on its separately pinned component; it is
  not a qualification of the current full backend. General control layers and
  full browser games remain open.
  [Current acceptance](docs/testing/control-source-frame-current-composition.md).
- [x] Qualify bounded temporary characteristics through checked HTTP actions and cold
  SQLite restore. Published `7dfbd51` passes seven whole pure modules / 232 checks;
  the exact parent source-only HTTP copy passes all 40 checks, including eight
  cold-process continuations and actual native-turn mana activation. Broader
  layers/copies remain open. [Current acceptance](docs/testing/suspend-and-characteristics-http-current.md).
- [x] Align bounded fixed-cost Suspend readiness with runtime admission and
  canonical context, not a name allowlist. Frozen7f audit: 61 passes / six
  blanket-warning failures; variable costs, unknown layouts/clauses and legacy
  context-free callers remain conservative. Current composition passes four whole
  modules / 136 checks. Do not declare whole decks ready or general Suspend complete.
- [x] Execute bounded printed exile time-counter bodies independently of the
  Suspend keyword: canonical Aeon draw and Detritivore land destruction use real
  trigger priority, targeting and retained object references. Parent current-source
  acceptance passes 403 cases across 17 whole modules, preserving graveyard-cast
  receipts. Multi-counter removal, unknown clauses/layouts, HTTP and whole-card
  readiness remain open. [Acceptance](docs/testing/exile-counter-current.md).
- [x] Integrate bounded canonical Soul-Scar conversion into affected-player
  replacement ordering, prevention and re-evaluation. Current source-controller,
  numeric-prevention and heroic union passes 1,133 checks across 46 whole modules,
  including original replacement/query and hydrated preflight action witnesses.
  Complete-clause diagnostics and native damage-source validation are included;
  this is not arbitrary replacement-clause or browser-game certification.
  [Current acceptance](docs/testing/source-controller-heroic-current.md).
- [ ] Establish complete graveyard clause/zone/permission inventory before
  broader relaxation of conservative combat leaves. Current bounded inventory,
  canonical self-return and public combat cohorts pass 323 checks across four
  whole modules; the older zone and 40-failure ledgers are historical, not current
  defects in this cohort. Arbitrary clauses, layouts and AI strength remain open.
  Absence of offered moves is not proof of inertness. Preserve hidden information.
  [Current acceptance](docs/testing/graveyard-combat-current.md).

These are distinct frozen audit and current-composition ledgers, not a summed
suite. Soul-Scar and Suspend audits used no SQLite/network; an earlier natural
App attempt stopped at preflight with zero match-start/action requests. The
later original full50 browser cohort completes on `d65791a`; this does not
qualify arbitrary decks or later engine compositions. Searing Blaze has
  [actual paid-entry witnesses](docs/testing/linked-damage-real-land-entry.md):
  four whole current modules / 146 passes; broader admission/copy/target coverage
  remains under investigation. No unsupported-warning bypass or natural-game retry is
authorized by these scoped repairs.

1. [x] Qualify phase-aware tactical combat scoring against actual checked
   damage/winners, preserving response and crackback uncertainty. Tactical
   fixtures are not a natural-game strength measurement.
   Scoped animation composition: 64 focused passes; natural previous-stage
   actions remain identical. Broader blocking/crackback planning stays open.
2. [ ] Audit and implement canonical land-animation admission and continuous
   characteristics, including summoning sickness, cleanup and source incarnation.
   Product and real Cloudshift reentry execute. Complete single-target
   nontoken-permanent Flicker now passes 78 core/HTTP cases in the current
   whole30 composition. Ghostly Flicker's two-target body remains unsupported;
   old exile-only and empty-pool characterizations require separate reconciliation.
   [Current scope](docs/testing/animation-strategic-current-composition.md).
3. [ ] Verify targeted search source departure/reentry and partial target loss
   through actual response spells, private choices and cold restart.
   Supported ordinary activation/bounce reference retention is now qualified;
   [current acceptance](docs/testing/retained-reference-current-composition.md).
   Immediate exile/return and independent clause binding now execute in the
   [current stage](docs/testing/blink-clause-exporter-current-stage.md). Shared
   announced-target identity now closes four original Favor blink cases and
   two Act blink cases unchanged. Current whole30 integration executes 730 cases,
   including all 62 Favor lifecycle/HTTP/clause checks passing. Browser,
   Ray of Command and dedicated activation paths
   remain open; see [target acceptance](docs/testing/announced-target-current-composition.md).
4. [x] Audit full 155-record seed regeneration for non-lossy canonical and
   approved derived facts, without weakening the historical 119-record fixture.
   Eight whole modules / 194 passes; real CLI idempotence and unchanged SQL.
   Cross-file interruption/recovery remains separate release work.
5. [x] Resume deterministic natural play only after storage checks; preserve
   failed resource-exhaustion runs separately from gameplay outcomes.
   Before/after seat-swapped replay has zero deterministic failures; all 2610
   recorded action entries are identical. No AI-strength improvement is measured.

## Gate 1: Reliable Local Human Playtesting

Existing implementations have scoped evidence in the historical plan. Remaining
items below require current-source acceptance, not another rewrite of working
features or claims based on helpers alone.

1. [ ] Requalify canonical hydration/views across live API, sideboarding,
   simulation and replay. Faces, effective stats/keywords, counters, damage and
   characteristic values must agree with combat and survive reload/restart.
2. [ ] Complete interacting draw/discard replacement, cleanup, repeat-cleanup,
   trigger-order and human replacement-choice fixtures through actual HTTP/UI.
3. [ ] Complete full human-vs-human and human-vs-AI browser games: both seats,
   mulligans, ordered bottoms, phases/priority, target/face/mode/resource choices,
   activated/crew/equip/zone plays, combat, cleanup and game completion. Every
   supported action must be reachable; unsupported controls must warn explicitly.
   One historical actual-App attempt with Mono Red Aggro versus Burn stopped at
   support preflight: Soul-Scar Mage counter replacement, Rift Bolt suspend,
   and Searing Blaze linked targets/conditional land-entry damage were flagged.
   There was one preflight POST and no match/action POST; no warning bypass or
   complete-game claim for that attempt. The later original full50 cohort on
   `d65791a` completes all declared episodes, including natural human-vs-human
   and both human-seat AI BO3. Every supported action and remaining rules gaps
   still need acceptance; see `docs/testing/current-d657-native-browser50.md`.
4. [ ] Requalify malformed/stale/wrong-actor requests across new actions with
   full state/controller/SQLite equality on rejection, including failed writes.
5. [ ] Complete refresh, backend restart, ambiguous timeout and manual/autoplay
   overlap acceptance. Reconcile before retry; preserve revisions/idempotency.
   Published checkpoint browser evidence covers refresh, a lost accepted HTTP
   response, duplicate land intent and real backend restart. The original
   full50 now also completes its declared recovery and natural series.
   Broader overlap and restart paths remain acceptance work.
6. [ ] Verify seeded interactive BO3 transitions, loser play/draw selection,
   sideboard inventory and restart parity. Implement deliberate AI sideboarding
   or label it unavailable, never silently substitute an untested policy.
   Current441 native/API acceptance now passes eleven whole modules / 100
   cases, including real three-game human series, deliberate different-card
   swaps, play/draw readiness and cold restoration. Controls callbacks and
   frontend checks pass. The later original full50 completes three actual
   browser BO3 series; broader sideboard policy strength remains open.
   See `backend/docs/testing/human-bo3-readiness.md` and
   `docs/testing/current-d657-native-browser50.md`.
7. [ ] Run clean-checkout offline assets, API/runtime contracts, frontend tests,
   lint/build and the configured browser flow without developer-only cache files.
   Current441 cold ASGI fallback qualified all 155 shipped names without
   network access, followed on the same database/cache by eight whole warm
   modules / 73 passes. Prior pinned-source harness failures remain immutable.
   See `docs/testing/offline-assets-cold-component.md`. Later compositions,
   actual browser/proxy fallback and full clean-checkout release remain open.

Exit: reliable supported-card local human games and BO3/recovery work through
actual UI/API, with no silent legal-action gaps or unexplained internal errors.
UI redesign is later; functional access to backend choices is not optional.

## Gate 2: Rules, Knowledge And Competitive AI

1. [ ] Maintain a provenance-backed supported corpus with faces, rulings,
   legalities, image/token metadata and explicit mechanic/effect-clause gaps.
   Complete all-card sync/cache coverage separately from semantic certification.
2. [ ] Expand reusable effect/ability handlers and modular unusual-card support.
   Verify static/triggered/activated abilities, replacements and prevention,
   continuous layer/timestamp/dependency fidelity, can't overrides, ownership,
   incarnation/LKI, simultaneous events and durable choice continuations.
   Admitted temporary creature-characteristic bodies and effective subtype
   readers now pass 232 pure checks on the current composition. Printed data,
   counters, real paid spell/response outcomes and cleanup/reentry are covered;
   actual HTTP/cold SQLite qualification remains outstanding.
   Next observed corpus seams: noncombat damage-to-counter replacement,
   suspend/free-cast continuations, and controller-linked conditional damage.
   Preflight flags are evidence of admission gaps, not by themselves proof of
   failed effect execution; canonical action goldens must establish each cause.
3. [ ] Expand canonical fixtures for combat/protection/landwalk/multiple blockers,
   damage/deathtouch/trample/first strike, bands, mana and restricted costs,
   legendary/planeswalker rules, tokens, graveyard/exile/library interactions,
   alternative win/loss, empty-library draws and uncommon historical mechanics.
4. [ ] Make knowledge affect production AI decisions and trace why. Validate
   actual decisions across aggro, burn, midrange, control, tempo, ramp, drain,
   aristocrats, reanimator, tokens, tribal, combo and interaction-heavy decks.
5. [ ] Improve combat/racing, blocking, resource reservations, removal/counter
   timing, threat assessment, mana efficiency, mulligans, dynamic faces and
   multi-turn planning. No blind attack, power-zero or named-card policy fixes.
   Intrinsic-mana dual-land combat admission is composed: 225 pure checks pass.
   The historical 316-case cohort retained 40 graveyard decision failures.
   Current schema drift was reproduced in four whole modules / 323 cases as
   269 passes and 54 failures. Explicit reviewed metadata coverage now passes
   all 323 unchanged cases plus 104 new boundary controls (427 total), without
   weights/depth or hidden-information policy changes. Natural-game strength
   and final composed-source qualification remain open; see
   `docs/testing/public-graveyard-reviewed-context.md`.
6. [ ] Define decision-quality benchmarks and before/after comparisons under
   hidden information. Training/data tooling needs legal-action traces, causal
   anomalies and evaluation; storage or a neural net alone does not prove skill.
7. [ ] Run predeclared seed/seat-balanced archetype matrices with full hand/board
   and decision traces, uncertainty intervals, timeout/deck-out policy and
   first-diverging replay diagnostics. Verify API/simulator/restart parity.

Exit: no unexplained cost/target/rules stalls in the declared supported corpus,
reproducible replay, and measured AI decision improvement across deck styles.
Continue expanding toward full rules and arbitrary-deck seasoned-player strength;
the supported-corpus exit does not redefine that larger goal as achieved.

## Gate 3: Packaged Release And Operations

1. [ ] Requalify actual built HTTPS API/media routing and explicit cross-origin
   configuration, then trusted-certificate LAN deployment on supported topology.
   The isolated `eb8d8805` loopback H1/H2/auth/media/restart component now passes
   all 547 observed check instances with actual native closure. LAN deployment,
   final browser and clean-machine trust acceptance remain outstanding; see
   `docs/testing/caddy-operator-current-acceptance.md`.
   Later immutable `3f512cd0` adds complete assigned-RFC1918 THISHOST native
   H1/H2/auth/body/media/restart acceptance: all537 observed checks, source/pins
   before/end equal and independent physical closure. It does not close this
   checkbox: remote-client routing, Chrome/Brave/Firefox/manual trust,
   clean-machine and final combined-source acceptance remain outstanding.
2. [ ] Document/enforce local single-user/single-worker limits. Before broader
   exposure, add authorization, restricted origins and measured resource limits.
3. [ ] Complete bounded job admission/queues, cancellation, byte/row retention,
   crash/restart recovery and stale concurrent mutation acceptance. Existing
   single-process controls are not distributed-worker certification.
4. [ ] Review current frontend/backend dependency advisories and compatible
   upgrades; run clean installs, dependency consistency/security checks and gates.
5. [ ] Verify clean-machine install, offline fallback, backup/restore, saved-game
   reconstruction, long-session browser soak, accessibility and actionable errors.
   Two-output seed export needs explicit restart recovery: the real 12-case
   fault audit has eight passes and four immediate-publication failures. A local
   rollback-journal/recovery implementation now passes 245 checks across ten
   modules, preserving original bytes without source inputs and refusing
   altered outputs. Real SIGKILL/new-process recovery is covered. Recovery is
   not atomic two-file visibility, and the stricter historical failures remain.
6. [ ] Reconcile features/limitations with current source, record changed files,
   checks, evidence, risks and manual review; publish and deploy only after the
   appropriate gates pass. Git pushes alone are not running-server updates.

## Completion Checklist

Current component evidence and remaining acceptance work are reconciled in
`docs/testing/release-acceptance-status.md`. Natural native browser BO3 and the
browser-origin security component have passed on their documented source pins;
neither result qualifies the final combined source or closes all three gates.

The current pending-stack privacy integration has an exact 22-whole-module pure
qualification of 950 passes on the `db16186` composition, with applied-byte
equality. See `docs/testing/pending-stack-privacy-current.md`; mixed HTTP/SQL,
complete private hand-to-library responses and final release remain open.

Current clean-CI fixture repairs preserve canonical/gameplay assertions while
removing an import-time audit-phase requirement, an NFS-only frontend test input
and an undeclared browser-test origin. Eight whole pure modules pass 231 checks;
default backend collection succeeds for 23,431 cases, not a full-suite pass.
The full remote workflow remains required. See
`docs/testing/clean-ci-fixtures-current.md`.

The complete self-entry gain-control trigger now has one nineteen-whole-module
pure composition: 365 ordinary passes, 165.10s, with deliberate public targeting,
actual copied-trigger controller and retained object identity. Static Aura
control remains separate work. See `docs/testing/self-entry-control-current.md`.
The modal legal-moves producer now uses the existing public cost serializer
with selected-face characteristics. One actual twenty-two-whole-module combined
control/modal declaration passes 441 checks in 169.59s with unchanged source
before/after; the unchanged frontend parser accepts the actual canonical packet.
See `docs/testing/modal-cost-view-current.md`. The observed remote workflow on
`00b8c8d4` passed frontend and reached seven browser checkpoints before this
contract defect. A complete workflow on the corrected published composition
remains required; component passes do not establish release readiness.

The published `3b99b96d` workflow passed frontend and 76 browser checkpoints
before a stale game-over test expected play/draw before human sideboard
confirmation. The corrected test requires confirmation, then asserts both
controls remain available. Eight actual readiness renders pass; remote full
browser/backend qualification remains required. See
`docs/testing/browser-bo3-readiness-ci.md`.

The `f64ba88b` frontend workflow also passes; its browser flow then exposed
manual copy fixtures missing native spell/ability-kind metadata. Five fixture
producers now declare that metadata without weakening engine validation.
One fresh 23-whole-module pure declaration passes all 447 checks in 171.09s,
including six red-before/green-after fixture-contract cases. The complete
corrected remote workflow remains required. See
`docs/testing/browser-native-frame-fixtures.md`.

The subsequent `c0528c8e` frontend job passes; its browser table scenario
exposes an incomplete scry continuation and an unsafe fixture-switch readiness
predicate. The test now completes deliberate ordering and checks committed,
idle, exact rendered match identity. Helper red/green, unchanged navigation,
actual native scry continuation, current typecheck and full source lint pass.
The full corrected remote workflow is still required; see
`docs/testing/browser-fixture-handoff-ci.md`.

The `bf9f268e` frontend job passes and its browser flow passes the corrected
scry continuation. It then exposes obsolete checkbox interactions for copy
choices, which the actual UI renders as one-click buttons. Ordinary, divided,
modal, Adventure, ordered, linked and conditional copy tests now use those
buttons while retaining their selected-target and gameplay assertions. Actual
compiled Controls/helper callback regressions pass for both seats; complete
corrected remote browser/backend qualification is still required. See
`docs/testing/browser-copy-choice-ci.md`.

Current native next-cast and entry-counter integration has one 36-whole-module
834-pass qualification on the composed `91c40e2` application baseline. Parent
applied bytes match the actual tested archive. See
`docs/testing/native-entry-current.md`; copied-bind, broader native APNAP,
historical aggregate diagnostics and full release acceptance remain open.

- [ ] All current batch items and all three release gates have authoritative
  evidence for their declared scope, on the actual composed source.
- [ ] Builds/runs succeed and no obvious broken page, action or data flow remains.
- [ ] Manual full-game/LAN/accessibility review and remaining risks are recorded.
- [ ] Original broader all-rules/arbitrary-card/expert-AI objectives are proven,
  or explicitly remain unfinished; do not mark the overall project complete
  merely because the scoped local release is finished.

## Known Limitations and Next Upgrades

Alpha, bounded card semantics and heuristic AI. Full rules coverage, arbitrary-
card correctness and seasoned-player strength are not established. Current
backend work takes priority over cosmetic UI changes. Full-suite, browser/LAN,
long-session, dependency/security and statistical AI acceptance remain open.

## 2026-10-07 Pull and Mass-Exile Checkpoint

Scoped current-base composition repairs mass-exile incarnation/PRE-leave lifecycle
and admits complete Pull from Eternity with retained native frames and explicit
owner replacement continuation. Same-source 26 whole modules: 524 passes; see
`docs/testing/pull-mass-exile-current.md` for evidence and guard limits. Existing
numeric-prevention transport is preserved. This is not a live deployment or a
full backend/game/AI release gate; the completion checklist remains open.

## 2026-10-07 Source-Controller and Heroic Checkpoint

Current-base composition adds complete source-controller counter-conversion
clauses, correct spell/ability replacement-query controller projection, early
native damage-frame validation, closed-instruction preflight diagnostics and
actual-reference heroic cast-target recognition. Same-source 46 whole modules:
1,133 passes in 302.49 seconds; original assertions unchanged. See
`docs/testing/source-controller-heroic-current.md` for the earlier harness-only
failure ledger and isolation limits. No live deployment or broader release
completion is claimed; the completion checklist remains open.

## 2026-10-07 Locked Frontend Checkpoint

Fresh isolated locked install, complete configured npm test chain, lint and build
pass on application source `6f9e29e`; full and production-only advisory scans
report zero findings. The missing Python prerequisite on the first attempt is
preserved separately, not treated as an application failure. See
`docs/testing/frontend-locked-current.md`. Backend offline assets, actual browser
games, BO3/recovery and deployment remain open; this does not close Gate 1.7 or
Gate 3 in full.

## 2026-10-07 Fable Linked-Discard Checkpoint

Complete optional self-discard/up-to-N/If-you-do draw-that-many instructions now
reuse the existing private selected-count continuation, including the full Saga
chapter envelope used by admission checks. Parent isolated published-source
qualification: five whole pure modules, 92 passes in 96.18 seconds, with source
hashes unchanged during execution. See
`docs/testing/fable-optional-linked-discard-current.md`. HTTP/SQLite/browser,
Reflection's copy ability and broader release gates remain unverified here.

## 2026-10-07 Native Type-Note Control Checkpoint

The existing mechanic button route now exposes explicit offered creature-type
choices for both seats. Actual backend public views and React-rendered callbacks
pass the configured frontend test chain, typecheck, lint and production build.
See `docs/testing/native-type-note-controls.md` for the fixture failure ledger
and scope. This closes the identified control-routing gap, not manual browser,
full-game, BO3, copied-bind/APNAP or overall release acceptance.

## 2026-10-07 Pinned Offline Warm Checkpoint

The preserved `6f9e29e` backend now has an independently checked eight-whole-
module warm result: 73 passes, exact original node identities, 23 paired
lifespans, strict runtime stub provenance and quiet resource closure. Earlier
cold and failed warm ledgers remain distinct. See
`docs/testing/offline-assets-cold-component.md`. This does not close current-
source offline/browser fallback, full Gate 1.7 or overall release acceptance.

## 2026-10-07 Resource-Scaled P/T Checkpoint

Current native-backend composition now admits the complete named-artifact-token
resource-scaled debuff and resolves its count after actual responses. Five whole
pure modules passed all 103 cases in 81.81 seconds; applied product/dependency
bytes match the tested source and native bindings remain intact. See
`docs/testing/resource-scaled-pt-current.md`. The mixed HTTP neighbor cohort,
broader variable P/T families, browser and full release remain unqualified.

## 2026-10-08 Fresh Runtime And Natural-Game Checkpoint

Fresh isolated installation on immutable `9f50190` completed the configured
frontend checks and the unchanged thirteen-whole-module backend AI/entry cohort:
655 passes in 234.43 seconds. Installation, exact wheel/lock provenance and
native pure-gate closure are recorded in
`docs/testing/current9f-fresh-dependency-runtime.md`. Fresh mixed SQL/ASGI,
HTTPS, browser and clean-machine deployment are still separate acceptance work.

Four predeclared White/Tempo natural games on immutable `349a5d2` completed with
2,832 checked decisions and 8,496 verified checkpoints. All four rows use one
correlated seed; one existing bad-block diagnostic remains recorded. Its four
checked immediate-combat alternatives do not establish strict domination; see
`docs/testing/current349-block302-causal-review.md`.
See `docs/testing/current349-white-tempo-natural-four.md`. These rows do not
establish thirteen-style, multi-seed or expert-strength acceptance.

Published `1c3fbbd` repairs the App response-window prerequisite to use the
actual human controller rather than seat 1. The actual-source 36-check regression
and candidate frontend checks pass. Live both-seat countdown/pause/pass behavior
still needs affected browser qualification; see
`docs/testing/human-response-controller-role.md`. None of these components closes
the full release gates or the original full-rules/arbitrary-deck objective.

## 2026-10-08 Fresh HTTPS Checkpoint

Immutable `1c3fbbd` with the exact tested frontend build completed actual
owned-CA loopback HTTPS/auth/Origin/API/media/lock/restart qualification on the
restored fresh runtime. All 205 reported instances pass: the same 111 stable
contract instances as the older gate plus 94 process-identity polls. Independent
source, dependency and native resource closure verified the slot release. See
`docs/testing/current1c-fresh-https-qualified.md`. Live browser, trusted LAN,
clean-machine deployment and the full release gates remain open.

## 2026-10-08 Complete Printed-Body Composition

The isolated composition over `6c5c62b` passes 823 checks across 22 whole modules;
all 400 original corpus/consumer cases pass unchanged. Shared cast preflight now
rejects unsupported complete bodies before payment, and shipped loyalty ability
availability is restored through complete instruction compilation. Raw energy,
Aura, land-setting, untap-preview and target-fizzle fixes compose together.
Separate resolution/entry neighbors pass 179 checks across seven whole modules.
See [scope and historical ledgers](docs/testing/complete-body-rules-composition.md).

Ten historical loyalty fixtures assumed unsupported casts would succeed; their
unchanged early-rejection ledger is preserved separately from the strengthened
repository checks. General hand-entry/Aura/land-choice interactions and public
emblem visibility are explicit follow-ups. Full browser acceptance, arbitrary
cards, expert AI and all three original release gates remain open.

## 2026-10-08 Locked Dependency Advisory Refresh

Exact published `bf6731c` Python/frontend locks were queried against OSV at
23:24:27 UTC: all 28 PyPI and 214 npm unique locked versions, including optional
platform packages, returned no affected package. Exact inventory, input hashes,
response cardinality and absent pagination were independently verified. See
[the advisory scope and evidence](docs/testing/current-locked-dependency-advisories.md).
This changes no dependency and does not replace final-source clean installs,
runtime gates, application security review or deployment qualification.

## 2026-10-08 Loyalty Entry And Public Emblems

The current-source composition over `8b2078c` executes 31 whole backend modules:
1,003 passes in 183.20s. Pytest exits zero; the wrapper's separate inventory
assertion exits one for four generated SVG cache appends, with every original
inventoried source path unchanged. Exact output hashes and the failed wrapper
ledger remain preserved. Complete configured frontend test/lint/build exit zero.
Actual paid Ugin land/Aura/planeswalker entry and public command-zone emblems
now have existing-pattern human selection/display controls, strict response
validation and both-seat component checks. See
[the scope, ledgers and remaining work](docs/testing/loyalty-entry-emblems-current.md).
No HTTP/browser, arbitrary entry rules, expert AI or final release gate is
certified by this scoped composition.

## 2026-10-09 AI Loyalty And Replay Input Safety

Composition over `9d519b5` passes the same 13 declared whole modules: 392 passes
in 62.19s. Actual AI uses live offered loyalty card/Aura references and the
correct distinct choice fields. Replay artifact paths reject equal, symbolic
and hard-linked aliases before simulation or evidence creation. The corrected
baseline reproduced 15 unsafe alias cases; the first combined run's 26 denied
repository-fixture setups remain archived separately. Only declared owned SQL
fixtures were subsequently admitted, with source equality and physical closure.
See [scope and evidence](docs/testing/ai-loyalty-replay-artifact-safety.md).
This is conservative legality and artifact protection, not optimal AI,
13-archetype natural-match evidence or completion of any original release gate.

## 2026-10-09 Bounded Spells And Entry Strategy

Current composition over `9b86ca2` passes 30 whole modules / 981 cases in
177.82s, retaining the original 400 corpus/consumer nodes and assertions.
Full frontend test/lint/build passes. Complete bounded removal uses retained
target references; malformed linked/X-token bodies reject before payment even
with embedded unknown parentheses or leading whitespace. Human target drafts
respect the offered maximum and clear stale scalar fields. Actual AI compares
known Aura-entry and decline outcomes at the same completed stack boundary.
See [scope and preserved baselines](docs/testing/bounded-spells-and-entry-strategy.md).
This does not certify alternative pitch costs, noncreature copy/retarget paths,
full browser acceptance, maximum-width planner latency or seasoned-player AI.
All original release-gate requirements remain unchanged and open.

## 2026-10-09 Ordered Copy Targets And Acceptance Harness

Composition over `1a73e6b` passes the same declared 35 whole modules / 1,129
cases in 247.46s, including six existing owned-SQL HTTP fixtures. All original
400 ordered corpus nodes and 981-case modules remain unchanged. Public ordered
copy candidates include authoritative noncreature card surfaces; actual paid
Force/Twincast and blink responses preserve keep/refresh identity in both seats.
Full configured frontend test/lint/build passes.
See [scope and preserved ledgers](docs/testing/ordered-copy-current.md).
The NEW reusable browser harness is syntax-checked, not runtime-qualified here.
Current full browser, 13-style strategy and all original release gates remain open.

## 2026-10-09 Original Full50 Browser Checkpoint

Published `d65791a` completes the unchanged original 50-episode browser cohort
in 1,149.532s: paid40, recovery3, origin4 and three natural BO3 series, including
both human seats versus AI. The reviewed helper correction follows genuine
native revision advances rather than fabricating pass actions. All tracked
source and pinned runtime inputs remain equal; independent resource closure
and SQL release are verified. See
[scope, preserved failures and evidence](docs/testing/current-d657-native-browser50.md).
Every supported action, broader rules/corpus semantics, measured seasoned AI,
final HTTPS/LAN/clean-machine/soak acceptance and the original completion
checklist remain open. This is not overall release completion.

## 2026-10-09 Granted-Target, AI And Loyalty Checkpoint

Surgical composition over `8b56b3a` adds bounded generic recipient-bound target
triggers, publication-before-callback quota/receipt handling, count-only AI
attachment forecasts and explicit public loyalty permanent/X choices. The
repository runner executes fourteen complete modules: 265 passes in 154.86s,
including unchanged original equip/attachment checks, exact actual copied
StackItems/quota deltas and the shared opaque-conditional simulation frontier.
Known-card resolution, first priority passes and real offered responses remain
executable without fabricating unknown hand cards. The original productive-equip
assertions are unchanged. Earlier whole140 and strict counterexample ledgers
remain separately archived. All source/runtime/seed/RNG/resource checks pass.
Twenty actual compiled loyalty handlers replay successfully on the integrated
backend; the full configured frontend suite, lint, types and build pass.
See [evidence and limits](docs/testing/granted-target-ai-loyalty-current.md).

The original paid24 assertion/helper/recipe bytes are retained with their
historical input failures; two explicit opt-in reentry seed inputs have a
separate qualified ledger. Four original Tibalt admission failures remain open
and strict. The 13-style ordinary-equip controls are not a statistical strength
evaluation. New loyalty mounted-browser and current-composition natural-game
qualification remain next work; old browser50 cannot be transferred. Full
rules/corpus/arbitrary decks, expert AI and all three release gates remain open.

## 2026-10-09 Source-Linked Exile And Opaque Acquisition

The composed source-linked loyalty/emblem permission, physical colored-mana
substitution and foreign-owned land-control implementation passes 398 checks
across 21 whole modules on the `c7fc760` baseline. The AI stops before opaque
library acquisition inside the actual effect sequence, rather than creating
placeholder exile permissions. Its unchanged eight regressions first produced
six failures and two passes, then all eight passed after the AI-only correction.
Repository-native packaging separately passes 133 checks across seven whole
modules; all original assertion ASTs and canonical fixture bytes are retained.
Parent production/test postimages match those tested bytes. These overlapping
counts are not a summed full-suite run.
See [component evidence and limits](docs/testing/source-linked-exile-current.md).

The four original Tibalt admission cases now pass in this composed native cohort;
the previous checkpoint remains their historical ledger. Aura control,
self-entry control, dependent artifact/type layers, current permission HTTP and
cold restart, mounted-browser acceptance, natural games and measured expert AI
remain open. The separate original 509-case HTTP-neighbor attempt executed 506
ordinary passes and three pytest-symlink setup errors, not a complete green gate.
All three release gates and the original full project objective remain open.

## 2026-10-09 Static Aura Control-Layer Integration

The aggregate prepared over `bf9f268e` applies once over `58c34d09`, whose
complete backend tree is independently identical. Subsequent independent review
corrects actual-change dependency admission, per-effect reevaluation and external
prerequisite ordering inside loops. Final isolated verification passes seven
whole modules /127 cases in 276.35s, with source equality and no native gameplay
I/O attempts. Historical 73/619 ledgers retain an incorrect authored three-Aura
golden; its corrected expectation and the new 54 regressions are explicit.
No preexisting committed test was replaced; no exclusions or xfails were used.
See [scope, evidence and snapshot compatibility](docs/testing/static-aura-control-layer-handoff.md).

Current copy-choice browser episodes execute successfully; complete Tamiyo
body support blocked the subsequent browser checkpoint on `58c34d09`. The permission
HTTP component separately passes all 16 cases after its phase-helper correction,
with actual closure/lease release. The older backend CI ends in disk exhaustion
and retains earlier unresolved failure markers. Final whole CI, current mixed-I/O/browser,
snapshot migration, full corpus, measured expert AI and every original release
gate remain open; no live deployment or release-complete status is claimed.

## 2026-10-09 Complete Loyalty And CI Publication

- [x] Implement the full canonical loyalty bodies without card-name shortcuts,
  preserving native costs, references, entry/legend and explicit copy choices.
- [x] Qualify copied-Aura/underlying-control interactions with the final static
  layer: one actual 38-whole-module union /1,001 passes, 501.55s, source equality
  and no bounded native gameplay I/O attempts. Worker870 and cross4 overlap.
- [x] Preserve the private sealed regression through protected CI input rather
  than publish it. Qualify strict ownership, decoder, cold-worker boundaries,
  assertion privacy and all49 existing private-damage cases: three whole modules
  /86 passes, 28.06s, including six independently corrupted protocol controls.
  Full BO3/CLI/packaging episodes remain remote prerequisites.
- [x] Qualify named unfiltered CI reporter parity and real failure/interrupt/
  evidence-write/ENOSPC handling. Keep all old workflow failures visible.
- [ ] Publish this composition and verify the complete configured remote
  backend/frontend/browser jobs. Do not infer a full-suite result from collection,
  anonymous progress, generic canaries or component passes.

See [rules composition](docs/testing/tamiyo-aura-current-composition.md) and
[CI inputs/diagnostics](docs/testing/backend-ci-inputs-and-diagnostics.md).
Broader final-source migration, mixed I/O, AI quality, operator/proxy,
clean-machine and soak requirements above remain unchanged.

## 2026-10-10 Officer Fixture Admission

The `daa644c7` browser executes three natural BO3 component checks and all 12
original interactive-preflight checks, then stops at Officer's first action:
HTTP 503 from the absent database owner. The fixture now enables the native
lifespan and configures its exact owned database before persistence imports;
production admission and shutdown rules are not bypassed.

Two whole pure source-protocol modules pass 42 checks in the worker (0.76s) and
independent parent (0.74s). A separate shutdown test-helper correction includes
the actual retired-job helper without changing original assertions. Real native
startup, Officer gameplay/restart, resource closure and full browser acceptance
remain required. See [scope and evidence](docs/testing/officer-fixture-lifecycle-current.md).
All original gates, measured AI quality and the broader full-project objective
remain unchanged and unfinished.

## 2026-10-10 Officer Browser Origin And Passive Diagnostics

The completed `d89e18a3` browser reaches Officer's eight HTTP/privacy passes,
then the mounted App cannot fetch because the dedicated port 15237 is absent
from its launcher origin configuration. A one-line exact-origin export retains
production policy and passes three whole pure modules / 108 cases (0.26s),
after four new regression failures. A subsequent unchanged native Officer cohort
passes all eight HTTP/privacy and four mounted-browser scenarios, including
actual backend restart. All1988 source hashes match and scoped owned resource
closure is verified. This is Officer acceptance, not the entire browser gate.

The private opt-in CDP observer passes 31 independent protocol controls and
both original navigation checks. Default driver bytes, package/cohort/actions
and clocks are preserved; coverage completeness is not gameplay completion.
See [scope and evidence](docs/testing/officer-origin-and-passive-browser-current.md).
All original release gates and the full-rules/arbitrary-deck/expert-AI objective
remain intact.

## 2026-10-11 Two-Target Blink And Terminal Fixture Evidence

The reviewed Ghostly-compatible batch retains real target/copy object identity,
commits simultaneous entries and counters before collectors, and materializes
the advertised two-permanent AI choice. Its current 14-whole-module component
passes 363 cases in 81.29 seconds; all original neighbor tests remain unchanged.
Test-only terminal HTTP fixture archiving passes a separate parent 21-case pure
gate. Eight old strict legacy restart-hash failures are retained and independently
reproduced on their unchanged preimage, not hidden by cleanup or counted as green.
See the current blink and terminal-fixture evidence documents in `docs/testing`.
Protected CI input, full backend qualification and all original release gates
remain required. These are bounded correctness/retention changes, not a measured
expert-AI or arbitrary-card support certificate.

## 2026-10-12 Missing Sources And Consumer Restart Epochs

A two-line shared color guard restores missing primitive-source behavior without
weakening protection or replacement selection. The corrected seven-whole-module
component passes 212 cases (163.33s), retaining the earlier strict failures and
subprocess-policy ledgers. Separately, consumer10/new HTTP4/restart-contract53
pass 67 cases (95.85s): actual cold epoch changes are proved before a new raw SQL
baseline, exact saved game/controller bytes and all 26 original assertions remain.
See [scope and evidence](docs/testing/ci-missing-source-and-consumer-epochs.md).
All original release gates and measured AI quality remain required and unfinished.

## 2026-10-12 Explicit Favor Cold Test Inputs

The cold ASGI test now binds source and owned data explicitly instead of depending
on an inherited audit-root environment. All original 18 caller assertions and
the ASGI body are preserved. Independent parent original16/new8 pass all 24
cases (47.36s); two generated cache SVGs are separately recorded, not published.
See [scope and evidence](docs/testing/ci-favor-cold-launch-inputs.md).
Hosted backend qualification, all original gates and measured AI quality remain open.

## 2026-10-12 Pytest Subreport Completeness

The `7c711d23` hosted backend finishes with pytest exit zero and no failed test
phases, but its evidence audit rejects 15 duplicate call records. Actual pytest 9
reproduction establishes that these are `SubtestReport` observations from two
collected unittest methods, not repeated executions. The prospective correction
preserves every subreport in a separate ledger and public, context-free metadata
array. Ordinary duplicate-phase checks remain strict; failed subreports still
veto successful qualification.

The complete 153-check script cohort passes on the isolated correction. Parent
verification records 151 passes and two existing cleanup-control failures; both
reproduce on the exact pre-correction source when the unchanged five-second
`fuser` check times out. Backups remain safely retained. No cleanup timeout or
assertion is weakened. See [subreport scope](.github/scripts/ci_backend_subtests.md).
The next hosted composed-source qualification, original Gates 1–3, full rules and
measured expert AI remain unfinished.

## 2026-10-12 Safe CI Timings And Current Fixture Contracts

The safe metadata reporter adds bounded, public-definition-verified numeric
phase timing without raw logs or private parameters. Independent parent script
verification passes all 146 checks. Separately, current combat/Suspend fixtures
pass 109 checks and token packaging passes 7 checks plus 15 URI subtests. Explicit
obsolete expectation adaptations are documented; gameplay production is unchanged.
See [scope and evidence](docs/testing/ci-timings-combat-and-media.md).
The completed `8fff3117` backend cohort has zero setup failures but 58 call
failures, so it is not green. Current whole-backend qualification, all original
release gates and measured AI quality remain open.

## 2026-10-12 Full Vraska Rules Acceptance

The complete canonical three-ability body now uses generic loyalty, combat-trigger
and player-loss handlers. The public package and fifteen whole pure neighbor
modules pass376 (163.90s); the final source separately passes all119 persistence,
ASGI and serializer cases (186.39s). A reviewed animated-recipient gap has a
both-seat failing-before/passing-after regression. All original three-ability
text is retained; no card-name AI branch or partial body admission is substituted.

The old unsupported-card diagnostic receives an explicit admission/cost/atomicity
adaptation, not an exclusion. Fixtures use declared initial boards and mana;
selected animation/protection/blink seams are controlled rather than certified
paid spell episodes. These component results do not close whole-backend CI,
strategic AI quality or any remaining original release gate.
See [exact scope](docs/testing/vraska-full-current-acceptance.md).
