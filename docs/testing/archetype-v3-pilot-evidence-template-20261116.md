# V3 pilot result — evidence-scope template

**Template only. Do not fill result fields until the operator confirms the run
has finished and authorizes output review.** No result is inferred from elapsed
time, an output directory, progress receipts or successful launch. This document
was prepared without reading the live pilot output or running games/tests.
Replace `TBD` only with terminal evidence; leave unavailable measurements unknown.

## Identity and terminal evidence

The operator reported this launch identity; it is not independently verified by
this template:

| Item | Value / evidence to record after completion |
| --- | --- |
| Run ID | `archetype-pilot-20261116-v3-trace1` |
| Source commit | `54c50a91becc629f868f0b2a09814bf35a97e297` |
| Issued plan **file** SHA-256, reported by operator | `ec53f5962d2a7302bd6b8e24403e0cc0860bf20bb9dbba486b99b8f279aa153b` |
| Plan canonical-object digest (`plan_sha256` in controller report) | TBD |
| Fresh hash-locked install record; exact interpreter/runtime identity | TBD; retain privately, summarize provenance without paths/credentials |
| Source/runtime canonical digests and matching private artifact file hashes | TBD; label the two kinds of hash separately |
| Actual terminal controller exit, start/end times, elapsed seconds | TBD |
| Final report filename and file SHA-256 | TBD; `PILOT-COMPLETE.json`, `PILOT-INCOMPLETE.json`, or absent |
| Report `complete`, `usable`, `budget_refused`, `forecast_reason` | TBD, with exact values/types |
| Scheduled / accounted / missing / duplicate / undeclared cells | TBD; compare ordered IDs to the frozen plan, not just lengths |
| Status and termination counts over **all** scheduled cells | TBD; retain missing cells explicitly |
| Wait/accounting closure and registry state after termination | TBD; a closed registry is not a health pass |

The plan file is pretty-printed JSON, while the report's `plan_sha256` uses the
adapter's canonical JSON-object digest. They are different identities: compare
like with like using the committed adapter's algorithm. The same distinction
applies to published source/runtime objects versus their file-byte hashes.
Do not call the supplied plan-file hash a matched report-object digest.

A controller exit 0, a filename containing COMPLETE or `accounted: 36` alone is
insufficient. Check the terminal process, final report, ordered schedule,
source/runtime/plan bindings and applicable per-cell evidence together. Missing
or contradictory evidence leaves the conclusion unverified; do not repair a
report to make it consistent.

## Frozen scope and budgets to check against the actual plan

- **36 single games**, nine adjacent admitted deck pairs × two fresh seeds
  (`2026112001`, `2026112002`) × both seats. No sideboarding; unchanged master AI
  and rules. Burn/Mono Red exclusions remain the declared admission policy.
- This is not all 36 deck pairs, the original 1,440-game/20-seed statistical
  matrix, a natural BO3 cohort, or an AI-strength acceptance sample. Mirrored
  seats share an engine seed but do not fix shuffles by named deck: swapped
  seats can receive different hands/draws. Do not count games/seats as independent
  seeds or manufacture a precise strength interval from this pilot.
- Two concurrent worker slots, one-core affinity and 2-GiB address-space limit
  per worker. Require the declared host headroom and idle-host condition to be
  recorded. These are process/affinity controls, not cgroup reservations or a
  measured aggregate-memory guarantee.
- **1,200 CPU / 1,500 wall seconds per cell shared by play plus verification**;
  no retry/resume. Check the active v3 policy, not the older budget nested in the
  lineage-only source matrix. Tick/turn/trace limits and host sleep remain
  failures, not draws, losses or completed wins.
- Per-action complete state/legal/RNG digest chain; full checkpoints every 64
  actions and at declared decision/handler/final boundaries. Sequential replay
  and serialization round trips still run at every accepted action. A lighter
  trace does not relax replay equality.
- The campaign ceiling is 48 worker-hours: 15 pilot, 30 reserved for a separately
  approved health run, three overhead. The registry carries prior charges across
  new run IDs. Both slots are charged through controller lifetime, including
  setup/idle/postprocessing; actual child CPU is a different measurement.
  External installation/setup work also consumes operator-accounted overhead.

## Interpret the result

### If `complete: true` and `usable: true`

The committed controller requires the exact scheduled rows without invalidation,
all statuses `resolved` or `draw`, successful bound verification, complete valid
phase receipts, reaped attempted children and finite measured CPU totals. Its
verification binds the whole outcome, including winner, to sequential replay;
selected first/every-100th/last boundaries also compare real app-handler/SQLite
state. These direct handler comparisons are **not HTTP or browser parity**.

After independently checking that evidence, the strongest supported statement is:

> On the exact source/runtime/plan above, all 36 declared pilot games completed
> with genuine engine outcomes and passed the configured per-action replay,
> serialization and selected handler/SQLite checks. The pilot is usable for its
> bounded operational forecast. This does not accept the matrix, AI strength,
> general rules correctness or RC.

