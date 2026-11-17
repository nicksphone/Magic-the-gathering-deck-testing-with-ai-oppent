# CI test tiering implementation plan — 2026-11-17

> **For agentic workers:** Implementation requires separate approval. Use
> `superpowers:executing-plans` or `superpowers:subagent-driven-development`
> only after approval; this branch changes documentation only.

**Goal:** Give every PR earlier feedback without hiding any backend tests,
source-contract checks, failures or release obligations.

**Architecture:** Full source-bound collection produces two explicit, disjoint
whole-module manifests. Tier A runs for every PR. Tier B remains required on
main, nightly and before RC; the recommended merge queue also runs A+B before
merging. Timing weights balance modules without changing their internal order.

**Tech stack:** Existing Python 3.12 pytest/evidence/shard runner, CI Python and
Node self-tests, GitHub Actions. No workflow, test, pin, dependency or runner
change is implemented here.

**Spec:** Maintainer's docs-only tiering request and the no-hidden-skip rule in
[plan.md](../../plan.md). All measured names and module totals are in the
[complete membership appendix](ci-test-tiering-modules-20261117.md).

## Global constraints

- Preserve baseline failures, setup errors, skips, strict xfails and timeout
  ledgers. Neither tier is permission to add a skip or weaken an assertion.
- All source-pin, interface-scope and golden gates, and every CI self-test,
  belong in A even if slow. Existing frontend/browser/native and release
  workflows remain required as before; this is backend tiering only.
- B is never optional release coverage. A-only success is labelled **Tier A**,
  never “full suite passed.” Main is not RC-qualified until exact-commit A+B,
  all existing independent gates and failure ledgers are satisfied.
- Keep private node parameters, failures, streams and environment values out
  of public artifacts. Publish module names/aggregates and existing bounded
  evidence only. Do not print evidence secrets.
- No source-pinned bytes, pins, snapshots or workflow contracts are updated by
  this draft. Future changes need reviewed, narrowly scoped layered updates.

## Review focus

1. New/renamed/unmapped module: defaults to A; unknown ownership or missing
   collection must fail planning, not omit work.
2. Failed/skipped/setup-error test: its duration cannot prove that its body is
   cheap; retain the whole module in A pending healthy measurement.
3. Slow contract/golden gate: always A, with no timing override to B.
4. Canceled/missing/stale B job: blocks qualification; an old nightly success
   cannot qualify a changed SHA or make a merge safe retrospectively.
5. Different fixture/import order and environment: compare full rosters and
   keep failures visible; a smaller tier may expose or mask order dependence.

## Evidence and its limits

Read-only analysis of the maintainer's completed six-disposable-clone host run
at `e964503e9bb1c55f38dcbf21d8949c7bc55919eb`, dated 2026-11-17. No tests were
launched, retried or deleted for this proposal. The six private JUnit files
are consumed in place; no raw rows, parameter values, failure text or files
are copied into the repo. Module and CI-self-test names are public source
names. The appendix contains aggregated module durations only.

| Outcome | Testcases | Sum of recorded testcase elapsed seconds |
| --- | ---: | ---: |
| Passed | 34,736 | 12,002.447 |
| Failed, errored or skipped combined | 3,339 | 277.147 |
| Total | 38,075 | 12,279.594 |

The combined row is **580 failed + 2,660 errored + 99 skipped**. These are
observations, not accepted baseline failures or a green suite. Missing CI
evidence/isolation environment and live-DB guards prevent many bodies from
running. No error is automatically excused; the maintainer's environment
diagnosis must be confirmed in the actual CI environment.

**JUnit `testcase.time` is elapsed time, not measured CPU usage.** Summing
parallel shards does not turn it into CPU time. Passed-test elapsed work is
3.334 testcase-hours; all-outcome work is 3.411 testcase-hours. CPU-hours and
end-to-end hosted duration cannot be recovered from these XML files. Fixture
setup/teardown attribution follows pytest's JUnit configuration; session
collection, installation, self-tests and runner closeout are not fully modeled.

Across **all outcomes**, median is 58 ms, top **1,646** cases reach 50% of
recorded time, top **10,663** reach 90%, **2,799** exceed 1 s and **45** exceed
10 s. Passed-only median is 66 ms, with 1,551 / 10,389 cases reaching 50% / 90%
and 2,724 over 1 s. Distinguishing these denominators matters. There are
**1,395 measured modules**, including the audit golden module outside
`backend/tests`; collecting only that tests directory would silently lose it.

## Membership rules, applied in order

