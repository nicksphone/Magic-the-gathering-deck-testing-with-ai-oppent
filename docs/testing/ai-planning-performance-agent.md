# Master AI planning latency: isolated performance-agent investigation

## Parent reproduction

The parent independently verified the archived checksums and reran the final
diagnostic script from a new disposable `git archive` of `b7b183b`, using the
declared pinned inputs and isolated interpreter. Decision 1422 reproduced
16 legal moves, `pass_priority`, 84 destruction projections / 12 unique inputs /
72 duplicates, and the report's exact action/source/checked-result hashes.
Decision 1169 reproduced 28 legal moves, the same Memory Deluge action hash and
zero destruction projections. Both decisions left their source unchanged and
passed actual checked execution. Observed wall times were 21.78 and 2.14 seconds;
these are individual measurements, not optimized performance results.

Verified parent logs and result packets are under `parent-verification/` in the
agent archive below. This confirms the diagnostic on its declared source base,
not the subsequently changed production backend. No production memoization or
search reduction is implemented by importing this script/report.

## Outcome and scope

The late Blue Control decisions reproduce on committed main. Decision 1422 spends most of its profiled time projecting friendly destruction: **84 calls, 12 distinct exact input groups, seven executions per group**. All 72 duplicate results agreed. This is not the only bottleneck: decision 1169 takes about 2.11 seconds and makes **zero** friendly-destruction projections; strategic stack search, payment planning, continuous queries and copying dominate that case.

No production optimization was implemented. Owned files are this report and `backend/scripts/ai_planning_performance_agent.py`. Branch: `diagnostics/ai-planning-performance`; isolated worktree: `/home/nick/mtg-ai-performance`; exact base: `d58dbecf69765b2c22be81745b3c3ef1d7f5fc16`. The archived commit metadata identifies the final diagnostic commit. No merge, reset, rebase, push, server, service, matrix, balance tuning, shared Graphify edit or regression-fixture edit was performed.

## Evidence, provenance and executable baseline

