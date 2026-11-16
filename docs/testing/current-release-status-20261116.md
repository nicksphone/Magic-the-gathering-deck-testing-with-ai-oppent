# Current source and remaining release gates — 2026-11-16

Reviewed source: `origin/main` **91c0db9da0a1a0234fc6e9fa5543f20e546c97b1**.
This is a source/status reconciliation, not a new full test or deployed-server
qualification. Historical results retain their original revisions and scopes.
No overall RC or AI-strength acceptance is declared.

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
  The approved matrix is only a plan/inert harness, not measured games. Its
  seed-only screen still stops Burn/Mono Red on Rift Bolt and Searing Blaze
  coverage flags; no omission, substitution or old 110-series prefix is allowed.
  Empty coverage warnings never certify complete Oracle support.
- **Legacy ambiguity:** `legacy_unknown` uses spell cleanup. At the direct
  historical/resumed-frame finisher seam, an untyped older ability can move a
  separately recast source while that new spell is pending. Normal LIFO does
  not establish a naturally played exploit. The regression/policy task is
  separately tracked; there is no approved rules fix or blanket legacy migration.
- **Gate 3 #1/#2:** the existing operator fixes one loopback Uvicorn worker and
  one shared BasicAuth identity. Capacity ownership is a same-host, same-file
  lock, not distributed coordination or user/seat authorization. Single-user
  docs/enforcement follow-up is separate; raw developer servers are not a secure
  multi-user service. Assigned-LAN routing, client certificate trust and final
  browser/HTTPS topology acceptance remain open.
- **Gate 3 #4:** dated host scans found no npm production advisories; the dev lint
  chain has the accepted temporary minimatch exception owned by Claude, pending
  compatible upstream updates. The reviewed base still pins OpenTelemetry API
  1.45.1; its approved 1.45.2 coordinated patch is a separate branch awaiting
  integration/CI and a fresh composed scan. A zero-production npm count does not
  dismiss developer-server or CI toolchain exposure.
- **Gate 3 #5/#6:** final clean-machine operation, backup/restore, long-session
  soak, accessibility, user-selected topology and release/deployment sign-off
  remain separate gates. This reconciliation does not mark them complete.

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

This update checks the Git merge history, workflow/script source, Vite and
OpenTelemetry pins, the AI diff from the old status revision, default operator
launch arguments and the bounded host results supplied by the project manager.
It changes documentation only; no new gameplay, full suite or deployment was
executed. Relative links and executable paths are checked against this tree.
Status can become stale when another branch merges; refresh the revision and
results before release. Keep earlier failure ledgers/source-pin evidence rather
than rewriting them as new-source successes.

Changed documentation in this reconciliation: `README.md`, `plan.md`,
`AI-STATUS.md`, `docs/testing/battle-payment-browser-20261115.md`, and this status
page. No source, tests, lockfiles, acceptance thresholds or historical pins change.