1. **A contract override:** all pin/interface/golden gates. The initial list
   conservatively protects modules whose path or source matches
   `interface_scope`, source pin/binding, `compatible_product_hash`,
   `restore_reviewed_source`, `SOURCE_PINS`, `SOURCE_BINDING`, `engine_hash`, `source_hash`, `sha256`,
   `git_blob`, `runtime_blob`, golden or snapshot-parity terminology. This
   over-includes ordinary hashing tests deliberately: **461 modules**, totaling
   4,341.277 s, are protected, including eight with an individual passing test
   over 10 s. Filename or text matching is not a proof of semantic completeness;
   activation requires an owner-reviewed gate inventory, including dynamically
   imported helpers, with any additional gate moved to A. No B promotion based
   on an absent keyword alone. New contracts default A.
2. **A uncertainty override:** any observed failure, error or skip keeps its
   whole module in A: **70 modules**, 386.732 s. This overlaps rule 1 and must
   not be added as a disjoint count. This also preserves the two documented
   strict xfails; skipping them is not passing their seam.
3. **B heavy tail:** a remaining wholly passing module qualifies only if at
   least one passing testcase takes **strictly more than 10.000 s**. The exact
   draft list is 10 modules / 160 cases / 1,664.792 s. Every case in a selected
   module travels with it, including its faster cases; no parametrized hunk
   splitting or hidden per-node deselection. These include natural BO3 and
   replay/training workloads, which retain their existing content and gates.
4. **A small/medium default:** every other module. All modules with maximum
   passing case at most 10 s stay A unless they travel with a B module under
   rule 3. Rule 3 uses a measured long-test boundary, not a module-total cutoff
   that would demote hundreds of cheap cases simply because they share a file.
5. **A CI self-tests:** every current `.github/scripts/tests/test_*.py` and
   `test_*.mjs` in the appendix, including source-binding, workflow, privacy,
   shard, storage and closeout tests. They were not part of this timed backend
   run and have no invented zero-second cost. New backend modules and new CI
   self-tests default A until explicitly reviewed.

This cutoff is a conservative proposal to approve before implementation, not
an automatic nightly classifier. Freeze versioned explicit membership; do not
move modules between tiers on noisy timing changes. All 10 B modules were
checked for direct contract terms and their imports inspected. The semantic
gate audit remains an activation prerequisite, especially for indirect helpers.
Review already caught one missed terminology case: `test_training_environment.py`
rejects tampered `provenance.engine_hash`, whose producer hashes source trees.
The complete 50-case / 67.664-s module is therefore A; it is not traded away for
another minute of PR speed. The final scan includes engine/source hash terms.

### Approaches considered

- **Recommended:** conservative module tiers plus full pre-merge merge-group
  validation. Gives early A results, protects small/medium coverage and avoids
  changing fixture granularity. It does not promise dramatic PR speedups.
- **Keep full PR suite; balance timings only:** safest fallback if merge queues
  or required-gate administration are unavailable. No reduction in pre-merge
  coverage; still address the demonstrated shard imbalance.
- **Aggressive top-cost node selection / A-only merge:** rejected as the
  default. A top-50% timing cutoff would cross fixture/module boundaries and
  may demote pin/golden gates; A-only merging lets a B regression reach main.
  A nightly run cannot retroactively prevent that merge.

## Exact list and four-shard projection

The appendix enumerates **all 1,395 measured modules exactly once**, each with
tier, cases, measured seconds, reason and proposed shard, plus the complete
additional A CI-self-test list with time marked unmeasured. No raw testcase rows
are included. The whole-module scheduler used for this estimate sorts by
descending module seconds, breaks ties by path and selects the lowest-loaded
shard, breaking load ties by index. It preserves each module's internal order.

| Proposal | Modules | Cases | Recorded seconds | Testcase-hours |
| --- | ---: | ---: | ---: | ---: |
| A backend | 1,385 | 37,915 | 10,614.802 | 2.949 |
| B backend | 10 | 160 | 1,664.792 | 0.462 |
| Union | 1,395 | 38,075 | 12,279.594 | 3.411 |

A's passed-only time is 10,337.655 s (2.872 testcase-hours). Its non-pass
277.147 s is not an estimate for successfully executing those bodies. **A CPU-hour
projection is unavailable from this input**, rather than a measured zero or an
elapsed-to-CPU conversion. Repaired environment paths may take much longer;
subprocess parallelism can also make aggregate CPU differ from parent elapsed
time. Obtain per-worker/child resource accounting in a separately approved
measurement before publishing a CPU forecast.

| Proposed shard | A testcase-minutes | B testcase-minutes |
| --- | ---: | ---: |
| 0 | 44.228 | 14.384 |
| 1 | 44.228 | 4.506 |
| 2 | 44.228 | 4.393 |
| 3 | 44.228 | 4.463 |

These are **summed recorded-duration projections**, not hosted wall promises.
Add installs, collection/reference, self-tests, evidence controls, closeout,
contention and healthy replacement timings before setting budgets. Unmeasured
CI self-test cost is additional. Tier B's longest module is
`test_live_bo3_series.py` (863.042 s), including a 798.465-s testcase; keeping
modules whole prevents ideal balancing there.

