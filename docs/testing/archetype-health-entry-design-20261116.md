# Proposed 72-game health entry point — 2026-11-16

**Design for maintainer approval; no code, plan issuance or execution.** The
[trace2 result](archetype-v3-pilot-evidence-template-20261116.md) is accounting-
complete but unusable: 35 verified life outcomes and one CPU-limit timeout.
This proposal does not waive that result or authorize retry/resume. It asks
for a separately named health investigation under the existing campaign.

## Scope and approaches

The manager requested **72 single games: all 36 unordered pairs of the nine
admitted decks × one new seed × both physical seats**, health-only. Existing
`archetype_plan_v3.build_plan(kind='health')` already describes that schedule;
the pilot CLI, worker validation and registry deliberately reject health
execution. Changing a plan's kind by hand or using a pilot ID would bypass that
boundary. The original 1,440-game statistical gate remains unmet.

Three alternatives are explicit:

1. Stop here under the prior usable-pilot prerequisite. This preserves the
   strict prerequisite but supplies no all-pair health evidence.
2. **Recommended for approval:** admit a new, separately labelled health
   entry point despite the unusable pilot, retaining every limit and failure
   result. It tests wider pair coverage; it does not supply a completed-game
   forecast, confidence interval or strength result.
3. Raise CPU/wall limits or reduce AI/search quality to complete the slow cell.
   This would change the experiment and budget basis. It is not proposed.

Only option 2 is designed below. Approval must explicitly accept that trace2
failed the pilot usability prerequisite; merely merging this document does not.

## Proposed registration and execution boundary

- Add a distinct health controller entry point (proposed module
  `scripts.archetype_health_v3`) and narrowly scoped health admission in the
  existing worker/registry. Reuse validated trace, CPU accounting, source/runtime
  bindings, process limits, replay and parity behavior. Keep the pilot CLI's
  kind restriction; no generic accept-any-kind switch or duplicate unchecked
  execution loop. Shared extraction/refactoring must keep pilot behavior intact.
- Freeze a **new health run ID**, proposed
  `archetype-health-20261116-v3-allpairs1`, only after checking it is unused.
  It is not issued by this note. Bind the exact final clean commit, source
  manifest, fresh hash-locked runtime identity, plan file and canonical digest
  before launch. No data from either pilot is inserted into the 72 outcomes.
- Use the existing new health seed **2026112101**, disjoint from the two pilot
  seeds and the registered source matrix. Require a checked collision assertion
  against all referenced plans before issue. Pair order is the existing sorted
  `combinations(names, 2)` order, with deck-A seats 1 then 2 per pair; cell IDs
  bind the new role/run ID and full schedule. No shuffled selective prefix.
- Preserve exactly the nine original admitted lists and both whole-deck Burn/
  Mono Red exclusions. Run support admission before any child. No substitutions,
  card swaps, fallback decks, sideboarding or master-AI/rules changes. Engine
  seeds with swapped seats do not fix shuffles by named deck.
- Two worker slots, one-core affinity and 2-GiB address-space cap each, on an
  idle host with headroom. Keep **1,200 shared game-plus-verify CPU seconds,
  1,500 shared wall seconds, 10,000 actions, 100 turns and 128 MiB trace per
  cell**; schema-4 chain/card-order fidelity, 64-action/decision checkpoints,
  every-action replay/serde and selected first/every-100th/last real-handler/
  SQLite comparisons. These are not HTTP/browser parity or cgroup accounting.

## Frozen health criteria and failure policy

For this 72-cell scope, success requires all 72 declared rows and traces,
zero crashes/illegal accepted actions/replay or selected-parity divergences,
and **zero resource-limit cells**. Existing `max_resource_limit_cells: 0`
is decisive; one of 72 is 1.389%, above even the lineage 1% bound. Do not round
that to zero or relax the integer after seeing results. Deck-out follows engine
rules, completed draws remain draws; timeouts have no winner/score.

