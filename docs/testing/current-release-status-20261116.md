# Current source and remaining release gates — 2026-11-16

Reviewed source: `origin/main` **495d820325179a625b5a63b2d62847718d5d5706**.
This is a docs-only source/status reconciliation, not a new full test,
workflow dispatch or deployed-server qualification. Historical results retain
their original revisions and scopes. No overall RC or AI-strength acceptance
is declared. OpenTelemetry 1.45.2 is applied; separate-device LAN/manual CA trust
remains user-deferred for RC, not passed.

## Merged since PR #79

The following source integrations are verified against local Git history.
PR #85/#86's work was composed in #88, not counted as two additional main merges.
Merges alone do not establish new CI totals or final-source browser acceptance.

| PR | Merge SHA | Merged scope |
| --- | --- | --- |
| [#80](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/80) | `7b1b707a` | Direct-combat browser waits for committed revision; deterministic stale-read contract. |
| [#81](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/81) | `5188a269` | Bounded knowledge/data evidence and its limits. |
| [#82](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/82) | `ec26f6f5` | Both-seat unaffordable-Pact browser episodes. |
| [#83](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/83) | `eb7cbb4e` | c2 pilot diagnosis and bounded profiling; no accepted matrix result. |
| [#84](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/84) | `54c50a91` | v3 digest-chain/checkpoint adapter, pilot and campaign accounting. |
| [#87](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/87) | `eaba2945` | Pending-Pact ASGI/SQLite cold-process reconstruction and test-order isolation. |
| [#88](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/88) | `fdab4c4e` | Composed simultaneous-debt and Battle-routing browser cohort. |
| [#89](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/89) | `2de3a167` | Legacy stack cleanup decision memo; no rules change. |
| [#90](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/90) | `0dd99fc0` | Consistent install/build/loopback launcher/restore/operator documentation. |
| [#91](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/91) | `45ba938e` | Pilot evidence-scope template, not a result. |
| [#92](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/92) | `495d8203` | Authenticated card-order fidelity fix and 128-MiB trace ceiling. |

### Pilot evidence: failed predecessors remain failed

- **c2**, `archetype-pilot-20261116-v2-c2`, source `93bd5971`: all **36/36**
  cells ended at the 90-CPU-second limit; no completed game/replay result.
  Streaming diagnosis counted **12,228 accepted actions**, turns **9–16** and
  **7,985,144,851 trace bytes**. Games progressed in the observed prefixes;
  no stationary priority loop was demonstrated. Bounded cell-000 profiling
  implicated snapshot construction and AI simulations, rather than disk writes
  alone. Scheduling completion is not pilot usability, a completed-game timing
  forecast or matrix acceptance. See the [c2 diagnosis](archetype-pilot-c2-diagnosis-20261116.md).
- **v3 trace1**, `archetype-pilot-20261116-v3-trace1`, source `54c50a91`:
  **12/36** accounted, with **9 resolved, 1 replay divergence, 1 trace-limit
  timeout and 1 canceled peer labeled error**; `complete: false`, `usable: false`.
  Cell 010's first divergence was zero-based action **647**: canonical adapter
  capture/restore lost `state.cards` insertion order, changing simultaneous-SBA
  log order. It triggered fail-fast cancellation; 24 cells never started.
  Cell 001 refused the next whole trace record after **1,151 actions** and
  **65,890,540 bytes**, at **985.111 CPU seconds**: a trace quota, not CPU/wall
  exhaustion. Cell 011 was peer SIGTERM cancellation, not a recorded independent
  engine exception. The nine verified games total **5,689 actions**, turns
  **16–29**, with five seat-1 and four seat-2 wins, **accounting only**. No
  strength estimate or completed-game forecast follows from this incomplete
  prefix. See the [trace1 diagnosis](archetype-v3-trace1-diagnosis-20261116.md).

PR #92 preserves explicit card-map order at capture/replay and selected handler/
SQLite boundaries while retaining canonical state digests; it does not sort or
ignore logs or change rules/AI. Its declared real-combat/SBA regression failed
before and passed after; v2 digest equivalence is retained. The local explicit
17-module check recorded **396 passed, 0 failed/errors/skips** (128 v3, 75 v2,
193 pin checks), using the existing local environment, not a fresh locked install
or full backend run. The new **128-MiB** quota keeps 64-action and decision-boundary
checkpoints and the 1,200-CPU/1,500-wall-second cell limits. It is not a guarantee
against another quota failure. The [quota arithmetic](archetype-trace2-quota-proposal-20261116.md)
retains prior campaign charges; no stopped run is resumed or reclassified.

### Trace2 launch: result pending

Claude reports issuing and launching **`archetype-pilot-20261116-v3-trace2`**
on a clean clone of **`495d8203`**, with the same hash-locked environment and
plan file SHA-256
`79beba36d65d6745a363f2e9a4063ee8c5fb25f553b1e6bea77746cdcc26389d`.
This records operator-supplied launch metadata only. Its private outputs have
**not been read for this update**; completion, statuses, timing, replay health
and usability are unknown. No new result, forecast or acceptance is claimed.
The separately approved future 72-game health-only scope is not the original
statistical gate and has no run result here.

## Landed source and bounded results

| Work | Landed source | Evidence and limits |
| --- | --- | --- |
| Paid-copy boundary, RC feature batch | PR #52/#54/#55 | Earlier main `e51ddb82` CI run **43759790245** passed every job: 37,722 collected, 37,625 passed calls, 97 skips, 0 failures. This is not a run on the newer reviewed revision. |
| Battle request atomicity | PR #58 | Host 64 passed; malformed/stale/wrong actor and rollback/idempotency coverage. Does not prove every API action atomic. |
| Battle recovery | PR #60 | Host 8 passed on three consecutive runs. ASGI response loss, controller reconciliation and separate-process SQLite restart; no claim of actual TCP/browser refresh from these tests alone. |
| Battle/payment browser cohort | PR #61 | Host six PASS episodes: four **declared canonical midgame** flows (both seats, human/human and human/AI) plus two warning negatives. Warning-only baseline passed both seats; warning removal failed at the explicit warning assertion. Existing natural BO3 cohort unchanged. |
| Siege defeat live/reload fix | PR #63 | `resolve_defeat` now reconciles departed targets before the cast-choice pause. Host goldens+related slice 475 passed, pin slice 393 passed. These are scoped host results, not new unique test totals to add to main CI. |
| Fresh-checkout acceptance command | PR #62 | Script/runbook/manual CI workflow exist; the complete hosted run has **not** been established. See action below. |
| Vite security patch | PR #64 | Source pins 6.4.6. Host lint/build and 1,047 frontend tests passed; host audit cleared the Vite advisory. Final composed CI/scans remain distinct. |

PR #88 now contains the composed 16-episode program: four funded canonical-
midgame flows, two unsupported-control warning negatives, two unaffordable-Pact,
two simultaneous-debt continuation and six Battle-routing episodes. This is
its declared scope, not a newly observed 16-PASS run in this reconciliation.
PR #87 adds four both-seat pay/decline cold-process cases; the manager reports
4/4 with and 4/4 without a stray default DB after its test-order fix, separate
runs rather than eight distinct cases. These are ASGI/SQLite checks, not an
uninterrupted browser connection across backend restart. See the
[browser scope](battle-payment-browser-20261115.md) and
[cold-restart evidence](pact-cold-restart-20261116.md).

The PR #61 host run was on its branch before the Vite patch. Do not transfer its
browser pass to all later source/dependency compositions without the configured
acceptance run. A merge/push is not deployment of a running server.

## What remains open

- **Gate 1 #3–#5:** new Battle/payment/atomicity/recovery cases are covered above;
  they do not exhaust every supported action, cross-feature choice, disconnect or
  concurrency path. Midgame fixtures are not natural-game history. Real TCP
  timeout/response-loss and broader browser recovery remain separate work.
- **Gate 1 #7:** final fresh locked installs, cold offline assets, API/runtime
  contracts, full frontend tests/lint/build and the entire configured browser
  flow need one successful current-source acceptance run without developer
  caches. Host attempts stopped at missing ensurepip; sandbox attempts stopped
  at Node/runtime/socket constraints. Neither is a passing downstream run.
- **Gate 2:** AI implementation exists and changed since `3c054542` (including
  deferred-payment policy and agent/resource/pending-effect work). Playing
  strength, representative before/after decision quality and full seeded/seat-
  balanced evaluation remain **unaccepted**, with no percentage estimate.
  The adapter has now run the failed c2 and incomplete trace1 pilots summarized
  above; trace2 is launched with no reviewed result. The v2 plan explicitly
  excludes whole Burn/Mono Red decks on Rift Bolt/Searing Blaze coverage flags
  and schedules nine unchanged admitted lists; this is reduced scope, not
  eleven-deck admission. Neither the future 72-game health-only run nor these
  pilots replace the original statistical gate. No old 110-series prefix,
  outcome splicing or strength claim is allowed. Empty coverage warnings never
  certify complete Oracle support.
- **Legacy ambiguity:** `legacy_unknown` uses spell cleanup. At the direct
  historical/resumed-frame finisher seam, an untyped older ability can move a
  separately recast source while that new spell is pending. Normal LIFO does
  not establish a naturally played exploit. The manager chose to retain this
  RC limitation after PR #89: two strict xfails remain in the
  [failure ledger](known-failures.md), while typed-activation controls remain
  normal passing tests. No rules fix or blanket legacy migration is approved.
- **Gate 3 #1/#2:** the existing operator fixes one loopback Uvicorn worker and
  one shared BasicAuth identity. Capacity ownership is a same-host, same-file
  lock, not distributed coordination or user/seat authorization. Single-user
  enforcement and the one-command built-frontend launcher are merged; PR #90
  reconciles the quick-start and restore instructions. Raw developer servers
  are not a secure multi-user service. Source/docs integration does not certify
  a final operator installation. Separate-device LAN routing and manual
  CA-trust checks are
  **user-deferred for RC, not passed**, as recorded in the release ledger.
  They remain unfinished before wider deployment. Final local HTTPS/authentication
  and Linux Chrome, Brave and Firefox acceptance remain in RC scope.
- **Gate 3 #4:** dated host scans found no npm production advisories; the dev lint
  chain has the accepted temporary minimatch exception owned by Claude, pending
  compatible upstream updates. PR #66 already applied OpenTelemetry API
  **1.45.2**, including its wheel hash and coordinated runtime inventory; do not
  bump it again. The final composed advisory scan and disposition confirmation
  remain open; see the [applied patch status](dependency-advisory-review-20261115.md#applied-patch-status--2026-11-16)
  and the [user workflow actions](release-acceptance-status.md#2026-11-16-user-actions-for-final-acceptance-evidence).
  A zero-production npm count does not dismiss developer-server or CI toolchain
  exposure.
- **Gate 3 #5/#6:** populated-SQLite backup/restore and saved-game reconstruction
  tests/runbook are merged (PR #75), and operator wording is reconciled by #90.
  Final clean-machine operation, an operator backup/restore rehearsal,
  long-session soak, accessibility, local operator acceptance and
  release/deployment sign-off remain separate gates, with the LAN/manual CA-trust
  deferral above preserved.
  This reconciliation does not mark them complete.

## Action needed for Gate 1 #7 evidence

A repository user with workflow-dispatch rights should open **Actions → Clean
Checkout Acceptance → Run workflow**, select **main**, and run it after the
intended fixes/dependencies are merged. Claude's token received 403 for dispatch;
no workflow run is implied by publishing the YAML.

The workflow calls `scripts/accept-clean-checkout.sh` with `GITHUB_SHA`. Inspect
its revision, `results.tsv`, JUnit, runtime and browser logs; record the run ID,
exact source revision, per-stage exits and exact case/episode counts. A failed
or undispatched run leaves #7 open. See the [acceptance runbook](clean-checkout-acceptance-20261115.md).

## Reconciliation checks and risks

This update checks local Git merge history through #92, the committed pilot
analyses and runbooks, literal-consumer references in `.github/scripts/tests`
and `backend/tests`, and bounded results supplied by the project manager.
Only this page and `release-acceptance-status.md` change. No new gameplay,
full suite, browser, workflow, pilot or deployment was executed. Trace2 outputs
were not read. Relative document links are checked against this tree.

Status can become stale when another branch merges. Refresh source identities,
workflow run IDs and exact scopes before release; keep earlier failures and
source-pin evidence rather than rewriting them as current-source successes.