Durable output directory:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-planning-performance-agent/20261004T221221Z/`

It contains `evidence.tgz`, outer `SHA256SUMS`, and commit/ownership metadata. The archive contains an inner per-file `SHA256SUMS`, exact commands, environment/package metadata, binary cProfiles and readable profiles, raw timing JSON, selected snapshots, privacy checks, canonical control construction/trace, test logs, input provenance and the diagnostic source. Databases were never opened on NFS. Before writing, `findmnt` showed both autofs and final **nfs**; a unique write/read/delete probe passed. Readback hashes are verified by the archival procedure.

Input archives were checked against their containing `SHA256SUMS` before extraction:

- `release-and-latency-evidence.tgz`: `afe317ff245b07abadb3f10ea314d94ed8e23eaf346843a369b68a479c575cdd`
- `validated-gates-verified.tgz`: `687ad33e8f1cdc695048a87107b46a0068ce7ab856309f27059422cb6b128b3c`
- Resolved `pair-0.json`: `373f78139146f6208f75ef888deff9c17e4444e9a8eb14c16c90a208ab23cae6`; production manifest validator confirmed corpus `da32a3af2b3a3e81748c6db689936f8e601ecc43679780f61c3c32ce1d0c32e7`.

The manifest is a bundled offline resolved corpus with source provenance `6e2a4d8`, not a newly synced or universally certified deck corpus. Historical seed is `299881130`, Ramp seat 1 / Blue Control seat 2. The archived tracer saved snapshots **after** `choose_action` and did not save the agent's accumulated pass counters. These probes restore the saved state with a fresh agent, not the entire historical process. Nevertheless all four selected historical action dictionaries match exactly. Comparison of archived backend Python files with the current base found only `tests/test_regression_repair_edges.py` different; no archived production Python difference was found. Full manifest validation followed the initial hash-verified snapshot smoke, before the later canonical-control probes.

Graph report was read first; its recorded base `e6c6774a` is stale relative to this base. There is no `graphify-out/wiki/index.md` or nested applicable AGENTS file in the worktree. `/home/nick/AGENTS.md` applies. The assignment explicitly prohibits shared graph updates.

All execution used a local `git archive` copy under `/home/nick/.hermes/cache/scratch/ai-performance-agent-q7lf6oer/source`, never either live worktree. Interpreter `/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python` was used read-only. Python 3.12.3, Linux 6.8.0-111-generic, AMD Ryzen 7 2700X, eight exposed CPUs; timed subprocesses pinned to CPU 0, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. Packages and exact OS details are in `environment.json`. Host exclusivity/governor was not controlled.

Executed from disposable `source/backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q tests/test_ai_information_boundary.py tests/test_ai_search_prefix.py
# 166 passed in 32.22s (before timing probes)
PYTHONDONTWRITEBYTECODE=1 /home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q tests/test_ai_projection_scope.py tests/test_pending_removal.py
# 41 passed in 8.18s
```

These are targeted baselines, not the full suite or rules certification.

## Repeated unprofiled measurements

Eight selected states, two fresh processes per state, two decisions per process: **32 primary timing samples**. A new agent and restored snapshot are used for each decision; “warm” means process-level parser/import caches, not reused strategic agent history. Timing begins after agent construction and authoritative legal generation and ends after `choose_action`. Legal generation and checked execution have separate timings. “First” is first decision in that process, **not** cold OS page cache or application startup. Warm runs also follow the first run's checked validation.

| State | Turn / step / actor | Battlefield sizes 1:2 | Legal moves | First-process wall seconds (two) | Warm wall seconds (two) | Median CPU seconds |
|---|---|---:|---:|---|---|---:|
| 1169 | 42 upkeep / 2 | 20:12 | 28 | 2.1154, 2.1077 | 2.1064, 2.1046 | 2.1056 |
| 1234 | 44 upkeep / 2 | 21:14 | 31 | 7.1910, 7.2145 | 7.2031, 7.1354 | 7.1919 |
| 1396 | 48 precombat main / 2 | 19:20 | 19 | 19.7303, 19.7532 | 19.6735, 19.8768 | 19.7280 |
| 1422 | 49 precombat main / 2; one stack item | 19:20 | 16 | 21.0105, 20.9267 | 20.9141, 20.9738 | 20.9319 |
| Checked successor of 1169 | 42 upkeep / 2 | 20:12 | 19 | 0.8681, 0.8759 | 0.8375, 0.8762 | 0.8704 |
| Checked successor of 1396 | 48 precombat main / 1 | 19:20 | 21 | 0.0348, 0.0353 | 0.0133, 0.0123 | 0.0240 |
| Mono Red Aggro control | 3 upkeep / 1 | 2:1 | 2 | 0.0546, 0.0514 | 0.0195, 0.0189 | 0.0355 |
| Its Ramp opponent | 3 upkeep / 2 | 2:1 | 3 | 0.0492, 0.0495 | 0.0164, 0.0161 | 0.0328 |

The two successor states were first derived using actual checked actions, then timed again from their saved snapshots in fresh processes. Earlier `advance1` results in the archive are ancillary and already warmed by derivation; their original `process-first` label must **not** be interpreted as cold. The final script labels such runs `advance-warmed`.

Median legal-generation / checked-action wall seconds for slow states: 1169 0.1384 / 0.1642; 1234 0.1669 / 0.1986; 1396 0.0784 / 0.0770; 1422 0.0608 / 0.0847. CPU closely follows wall time: these selected decisions are predominantly computational, not storage waits.

The added archetype uses the existing `BUILTIN_DECKS['Mono Red Aggro']` 60-card list, local canonical hydration with no network/database lookup, and the already validated Ramp list. `ready_for_match` passed for every red entry. Seed 731 reached the saved turn-three controls after 55 actual checked actions. No card text was invented or tuned. These early controls do not establish late-game Aggro performance.

## Profiles and repeated work

Separate cProfile runs took 6.5761 seconds for 1169 and 68.1182 seconds for 1422: **3.121x** and **3.251x** their respective unprofiled medians. Do not substitute profiled seconds for latency. Counts below are total calls; cumulative times overlap and must not be summed.

| Production function | 1169 calls / cumulative seconds | 1422 calls / cumulative seconds |
|---|---:|---:|
| `friendly_destruction_profit` | 0 / 0 | 84 / 60.7068 |
| `planning_copy` | 84 / 1.8262 | 188 / 4.8680 |
| `deepcopy` (recursive calls included) | 567,848 / 1.3677 | 3,454,608 / 8.4904 |
| `checked_action` | 0 / 0 | 96 / 32.2236 |
| engine `legal_moves` | 29 / 1.7678 | 97 / 10.3367 |
| `build_cast_hints` | 13 / 0.0060 | 487 / 5.2062 |
| `_plan_payment` | 197 / 2.5642 | 480 / 11.9558 |
| `printed_abilities_suppressed` | 65,960 / 2.2827 | 1,399,153 / 30.0945 |
| `_settle_announced_stack` | 0 / 0 | 180 / 28.6439 |

Paths and mechanisms:

- `backend/ai/agent.py:2846` materializes actions; `:2963-2968` calls `unproductive_destroy_targets` with candidate target IDs and a freshly allocated closure capturing this agent.
- `backend/ai/pending_effects.py:138-169` considers friendly candidates; `:172-198` copies, checks a cast, settles its full announced stack, separately settles the baseline, and compares board values. Unknown/private continuations remain unknown rather than profitable.
- At 1422, `_materialize_action` costs 60.8227 profiled seconds; `unproductive_destroy_targets` 60.7827; `_winning_self_removal_action` (`agent.py:2640`) 41.7054. These are nested costs, not independent additions.
- At 1169, `_strategic_plan_action` (`agent.py:770`) costs 6.5301 profiled seconds, `_strategic_line_score` 6.2843 and `_stack_two_ply_value` 3.9179. Removing destruction overhead alone cannot fix this case.
- Existing root caches already live in `pending_effects.py:25-34,75-100,260-268`; pure query scopes are in `rules_engine/query_context.py:9-39`. Do not duplicate or globally extend these blindly.

The duplicate-only instrumentation does **not** cache or change return values. For each call it records:

1. retained state-object identity and hash of the complete serialized planning state;
2. player ID and canonical **complete** action, including source ID, dynamic cost options, target hints and announced targets;
3. policy code/function identity, bound receiver identity, and retained closure capture identities plus current serialized captured-object attributes.

Callable and state references are retained to prevent object-ID reuse. Fresh lambdas are normalized by their actual code and captured receiver state, not transient lambda object IDs. This is evidence about this concrete closure, **not** a proposed generic callable hashing API. Serialization misses arbitrary transient/custom attributes; production caching must use an immutable-root contract, not copy this expensive diagnostic key.

For 1422, final duplicate instrumentation measured 84 calls / 12 groups / 72 repeats, with seven calls in every group. The full action groups are two Fatal Push instances (`p2-029`, `p2-028`) and Drown in the Loch (`p2-025`) against each of four friendly Shark instances (IDs ending `0057`, `0058`, `005a`, `005b`). All results were `False`; repeated result equality was asserted. The common serialized planning-state hash is `0dc96feac17383ef6453dbfc33e64af473036a0f87f6449a251e6d31d2a31c1a`. The final instrumented decision took 22.4089 seconds, of which 19.1272 seconds were inside the original projection function. **85.7% of these calls repeat identical recorded inputs.** That fraction is not a proven end-to-end speedup. At 1169 the same instrumentation observes zero such calls.

## Legality, stability and private information

Every timing/profile/duplicate sample regenerates actual engine legal moves, checks serialized source equality before/after legal generation and decision, and executes the chosen action through `checked_action` on its copy. Casts in 1169 and 1234 and the cycle in the 1169 successor therefore exercise real payment paths, not merely membership in legal-action types. Every primary state's repeated action and resulting snapshot hashes agreed across all four samples. 1169 casts Memory Deluge; 1234 casts Go for the Throat; 1396 and 1422 pass. The four historical action dictionaries matched the corresponding archived decision records exactly.

The benchmark never bypasses `AIAgent.choose_action`'s production `decision_view` (`agent.py:106-110`; `information.py:23-79`). No hidden card identity is used to rank or select actions. As in the archived caller, archetype parameters are derived from submitted lists; opponent hand/library identities are not supplied to search. Sanitized summaries expose counts, own chosen actions and hashes; full reproducibility snapshots remain in the evidence archive, not in public-facing summaries.

Additional real metamorphic checks used 1169 (seat 2), the 1396 successor (seat 1), and the red control (seat 1). Only cards the production view classified as unknown had hidden characteristics replaced by canonical Island characteristics, with IDs, membership, public counts and observations preserved. Respectively 37, 26 and 112 unknown records changed. **Full AIDecision equality**, source nonmutation and checked legality held in all three. The targeted information-boundary baseline also exercises both seats, styles, authorized inspections, remembered/private fields and library order. This is bounded evidence, not a proof for every rules mechanic.

## Prioritized proposals — not implemented

1. **Decision-local memo for friendly-destruction utility on the immutable root.** Highest measured opportunity: 1422's 84 evaluations could require only 12 computations if the contract below is proven. Scope strictly to one synchronous `decision_projection_scope`, the exact root state and actor. Key the full announced action (source instance/incarnation, selected face/mode, cost choice, X, targets, additional payments and restrictions) plus an explicit stable choice-policy token. Cache `False` and `None` distinctly. Initially retain complete immutable action data rather than prematurely stripping hints. Never reuse across other states, projected mutations, priorities or decisions. Do not cache by card name or target name.
2. **Reuse baseline settlement within the same root/policy.** `friendly_destruction_profit` separately copies and settles the unchanged baseline after each payable candidate. Share only immutable outcome/value metadata, not the mutable settled state, and only when own-choice behavior is pure/stable. Preserve winner, private/library change and unresolved-choice sentinels. Do not collapse `unknown` into `False`. Measure incremental benefit after proposal 1; much of its work overlaps.
3. **Reduce immutable query/payment recomputation in strategic search.** 1169 shows payment and continuous layers remain substantial independently of destruction. Profile exact repeats at each unmutated search node before adding reuse. Cache parser output by immutable text if useful; effective characteristics require current board/layers/counters/attachments/control/timestamps. Payment feasibility additionally depends on mana pool restrictions, tapped/sick sources, reservations, life, sacrifice/discard availability, target-dependent tax/reduction, alternative cost, snow/hybrid/X/kicker and announced context. Invalidate at each actual state transition; never share a root query cache with a mutated projection.
4. **Copy/serialization work only after the above.** Existing `planning_copy` already omits logs and optimizes flat fields. Further changes must preserve aliases, cycles, RNG, pending choices, printed-versus-current faces, zone-incarnation IDs, linked exile, continuous-effect timestamps and caller isolation. Use current projection-scope tests as a starting point, not a license for shallow copies. Do not remove checked execution or stack settling merely to reduce time.

**Bound-method/closure policy:** a bound method object is freshly allocated on access; identity alone loses legitimate hits. Conversely `__func__` alone conflates agents. Use a retained receiver + function + explicit immutable decision-policy configuration/version token. The current lambda captures mutable `self`; its nested `choose_action` may change strategic bookkeeping. Either make the specific choice policy explicitly pure/decision-scoped or decline memoization when purity is unproven. Distinct closure captures, changed receiver state, opaque callables and unresolved opponent choices must remain separate or bypass the memo. Nested scopes and exceptions must restore outer state; concurrent decisions cannot share the memo.

**Invalidation is a rule, not an afterthought:** even the same Python state/card ID can change zones, controller, costs or incarnation. A card returning to the battlefield is not its old object for targets/effects. Any root mutation invalidates all dynamic results; reconstructed snapshots and other actors get fresh scopes. No cross-game/process cache of hidden or mutable game state is proposed.

## Regression and benchmark acceptance plan

For the production owner:

- Keep these eight pinned states and input hashes as a small benchmark corpus; add later-game Aggro, tax/reduction, modes/X, ward, replacement, nested own choices, unknown opponent choices and blink/re-entry cases before broad adoption.
- In ordinary tests compare complete decisions, full source snapshots, checked result snapshots, payable actions and unknown-state behavior. Compare cached/uncached or old/new paths on canonical states. Assert deterministic call-count reduction for the exact root case (84 to at most 12 original utility evaluations), not fragile milliseconds. Ensure 1169 still has zero destruction calls and unchanged decisions.
- Add cache miss/invalidation tests for changed actor, root mutation between decisions, nested projections, exception exit, concurrent contexts, cost/target changes, source re-entry, bound receiver/config change and opaque callables. Test `True`, `False`, `None`, rejection, draw/library movement and opponent choices separately. Do not silently weaken existing rules regressions.
- Repeat hidden-identity and library-order metamorphic checks for both seats; authorized observations must still affect choices. Verify no instrumentation or cache serializes hidden information into the planning input.
- On a quiet pinned host run baseline/candidate interleaved, at least ten fresh processes and multiple warm decisions per state. Pin source/dependency/fixture hashes, affinity, hash seed and policies. Report distributions/paired CPU and wall differences separately by state and cache regime. Use cProfile separately and report overhead. Set performance budgets in a dedicated benchmark job after measuring noise, not wall-clock assertions in regular tests.
- Require material late-control improvement with no meaningful fast-control/strategic-search regression and no decision/legality/privacy drift. Re-run the focused suites and owner-selected broader rules suite. Only then run a bounded legal trajectory; no full matrix or forced timeout draws are needed to establish this optimization.

## Independent parent verification

The diagnostic rejects execution from a Git worktree or outside local Hermes scratch. No package installation is needed. First verify archive checksums, then extract locally. Example (use a new output directory each time):

```sh
REPO=/home/nick/mtg-ai-performance
ARCHIVE=/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-planning-performance-agent/20261004T221221Z
(cd "$ARCHIVE" && sha256sum -c SHA256SUMS)
RUN=$(mktemp -d /home/nick/.hermes/cache/scratch/ai-performance-parent-XXXXXX)
mkdir "$RUN/source"
git -C "$REPO" archive diagnostics/ai-planning-performance | tar -x -C "$RUN/source"
tar -xzf "$ARCHIVE/evidence.tgz" -C "$RUN"
(cd "$RUN/evidence" && sha256sum -c SHA256SUMS)
cd "$RUN/source/backend"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 taskset -c 0 \
 /home/nick/mtg-deck-testing-lab/backend/.venv/bin/python \
 -m scripts.ai_planning_performance_agent \
 --snapshot "$RUN/evidence/inputs/slow-diagnostic/slow-decision-1422.json" \
 --output "$RUN/verify-1422" --repeat 1 --duplicates