Retain no retry/resume. Source/runtime drift, host sleep, malformed/protocol
failure and replay/parity divergence stop admission and invalidate as in the
pilot; drain/reap owned children and label interrupted peers censored. Handled
resource-limit cells remain explicit failures while the unchanged scheduling
policy may continue. Do not stop only the expensive matchup and call the
remaining prefix accepted. A crash or host sleep needs a new approved ID,
not recovery by deleting locks or resetting registry state.

Write a role-specific `HEALTH-COMPLETE.json` or `HEALTH-INCOMPLETE.json` receipt,
with separate accounting `complete` and health-pass fields, ordered outcomes,
source/runtime/plan bindings, actual waited CPU, partial progress, replay/parity
availability and charged campaign totals. Always keep
`statistical_gate_complete: false` and `accepts_matrix_or_strength: false`.
One seed supplies no independent seed-cluster interval; no win-rate precision,
AI-strength percentage or original-matrix acceptance follows even if all pass.
Publish aggregates only; raw game data and diagnostics remain private.

## Campaign, storage and admission bounds

The trace2 report has **155,489.762 worker-slot seconds remaining**, including a
**108,000-second / 30-hour health reserve**. It is a report snapshot; re-read the
existing registry at actual admission, retain every prior charge and use its
same host-local exclusion. Proposed role-aware registry support must accept the
health namespace without creating a new campaign, HOME or registry location.
The registry's pilot/overhead guard cannot simply be disabled for every role;
health gets its own bounded allocation under the same 48-hour total.

The resolved-only arithmetic is 5.989 worker-hours at mean duration and 12.147
at p95-duration-per-cell, before setup/idle/postprocessing overhead. These are
non-binding scenarios, not an accepted pilot forecast. Unseen pair interactions
and the censored cell can make the run slower. Keep a **30-worker-hour total
health-session cap including controller-held slots**, while enforcing the
remaining campaign ceiling and accounting external setup separately. Refuse
new launches when budget cannot cover the required admission; a refusal or
unfinished schedule is incomplete, never truncated success. At the cell wall
ceilings, 72 × 1,500 already equals the reserve, leaving no overhead, so worst-
case completion is not guaranteed. No automatic borrowing from the other
47,489.762 seconds is proposed without a new explicit budget decision.

Trace-only hard maximum is **72 × 128 MiB = 9 GiB**. Preserve prior outputs and
allow additional disk for requests, logs, DBs, caches and checkpoints. Preflight
host disk headroom explicitly; the trace ceiling is not a whole-directory quota.
Do not delete old evidence or owner locks to create space. The earlier full
1,440-game scope would require 119.777 worker-hours at the observed resolved
mean, exceeding the 48-hour campaign before overhead; 72 health games do not
silently replace that statistical requirement.

## Bounded implementation checks after approval

Use authored miniature schedules for orchestration tests; do not launch games
as part of this docs task. Before any host launch, require:

- Exact 72-cell all-pair/seat/seed roster, no duplicates or exclusions beyond
  the two declared decks; reject pilot role/ID/schema substitution and stale
  plan/source/runtime identities before any child.
- Health-only worker and registry admission, cooperative exclusion, preserved
  prior charges, no campaign reset, exact role budgets, refused-budget/incomplete
  paths and terminal accounted-versus-health distinction.
- Game + replay shared budget arithmetic, actual wait usage, selected parity,
  card-order fidelity, timeout censoring and first-diverging-action diagnostics;
  unchanged pilot regression and applicable source-pin tests. Report a pin
  shift before editing any pin or layered delta.
- No resume/retry, sleep/crash/cancel behavior, reaped children, no strength or
  statistical acceptance flag, private artifact paths and no raw-data publication.

The maintainer must approve **scope, the unusable-pilot prerequisite exception,
unchanged limits, zero-limit health threshold and the 30-hour total allocation**
before implementation. A later reviewed implementation and freshly issued plan
need separate explicit operator launch approval. This design issues no plan and
contains no command that purports to execute the presently unsupported role.
