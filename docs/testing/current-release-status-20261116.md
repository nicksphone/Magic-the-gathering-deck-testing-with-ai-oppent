# Current source and remaining release gates — updated 2026-11-17

Reviewed source: `origin/main` **7af7734e6ec1eb21248498533461795dfcb04b19**.
This is a docs-only source/status reconciliation, not a new full test,
workflow dispatch or deployed-server qualification. Historical results retain
their original revisions and scopes. No overall RC or AI-strength acceptance
is declared. OpenTelemetry 1.45.2 is applied; separate-device LAN/manual CA trust
remains user-deferred for RC, not passed.

## Advisory follow-up — 2026-11-17

Advisory lock follow-up: **`04088d21`** (base `ba847621`) refreshes only the
lint-tool dependency closure, with package.json unchanged and Vite still 6.4.6.
The manager reports Node **26.8.1** / npm **11.19** engine-strict install, lint,
build and tests all exit 0. Full audit falls **13 → 10 high / 0 moderate**,
all from picomatch; production audit remains **0**. **Minimatch's exception is
retired for this lock**. Picomatch's manager-owned exception remains, review by
**2026-12-01** or an earlier release/GHSA trigger. **Node 24.22.0 CI validation
is still pending**, not inferred from Node 26 host results. See the
[verified advisory results](dependency-advisory-review-20261115.md#verified-lock-refresh-and-host-results--04088d21).
This follow-up ran no install or tests locally and claims no new CI/browser pass.

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
| [#93](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/93) | `addea514` | Status-document reconciliation through PR #92. |
| [#94](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/94) | `ce61e70b` | Trace2 pilot result and separately scoped health-run design. |
| [#95](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/95) | `1a54be1f` | 72-game health entry and parent-detected mismatch stop fix. |
| [#96](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/96) | `1e8b4f32` | Operator guidance for interpreting health results. |
| [#97](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/97) | `e964503e` | 72-game health result: FAILED zero tolerance, 71/72 resolved. |
| [#98](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/98) | `d0082cf8` | Measured Python/native performance analysis; no optimization implemented. |
| [#99](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/pull/99) | `7af7734e` | CI test-tiering plan and module lists; proposal only, no CI changes. |

Main CI is **green at `1e8b4f32`**, [run 44019341176](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/44019341176),
and **green at `e964503e`**, [run 44046659274](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/actions/runs/44046659274),
as reported by the project manager. **The head `7af7734e` run result is not yet
known in this reconciliation.** Earlier green runs do not certify that newer
head; no new counts are inferred from the merges or summed across runs.

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

### Trace2 and health results: complete accounting is not acceptance

The trace2 pilot `archetype-pilot-20261116-v3-trace2` at `495d8203` finished
**36/36 accounted: 35 resolved and one CPU-limit timeout**, `usable: false`.
All 35 resolved replays and selected handler/SQLite checks passed without a
reported divergence. This supersedes the earlier launch-only status; it does not
turn the timeout into a completed game. See the
[trace2 result](archetype-v3-pilot-evidence-template-20261116.md).

The separate health run `archetype-health-20261116-v3-trace1` at `1a54be1f`
finished **72/72 accounted, 71 resolved and one CPU-limit timeout**.
**Health FAILED by predeclared zero tolerance**: `complete: true`,
`health_passed: false`, `usable: false`. The 71 resolved replays and selected
handler/SQLite checks passed with **no replay divergence**; the timeout has no
completed replay, winner or score. This is health-only evidence, not statistical
matrix or AI-strength acceptance. See the
[health result](archetype-v3-pilot-evidence-template-20261116.md#72-game-health-result--2026-11-17)
and [timeout options](archetype-health-timeout-options-20261117.md).

The resolved-only trace2 mean implies **1,440 games ≈119.8 worker-hours**, above
the **48-worker-hour** campaign ceiling even before censored/extra work. This is
non-binding arithmetic, not a completed-matrix forecast. The original statistical
matrix is infeasible within that budget; the 72-game health run does not replace it.

PR #98 recommends measured Python representation/copying work before considering
a native kernel; it implements neither an optimization nor a Rust rewrite and
accepts no game/strength gate. It explicitly discards method-wrapper profiling
figures that could force a planner fallback; retained timings preserve method
identity. PR #99 remains an unadopted tiering proposal: current CI coverage and
required checks have not changed. See the
[performance report](python-native-performance-spike-20261117.md) and
[tiering plan](ci-test-tiering-plan-20261117.md).

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

- **Clean Checkout Acceptance — Gate 1 #7 PASSED (2026-11-17):** run **44190103918**, `head_sha` `ba847621bce6ad787c7f5c05cc0b9116ec840975` (main), workflow_dispatch, 22:26:39–23:03:56 UTC. All 16 stages exited 0 (platform, node-version, create-venv, backend-install, backend-pip-check, backend-runtime, frontend-install, cold-offline, api-contracts, runtime-dist, runtime-inventory, runtime-source, frontend-tests, frontend-lint, frontend-build, browser). Hosted Chrome with the workflow's explicit no-sandbox setting; this is not native-protected Chrome/Brave/Firefox acceptance. Earlier dispatches exposed two script bugs fixed in PR #101 (frontend-tests python path, run 44183536248 on `6a440e39`) and PR #102 (`TMPDIR=/tmp` for the frontend-tests stage, run 44189216630 on `9471e461`); both failed runs are history, not acceptance. See the [acceptance runbook](clean-checkout-acceptance-20261115.md).
- **Dependency Advisory Review — Gate 3 #4 CLOSED with a documented exception (2026-11-18):** post-refresh run **44270263913** (workflow_dispatch, `head_sha` `9adf8dc8cc31657e7c04e2fadc130038a6a445ae`, main) reported: production npm **0**, pip-audit **0** over 28 packages, full-lock npm **10 high / 0 moderate / 0 critical**, every one via picomatch GHSA-fc5q-39xc-vjpf (no patched release; registry latest 4.0.7) propagating to fdir/tinyglobby/vite and the typescript-eslint family. The wrapper exits nonzero on any finding, so the run shows "failure"; this is the expected complete-findings outcome, not a query failure. The earlier 13-finding runs (44183595243, 44189247614) are pre-refresh history; lock `04088d21` retired the minimatch exception. **Disposition:** the dev-only picomatch exception is approved by the manager under the user's delegation of this decision (user, 2026-11-18: "you do what you think is best"); production is unaffected, there is no fix to apply and the audit's suggested vite downgrade is rejected. Revisit by **2026-12-01** or on any picomatch release above 4.0.7 / GHSA update. See the [verified advisory results](dependency-advisory-review-20261115.md#verified-lock-refresh-and-host-results--04088d21).
- **Health run — manager disposition: accepted as a disclosed limitation, no rerun (2026-11-18):** run `archetype-health-20261116-v3-trace1` remains a FAILED zero-tolerance result under its original pre-registration (71/72 resolved; one CPU/wall timeout, Drain Deck seat 1 vs Ramp seat 2, turn 26). It is not reinterpreted as a pass and no new limit is introduced. The 71 resolved games' replays and parity matched over 36,404 actions plus 470 selected checks. The user left the call to the manager ("if your happy to move on i am"); the manager moves on with this limitation disclosed. RC does not claim archetype playing health or strength.
- **Firefox/Brave native acceptance — not required for RC (2026-11-18):** the user states Firefox was a Codex choice, not a requirement, and the UI is expected to render equivalently across browsers. Hosted Chrome evidence (Clean Checkout run 44190103918, browser stage) stands as the browser acceptance; it uses the workflow's explicit no-sandbox setting. No native Firefox/Brave result is claimed.
- **Original 1,440-game matrix — descoped by the manager (2026-11-18):** infeasible at the resolved-only **119.8-worker-hour** arithmetic against the **48-worker-hour** ceiling. The user left scope to the manager. RC ships with the bounded evidence actually produced (v3 trace2, the 72-game health run with its disclosed limitation, and the CI/clean-checkout gates) and makes no statistical archetype-matrix claim; Burn and Mono Red remain excluded.
- **CI tiering-plan adoption:** PR #99 is proposal only. Membership, gate
  inventory, full-union pre-merge safety, CI/self-test layers and protection
  drills need separate review/implementation. No tests have been demoted.
- **AI strength:** not accepted, with no supported win-rate or before/after
  strength claim from the pilots, health run, profiling or CI results.

## Standing scope and known limitations

The single-operator loopback launcher, backup/restore instructions and related
bounded tests are merged, not a multi-user/distributed service certificate.
Separate-device LAN/manual CA trust remains **user-deferred for RC, not passed**.
The `legacy_unknown` source-movement seam remains a documented RC limitation:
two strict xfails stay in the [failure ledger](known-failures.md), with typed
activation controls passing normally; the manager approved no rules change.
Browser midgame episodes remain declared canonical midgame, never natural-game
history. Existing rules/data/operational scope limits are not broadened by this
reconciliation, and no overall release or deployment sign-off is declared.

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

This update checks local Git merge history through #99, the committed pilot
analyses and runbooks, literal-consumer references in `.github/scripts/tests`
and `backend/tests`, and bounded results supplied by the project manager.
Only this page and `release-acceptance-status.md` change. No new gameplay,
full suite, browser, workflow, pilot or deployment was executed. No private run
outputs were reread for this reconciliation; aggregate results come from the
committed result docs. Relative document links are checked
against this tree.

Status can become stale when another branch merges. Refresh source identities,
workflow run IDs and exact scopes before release; keep earlier failures and
source-pin evidence rather than rewriting them as current-source successes.
