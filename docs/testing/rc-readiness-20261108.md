# RC Readiness: November 8, 2026

Status: **unfinished**. The requirements remain the three gates in
[the finish plan](../../plan.md), the five-phase
[AI/data plan](../plans/2026-09-09-ai-knowledge-base.md) and
[roadmap issue #2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2).
This audit does not reduce that scope to the checks executed below.

## Candidate And GitHub State

The isolated branch `rc/ready-20261108` starts at
`bcfc73380d58c2e1ee039cd060e52b3ba151feb0`, the published head of
[PR51](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/51).
Its ancestry includes the UI, app-checkpoint, final-view, native policy and
observer changes in PR45--51. GitHub main is
`8f03cafccf5e0ab8568774c29fa652581641b0e3`; it is an ancestor with 157
candidate commits ahead and no main-only commits at this observation.
GitHub repository metadata reports zero forks; the outstanding work is in
branches and PRs. The older `mtg-deck-testing-lab` checkout is not current.

The connector independently reports all eight jobs successful in
[PR51 run 42406261862](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/42406261862):
frontend, browser, backend-reference, four backend workers and backend aggregate.
This is hosted CI on that candidate, not a local native Forge execution or a
qualification of later changes.

The migrated source worktree remains untouched. Comparing every public
candidate blob outside `graphify-out` finds 4,989 identical files, three files
with different bytes (AI status and the two runtime-profile modules), and twelve
absent observer-package/documentation paths. The new checkout supplies the
published versions without overwriting migrated work or private data. This is
a public-file comparison, not a claim that every ignored/private file is backed
up or semantically reconciled.

## Fresh Local Checks

These are separate executions on the published candidate, not a single total:

| Check | Observed result |
| --- | --- |
| Three whole backend modules: `test_native_forge.py`, `test_native_forge_persistence.py`, `test_native_forge_checkpoints.py` | 110 passed, 57 passed subtests; 12.17 seconds |
| Two whole stdio modules: `test_checkpoint_store.py`, `test_checkpoint_causal.py` | 121 passed, 312 passed subtests; 0.88 seconds |
| Whole `test_runtime_profile.py` module | 48 passed; 0.304 seconds; synthetic profile shapes |
| Six `forge-session*.test.mjs` modules with in-process Node test isolation | 51 passed, zero failures/skips; 0.313 seconds; synthetic UI/transport |
| Frontend lint and production build | Both exit zero |

Backend commands use `/home/nick/MTG/backend/.venv/bin/python -m pytest -q
-p no:cacheprovider` and the complete named modules. Storage tests are under
`tools/engine_evaluation/forge/stdio/tests/`; owner tests are under
`backend/tests/`. Profile checks use `python3 -B -S -m unittest discover -s
tools/engine_evaluation/forge/native-ai -p test_runtime_profile.py`.

Frontend commands are `npm run lint`, `npm run build`, and
`node --test --test-isolation=none --experimental-strip-types
tests/forge-session*.test.mjs` in `frontend/`. The last command retains all
51 named tests and assertions but changes process isolation; it is component
evidence, not the canonical full package test chain. A separate direct
checkpoint-module invocation also reports its 14 tests passing; those are
included in the 51, not additional tests.

Dependencies were reused from the migrated frontend after the offline install
failed. Both source and candidate lockfiles have SHA-256
`8a7ac6872d818c3d860500602f2147aa6b932b6b74eaeba11654779b3196923f`.
That equality does not certify installed package contents or a clean install.

## Preserved Local Failures And Limits

- The canonical `npm test` chain stops at
  `browser-qualified-search-contract.mjs`: Node's default piped child stdin
  produces `EPERM`. A standalone `/bin/true` reproduces it with piped stdin;
  ignored/inherited stdin succeeds. No assertion or fixture was removed.
- The broader four-module backend invocation was interrupted after 110 passing
  cases when the HTTP route cohort stalled. A minimal FastAPI TestClient
  reproduces the stall without application routes. A direct local socket-pair
  send raises `PermissionError(1)`; the captured thread stacks show the portal
  waiting on the event loop. HTTP tests remain unverified locally.
  Subsequent [timer-adjusted ASGI qualification](asgi-timer-qualification-20261108.md)
  runs named whole modules unchanged and supplies bounded current-source HTTP /
  SQLite evidence. The original canonical invocation and its failure remain
  distinct from that adjusted execution.
- `npm ci --offline --ignore-scripts --no-audit --no-fund` fails with
  `ENOTCACHED` for `zod-4.6.7.tgz`. The shell cannot resolve the npm/GitHub
  hosts. No dependency versions were changed.
- A new output directory was declared for the original guarded root26 runner.
  Bubblewrap exits before Java with `Failed to create NETLINK_ROUTE socket:
  Operation not permitted`. The runner then fails reading its absent canary
  receipt. This is a failed setup attempt, zero native tests and zero natural
  games. The original namespace/JNI/kernel guards were preserved.
- Under this sandbox Node's process-isolated reporter exposes file-level
  counts rather than individual subtests. Those six file passes are not used
  as a 51-test claim; the explicit in-process execution above supplies the
  named-test evidence. A deliberately failing sentinel still exits nonzero.

Local logs, source reconciliation and the declared native invocation are
retained privately in `/home/nick/mtg-rc-evidence-20261108/`. Raw private game
traces, models, protected lock files and user databases were not published.

## Operator Source-Artifact Correction

Review found a content-read gap in the immutable-source check: root owner-lock
and recognized capacity-backup files were hashed before preparation eventually
rejected the mismatched copy. Inventory also read unexpected owner-lock names.
The launcher now rejects those source artifacts and encountered unrecognized lock
names before content reads. Recognized private-runtime artifacts and existing
mutable runtime subtrees retain their ownership/type/link checks and content-free
exemptions. No ignored path
was broadened, and clean-source pins remain unchanged.

Four new file-only unittest methods exercise real inventory/preparation and
restart behavior with an audit hook denying opens of explicit synthetic artifact
files. The corrected baseline fixture produced eight failing subtests and no
errors; all four methods pass after the two validation changes. A fifth passing
method separately checks content-free exemption of lock-suffixed files in each
existing mutable runtime subtree. The initial
test draft additionally had one umask setup error, preserved separately. No real
owner file was opened. The original inventory program now passes 13 cases,
including individual source-lock and source-backup rejection, with all original
runtime/link/code controls retained. Eight existing dist-boundary and five
read-only-runtime methods also pass in separate executions. The new module is
wired into the hosted operator file-only stage; hosted qualification of this
change remains outstanding.

The existing supervisor cohort separately passes 20 tests, and hosted-clean
control contracts separately pass 38 methods (including the five read-only
runtime methods). These exercise inert children and controlled files, not native
services or a clean install. Independent read-only review found no remaining
issues in this correction and rechecked the new five-method module and original
13-case inventory program. Overall RC acceptance remains open.

Publication through the GitHub connector was refused at tree creation because
that mutation requires approval while this session's approval policy is `never`.
No branch or PR was created by that attempt, so there is no hosted result for
the correction. The reviewed local commits and an exportable patch are retained;
the successful PR51 workflow remains evidence only for its original head.

A broader operator-neighbor attempt recorded 21 passes and 40 setup errors:
the LAN/config modules require `MTG_CADDY_BINARY`, which was not supplied in
that invocation. That is not a passing config/TLS qualification. The missing
binary setting and original error log remain recorded, without replacing the
pinned-binary tests with synthetic substitutes.

The subsequent pinned-binary intake check finds its documented public build
packet's `/mnt/rchfiles/.../caddy2117-security-build-20261010-bwDTVP` directory
unreadable (`PermissionError(13)`). Scoped workspace metadata searches find
neither an exact-size candidate executable nor the named build packet; the listed
PR51 workflow artifacts contain no separately named Caddy build package. These
lookup results are not a settings/TLS test pass. The exact binary input and its
qualification remain outstanding.

## Evaluator Replay And Live Matrix

The [custom evaluator replay correction](evaluator-lossless-replay.md) records
complete ordered execution evidence alongside the existing quality projection.
Its final whole seventeen-module pure cohort passes 287 tests and 31 subtests,
with zero SQL/network/child operations and all 22 named input hashes unchanged.
An independent review's construction-before-copy finding is corrected and its
59-case affected-module rerun passes. The default legacy trace is preserved;
old compact quality records remain unsupported. This does not close an RC gate.

The [full Master matrix](full-master-matrix-20261108.md) continues separately on
frozen `a4f8df9`: eleven decks, 55 pairs, both seat orders, 110 BO3 series and
unchanged caps. At the independent thirteen-receipt observation, twelve games
resolve naturally and one reaches the shared series deadline. Receipt hashes,
trace counts and all 2,691 bound source files verify at that observation. This is
partial progress, not a completed or replay-qualified matrix. It was not restarted
after the additive recording correction.

The later 96-receipt independent observation verifies 93 natural games, three
deadline-limited partials and all source/log bindings. Available natural-game
metrics now include twenty unused-mana passes and two flagged blocks; their
denominators and interpretation are recorded with the matrix. Earlier zero
counts do not extend to this larger snapshot. The matrix remains live.

A separate old/new production Master Tempo/Tribal coordinate completes naturally
on both sources: Tempo wins on turn eleven, 321 actions, all 749 quality/event
lines equal after removing the additive envelope. Candidate complete-action
reconstruction and independent receipt/source checks pass. This is one same-seat
coordinate, not the pending full matrix or an AI-strength result.

The [current dependency check](dependency-advisories-20261108.md) finds the pinned
Vite 6.4.4 affected by a maintainer-published development-server advisory. The
minimum patched version is 6.4.5; actual package/lockfile upgrade and clean-install
qualification remain outstanding. The existing build result uses 6.4.4 and is
not remediation evidence. The full advisory gate remains open.

## Remaining Release Work

The subsequent [ASGI timer qualification](asgi-timer-qualification-20261108.md)
passes five whole modules in separate declared executions: 27 synthetic Forge
route tests plus 98 subtests, four real SQLite collision cases, 46 API input
cases, and one natural three-game human-controller BO3 with two cold restores.
The BO3 records 780 accepted decision POSTs and a 2–1 result; sources, child shim
hashes and process closure verify. Product/test sources and original bounds are
unchanged. This is a test-loop scheduling adjustment, not browser/TCP/native Forge
or canonical hosted qualification. Earlier guard-wrapper setup failures remain
recorded and independent review findings were corrected before the natural run.

The later [recovery and interaction follow-ups](asgi-recovery-followups-20261108.md)
pass both whole completed-series-restore and different-card-sideboard modules.
Their two natural three-game scenarios use 780 and 790 accepted action POSTs;
all six cold workers and the process group close normally, and inventory,
rebuilt stocks and sixteen atomic rejection receipts verify. A separate four-module
cohort passes 46 cleanup, replacement, selection and browser-origin tests.
Independent reviews approve both bounded results. The same tracked source stays
unchanged; these are adjusted ASGI/SQLite executions, not browser/TCP/native Forge
or hosted release qualification.

A further six-module lifecycle cohort passes 48 tests covering admission, quota,
cache, cancellation and shutdown. It combines actual owned SQL/ASGI operations
with existing worker/thread/AST controls. All 79 observed connection targets,
2,875 source hashes, runner pin and JUnit verify; independent review reports no
findings. It is neither 48 natural games nor production-throughput qualification.

The [current card-data acceptance cohort](current-card-data-acceptance-20261108.md)
also passes all 833 tests across its original seventeen whole modules, renewing
the canonical-record, rulings, repository, CLI and offline-hydration component
checks on the `91fd0a04` backend. All 2,875 source hashes match; 553 SQL connections
use process-local memory or 236 distinct owned file targets. The single HTTP
case uses the declared timer adjustment. This does not complete literal fixture
cleanup, Phase 1, clean installation or a release gate.

A separate [Control allocation profile](control-allocation-profile-20261108.md)
reaches the original deadline after 998 actions. It attributes most instrumented
time to AI choice, with substantial overlapping state-copy cost; trace building
is a small share. Source, receipt and process closure verify. The retained partial
is not a completed game, speedup or uninstrumented latency result, and its expired
post-run budget check is not evidence of an API result-size defect.

The subsequent [copy import-order correction](copy-import-order-20261108.md)
keeps the existing metadata prefix available after ordinary `typing` imports,
while preserving preexisting caller reducers and the exact registry guard.
Five fresh-interpreter controls and 235 tests across ten whole copy/information
modules pass on its final source. These are its new source qualifications; the
earlier ASGI/data/profile results retain their explicit `91fd0a04` boundary.
The captured slow Master decision still takes about twenty-one seconds, so this
bounded correction does not close practical latency or release acceptance.

The subsequent [offline seed snapshot correction](offline-seed-snapshots.md)
prevents caller edits from changing the shared catalog seen by later hydration
and match construction. Its complete eleven-module pure cohort passes562 tests;
an independent review approves and reruns the overlapping385-case subset.
The startup generator's finite source pin and typed-value consumer were adapted
without changing seed data or any media entries. A separately declared old/new
production-Python Tempo/Tribal comparison finishes both executions with all808
raw log lines and346 checked actions identical. These bounded results leave
full application, hosted new-head, AI-quality and release acceptance open.

All three gates remain open. Existing dated evidence in the finish plan and
acceptance ledger must be reconciled against the final chosen source; an old
failure is not assumed current and an old pass does not automatically transfer.

1. **Human play and recovery:** finish current-source hydration/action parity,
   interacting choice acceptance, malformed/stale/wrong-actor atomic rejection,
   complete supported browser actions, overlap/restart recovery, seeded BO3,
   sideboard inventory and clean offline execution. The native preview still
   explicitly offers a single game; native app BO3 is unfinished.
2. **Rules, knowledge and AI:** reconcile Tasks 1.1--1.4 and the remaining
   canonical fixture inventory; preserve explicit unsupported-mechanic gaps;
   finish decision-quality, timing, archetype and matched-game acceptance.
   The handoff's two-game observer-off/on experiment remains unexecuted.
   Learned policy is experimental opt-in; no generalization or expert-strength
   result is established by these transport/profile checks.
3. **Packaging and operations:** qualify the final combined source through
   clean installation, HTTPS/auth/media, Chrome/Brave/Firefox, backup/restore,
   long-session/accessibility and dependency-advisory checks. Reconcile local
   resource/retention/cancellation boundaries and deployment documentation.
   The historical user-deferred separate-device LAN/manual-CA check stays
   deferred, not passed. No deployment or default-runtime switch occurred.

The next native step requires an execution environment in which the unchanged
qualified guards can start. Preserve the pending two-game declaration and its
no-retry limits; do not spend it on a known pre-JVM sandbox rejection. Other
source, fixture and packaging work can continue in this isolated candidate.