```

Expected: legal count **16**, chosen `pass_priority`, 84 projection calls / 12 unique / 72 duplicates; action SHA-256 `c4cee3cc2482a60fe180cf5312c77fb6b49d2b91d840037cb38d9e27ca86003d`, normalized source `b7c42659ddcd7668918f7c416d90f2635ba48a9d918a7fc4ccfb50733b459e56`, checked result `00e1d9a2ed2b12fef08920a62414d6114201ec32a3b5c3612f9f861446cc2775`. About 22 seconds here, not a required timeout/threshold. Run 1169 with the analogous input and a new output: legal count **28**, Memory Deluge, zero destruction projections, action hash `265f1cabf86deaba6aa6e0d02abcefe19aef4300883353b02e01bece31ee9b70`. `--profile --repeat 1` records a separate binary/text profile. `--repeat 2` without instrumentation provides first/warm timings. All expected primary fingerprints are in `benchmark-table.json`.

## Limits and execution issues

All eight investigation checklist areas have bounded evidence or an explicit implementation/benchmark proposal. Remaining work is production implementation, broader state/mechanic coverage, statistically powered before/after timing and parent independent verification; no optimized speedup or expert AI strength is claimed. Only four archived slow states were reproduced, not all 55 or the entire game. First-process runs are not cold filesystem/import startup. Both actors were exercised, but a complete seat-swapped replay was not run. Full-game agent-history reconstruction is absent. cProfile covered two contrasting slow states, not every sampled state.

Corrected setup mistakes were a module invocation from source root instead of backend, attempting `DeckParser()` without its required repository (replaced by exact quantity/name parsing of the existing fixed builtin text), an aggregation glob matching `.log` files, and a relative script-copy destination from the wrong directory. No production files were touched by these failures. The final copied script was exercised separately in `1422-final-duplicates`, including its repeated-result assertion. Early diagnostic versions/ancillary runs are distinguished in the archive; primary unprofiled timings did not use monkeypatching. The smoke is excluded from the primary table. Successful disposable checkouts are removed only after archive readback verification.