Report the actual resolved/draw counts, resource/error/divergence counts and
checks performed. An engine-consistent outcome can still contain a rules/AI
quality defect that these equality checks do not detect. Do not translate replay
agreement into independent Oracle correctness or experienced-player quality.

### If `usable: false` (whether `complete` is true or false)

`complete: true` can mean every declared cell was accounted for even when games
hit limits or failed. It is accounting completion, not healthy completion.
`complete: false` includes missing/invalidated rows or a stopped controller;
all failures and missing cells remain in scope. A resource-limited or failed
verification must not retain a game winner as an accepted result.

Use this bounded statement, with the actual failure causes filled in:

> The pilot is unusable for completed-game forecasting: [TBD status/termination
> and missing/invalid-cell counts]. Accounted cells are not necessarily completed
> games. The original plan remains unchanged; no prefix or replacement run has
> been promoted to acceptance.

The controller sets completed-game forecast fields to `null` when unusable.
Preserve that. Do not drop failed cells, score timeouts as losses/draws, report a
win rate over the surviving prefix, reuse c2 traces, raise budgets after seeing
results, or silently substitute seeds/decks/AI. A future attempt needs a new
pre-registered ID and approval. An unproven controller/child closure blocks later
registry admission; no reset, lock deletion, HOME change or automatic recovery
is authorized by this template.

## Measurements and forecast wording

Fill these from final, bound evidence, keeping counts and missingness visible:

| Measurement | Observed value / scope |
| --- | --- |
| Statuses and termination causes | TBD over all 36 scheduled cells |
| Accepted actions, partial accepted actions, final turn/step/life progression | TBD; inspect private traces only after permission; publish aggregates only |
| Actual waited CPU by cell and phase; cells with CPU data | TBD; missing is unknown, never zero |
| CPU category attribution and residual/unattributed CPU | TBD; include interrupted-operation/receipt limitations |
| Cell elapsed mean/p95 and controller elapsed | TBD; limited/censored durations are not completed-game durations |
| Peak child RSS, address-space controls, failures | TBD; RSS is not the configured address-space limit or total host memory |
| Trace bytes and observed checkpoint/action counts | TBD; per-trace 64-MiB quota is not a quota on the whole output directory |
| Replay time/check counts and first divergence if any | TBD; no divergence claim without completed verification |
| Charged current/cumulative worker-slot seconds and remaining campaign budget | TBD; distinguish from summed child CPU and reserve 30 hours for health |

`cpu_attribution_complete` means valid phase receipts exist; it does not mean
all CPU is assigned to named categories. Include measured residual CPU. For a
killed worker, only the authenticated flushed progress prefix can support
partial category/action evidence; the interrupted operation stays unattributed.
Do not mistake wall timers, profiler-overhead runs or `None` for actual CPU.

Only a usable pilot supplies the adapter's completed-game forecast fields:
`forecast_72_worker_hours`, `forecast_1440_worker_hours` and
`forecast_trace_bytes`. Report them as exploratory extrapolations from these
nine pairs/two seeds, not measurements of the unrun cohorts or confidence bounds.
The 1,440 trace forecast scales pilot trace bytes by 40; it excludes other output
and does not certify disk sufficiency. Dividing worker-hours by two estimates
ideal two-slot elapsed time only, before scheduling/host overhead.

Compare remaining charged campaign budget, overhead and the conditional health
reservation explicitly. Final-report figures are measured before its own
publication; the registry ledger is authoritative for later admission. A favorable forecast cannot authorize another run or
silently reduce the original statistical requirement. A separately approved
72-game, all-pairs, one-seed health run remains **health-only**, with no meaningful
seed-cluster interval from one independent seed; it does not close the original
statistical or strength gate. The v3 pilot CLI does not execute that health plan.

## Publication and next decision

Keep plan files, complete snapshots/traces, hands, reasons, worker logs,
databases and runtime/registry records private. Publish only reviewed aggregate
facts and hashes without private paths or payloads. Hashes are bindings, not
proof that an unexamined artifact passed.

Result conclusion: **TBD — unverified until terminal review.**

- What passed, on which exact revision/runtime: TBD.
- What failed, timed out, remained missing or could not be verified: TBD.
- Is a separate health-plan review justified within the remaining ceiling: TBD;
  operator/maintainer approval required, not granted here.
- What remains open: final-source CI, clean-checkout/user-dispatched workflows,
  native browser/operator gates, rules/data scope, statistical/strength evaluation
  and RC sign-off retain their own requirements. This pilot alone closes none.

Reference: [v3 adapter/runbook](archetype-v3-adapter-20261116.md) and
[AI scope/status](../../AI-STATUS.md). This is a reporting template, not a new
plan, output audit, execution authorization or result claim.
