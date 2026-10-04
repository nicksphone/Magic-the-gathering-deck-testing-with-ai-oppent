# Regression Agent: Master AI Planning Performance Investigation

## Assignment

The second canonical rules regression wave is reviewed and reproduced. The
backend owner is repairing its five findings; do not modify or duplicate that
engine work. Investigate the expensive but progressing Blue Control/Ramp game
instead. Deliver reproducible performance evidence and safe optimization
directions, not an AI rewrite or forced deck-balance changes.

## Known evidence

One instrumented reversed Ramp/Blue Control game, seed `299881130`, completed
at turn 52. Its 1,506 choose-action calls totaled 493.35 seconds: median 0.0129s,
p95 0.8214s, maximum 20.31s, 55 above 2s. Captured stacks show repeated
`friendly_destruction_profit` projections from `unproductive_destroy_targets`,
including checked casting and complete stack resolution. This single observed
run is not a benchmark or proof that this is the only performance bottleneck.

The verified archive is:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-repairs/20261004T213559Z/release-and-latency-evidence.tgz`.
Its `slow-diagnostic/` member contains inputs, timing summary, full decisions,
stack captures and 55 slow snapshots. The containing `SHA256SUMS` verifies the
archive. Repeated pair inputs are also in `validated-gates-verified.tgz`, under
`replay-inputs/pair-0.json`. Local temporary copies may be cleaned; use archives
as the durable reference. Do not open archived SQLite files on NFS.

## Boundaries

- Read Graphify first. Work on an isolated branch/worktree based on current main.
- Own a new `docs/testing/ai-planning-performance-agent.md` report and, if
  useful, a new standalone diagnostic script under `backend/scripts/` with a
  unique performance-agent name. Do not edit production AI/rules, current tests,
  frontend, dependencies, shared docs/Graphify or the live checkout.
- Run all probes against disposable source copies and local scratch/databases.
  Do not start a full matrix if representative snapshots answer the question.
- Do not run tests in either live worktree, change card data, peek at private
  opponent identities, relax legality, delete search branches blindly, force
  timeout draws, or target arbitrary matchup win rates.
- Do not alter the first/second-wave regression fixtures or assertions.

## Investigation checklist

1. Verify archived hashes, inspect provenance and reproduce selected saved
   decisions with real production `AIAgent.choose_action` and legal generation.
2. Select several slow and fast controls across distinct turns/steps/boards.
   Measure repeated timings in a pinned environment, recording cold/warm runs,
   process CPU/wall time, source commit and profiler overhead separately.
3. Profile call counts and cumulative cost of destruction projections, legality,
   copying, mana/target enumeration, continuous layers and stack settling. Count
   repeated identical work within one decision; report actual inputs/cache
   boundaries rather than assuming the captured stack explains everything.
4. Confirm selected actions are checked/payable and source snapshots do not
   mutate. Preserve the decision fingerprint and relevant known-information
   constraints. Compare both seats and include another representative archetype
   using existing canonical decks when feasible.
5. Propose minimal shared optimizations with explicit invariants: decision-local
   cache lifetime/keys, mutable-state invalidation, bound-method choice policies,
   dynamic targets/costs, and source identity/incarnation. Identify where reuse
   would be unsafe. Do not implement production patches in this assignment.
6. Supply a regression/benchmark plan that can prove improved latency without
   weakening decisions, legal payment or hidden-information boundaries. Avoid
   fragile hard wall-clock assertions in ordinary unit tests.
7. Archive commands, profiles, sanitized summaries and selected snapshots on
   verified writable NFS under
   `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-planning-performance-agent/`.
   Verify copies before cleaning successful disposable checkouts.
8. Commit only owned report/diagnostic files and return commit IDs, reproducible
   commands, measured bottlenecks and prioritized recommendations. No merge,
   deployment, restart, force push or claim of completed expert-level AI.

The parent owns production implementation and the final combined verification.