The draft defers **13.6%** of recorded work, not half. At the same weights a
balanced full backend pool has a 51.165-testcase-minute maximum; A's maximum is
44.228, about **13.6% lower**. Running A then B serially would instead take
about 58.612 testcase-minutes at the slowest-shard level; do not claim less total
compute or faster full main validation. Merge-group/main/nightly can use one
balanced union pool and produce separate tier/union results. CI environment
repair and fresh timing can only replace these provisional projections with
new reviewed measurements; they cannot silently reduce coverage.

## Required gates and safe merge policy

Recommended required status design (names proposed, not existing statuses):

- PR: required `backend-validation` runs A, all CI self-tests and current
  independent frontend/browser/other checks. Its evidence explicitly says
  **PR / Tier A**, never full-suite qualification. A success permits queue entry,
  not a direct merge.
- Merge queue: the same required `backend-validation` context must run again
  on the exact merge-group SHA, this time requiring A+B with full
  source/runtime/manifest binding. Its evidence explicitly says
  **merge-group / full union**. Require queue use and no direct/admin bypass;
  validate the event-specific scope in the sealed plan and join. A PR A-only
  success cannot substitute for the merge group's required status. This avoids
  a separate required check that never reports on PRs preventing queue entry.
  Test the ruleset/status configuration before activation rather than trusting
  names. Other required jobs must also report on merge groups.
- Every main commit: required `backend-full-qualified` with A+B and exact union
  evidence. Missing, canceled, errored or timed-out work is a blocking result,
  not an optional status. A failed main run blocks release/deployment and
  subsequent promotion until corrected/reverted and requalified.
- Nightly: full A+B on an explicitly recorded main SHA, with a required
  qualification/promotion check that fails if B is absent or unsuccessful.
  A schedule alone is not a protection rule. Never use a nightly from another
  SHA to qualify current main. Keep the failure ledger and notify the owner.
- RC: exact candidate SHA A+B and all existing RC gates must pass with explicit
  skip/xfail ledgers. No “nightly usually passes” exemption or age-only waiver.

GitHub checks block merging only when branch protection/rulesets actually
require them. A failed post-merge status cannot prevent a merge already made.
Merge queues validate required checks on the combined merge-group changes and
Actions must handle `merge_group` events. Confirm repository/plan availability
and test that configuration before reducing PR coverage.
[Protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
[merge queues](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

If a usable queue is unavailable, retain full A+B as a required PR check on an
up-to-date head, or use a protected integration branch with full A+B before
promotion to main. **Do not silently adopt A-only merges.** That weaker option
would need a separate explicit risk acceptance: B regressions could reach main,
and required main/nightly plus deployment blocking only contain them afterward.

## Changes required in `.github` — description only

1. **Collection and membership schema:** extend `ci_backend_shards.py`
   `make_plan`, `validate_plan`, `assigned_nodes`, `worker_envelope` and `join`
   with a versioned tier manifest/digest, full-reference membership and a
   strict disjoint A/B union. Current plan validation mandates sorted-module
   `index % 4`; it must explicitly admit reviewed weighted assignments instead.
   Reject missing/extra/duplicate/cross-tier nodes, unknown modules, changed
   SHA/lock/runtime, stale timing manifests and a tier-only “full” join.
   New modules start A; changed manifests require review.
2. **Runner:** `run-backend-ci.sh` needs explicit tier-aware planning and a
   declared unexecuted complement, not `-k`, collection exclusions or ad hoc
   deselection. Existing “no deselection” contracts must be reconciled through
   new scoped manifests, not weakened globally. Keep input preparation, DB
   isolation, evidence controls, collection errors, deadlines, pressure limits,
   actual waits/closeout and privacy unchanged. Full-union runs still require
   every original identity exactly once. Preserve within-module order.
3. **Workflow:** `ci.yml` PR/full-main/nightly/merge-group triggers and stable
   uniquely named qualification jobs, explicit dependencies and fail-closed
   aggregate statuses. Keep four workers initially. Reference seals full
   collection; artifacts carry tier and full manifest binding. Download/join
   expected artifacts with `always()` handling, then fail on missing workers;
   never treat skipped dependency jobs as qualification. Keep existing CI
   self-tests early and all independent jobs; scheduled and manual runs must
   provision the same private-input/isolation environment as normal CI.
4. **Evidence/self-test contracts:** review updates in
   `test_ci_backend_shards.py`, `test_ci_backend_shards_v2.py`,
   `test_ci_backend_shards_e2e.py`, `test_ci_backend_metadata.py`,
   `test_ci_reference_failure_metadata.py`, `test_ci_capacity_job_roles.py`,
   `test_ci_trigger_policy.py` and `test_native_workflow_budget.py`. Review
   runner-byte/string contracts in `test_backend_ci_closeout.py`,
   `test_backend_ci_privacy.py`, `test_backend_ci_progress.py`,
   `test_backend_ci_tmp_retention.py`, `test_ci_backend_closeout_metadata.py`,
   `test_ci_selftest_annotations.py`, `test_ci_app_runtime.py` and
   `test_node_runtime_selection.py`; preserve unrelated assertions.
   `ci_backend_metadata.py`, evidence/progress/storage producers and consumers
   need matching schema review if their fields change. This is an impact
   inventory, not permission to rewrite all those files or source pins.
5. **Layered updates and repository administration:** locate every hash,
   literal-source and workflow contract before editing; preserve old accepted
   layers, add the exact approved new layer with inverse/negative mutation
   checks where the contract supports layers. Keep `interface_scope_*` and
   `test_current_main_source_bindings.py` strict; a mismatch is a stop/review,
   not a reason to repin. Have the maintainer configure and verify rulesets,
   required checks, queue eligibility and promotion/release rules outside the
   repo. YAML alone cannot enforce the intended policy.

## Risks, failure accounting and rollback

- **Environment/runtime undercount:** 3,240 failures/errors make this unsuitable
  as a passing baseline or final capacity estimate. Keep their modules A,
  repair provisioning in a separate task and measure again under actual CI;
  never turn missing evidence variables or live-DB refusal into test skips.
- **Flakiness/order:** `test_native_forge_checkpoints.py` remains A. In particular
  `test_save_waits_for_observed_detached_descendant_to_end` and
  `test_natural_completion_reaps_observed_descendant_without_explicit_close`
  exercise process closure; scheduling and host load matter. Preserve these
  assertions, record first failures and investigate; no rerun-until-green or
  permanent quarantine masquerading as pass. Import/fixture side effects can
  change with tiering even if module-internal order stays fixed.
- **Regression reaches main:** prevented only by full pre-merge validation;
  otherwise explicitly residual risk. A nightly/full-main required result is
  a release/promotion guard, not time travel. Revert/fix a bad merge; do not
  exempt its failing B module to keep main green.
- **Noisy one-host timing:** these six concurrent host shards used round-robin
  node assignments, not future hosted whole-module allocation. Long waits,
  CPU contention and setup attribution affect weights. Keep weights stable
  until reviewed refresh; do not tune thresholds to an observed green result.
- **Added operational cost:** PR A plus queue/full-main/nightly can duplicate
  work. Cache only immutable downloads keyed by lock/runtime, never success
  across changed commits. Evaluate cost after shadow runs; no workload deletion.
- **Rollback:** retain the existing full reference/4-worker qualification path
  as a reviewed fallback. Re-enable required full PR coverage before disabling
  tier jobs; do not remove a required status first and create an unguarded
  interval. Restore old complete schema/assignment via reviewed revert, retain
  failure evidence and requalify exact main. Do not clean locks or user DBs.

## Bounded implementation sequence, after approval

- [ ] **Gate inventory and baseline:** owner approves the exact appendix and
  semantic contract closure; verify all source-pin/interface/golden gates A.
  Provision the real CI environment, preserve all failures and collect healthy
  timings. Update projections openly if incomplete bodies are expensive.
- [ ] **Planner contract first:** write RED tests for each review-focus case,
  missing B artifacts, A-only full claim, stale source, duplicate union,
  timing-manifest drift, same-node different tier and new-module default A.
  Add the narrow schema/planner change, then GREEN those and existing shard
  self-tests. Include deterministic equal-weight/tie tests and module-order
  fidelity. No test content or required golden is demoted.
- [ ] **Runner/workflow shadow:** test tier selection/evidence with harmless
  synthetic modules; both A and B failure/interrupt/closeout must fail their
  aggregate. Keep existing full required PR validation active while new tier
  runs are non-authoritative. Run the complete unchanged cohort and compare
  exact identity/outcome ledgers, skips/xfails and full-union qualification.
- [ ] **Protection drill:** maintainer tests a deliberately failing B change
  on a disposable PR/merge group, missing scheduled artifact, canceled worker
  and branch advancing after nightly; each must block its intended promotion.
  Validate queue checks run on the correct combined SHA and cannot be bypassed
  with an A-only success. Keep full PR gate if this drill fails.
- [ ] **Activate or retain fallback:** only after approved evidence, switch
  protection atomically as far as the platform supports without a coverage
  gap, observe subsequent full main/nightly runs and verify rollback. No
  implementation, protection setting or RC gate is approved by this draft.

No implementation tests were run for this docs-only branch. Validation here
consists of read-only XML arithmetic, source-name mapping, exact membership
coverage and documentation checks, not a new test result.
