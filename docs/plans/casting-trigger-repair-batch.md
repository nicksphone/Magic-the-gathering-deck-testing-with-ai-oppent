# Casting and trigger repair batch

## Evidence and scope

Regression-agent handoff: `b94c477`. Parent reproduction uses committed main
`d58dbec` plus only the seven new test/fixture/report files in a disposable
checkout below `/home/nick/.hermes/cache/scratch`. The 40 new cases produce
34 passes and six failures, reproducing all reported mismatches. No original
assertions, canonical Oracle text, or live database were changed.

Treat the test report as evidence, not as an implementation specification.
Use its retrieved Scryfall records/rulings and pinned Comprehensive Rules.
Repairs must support the recognized instruction families, not card-name hacks.

## Checklist

- [x] Review the canonical second-wave handoff and reproduce on current main.
- [x] Preserve sacrificed creatures' paid-cost last-known characteristics in
  durable stack packets. Compile recognized sacrifice-linked damage through the
  common damage handler; verify countered spells, changed stats, departure
  replacements, tokens, both seats, restart and illegal sole-target behavior.
- [x] Preserve occurrence-specific target requirements and distinctness for
  ordered counter-placement instructions. Resolve surviving targets with their
  announced allocation; reject duplicate required-different targets before
  payment without banning repetitions that other spell clauses permit.
- [x] Add supported ETB flashback grants through ordinary trigger target choice,
  durable object references and temporary permissions. Share actual cost and
  expiry logic with native flashback, preserve X/additional kicker, prohibit
  competing alternative costs, and validate departure/reentry and restart.
- [x] Add bounded self-return-to-hand graveyard-from-battlefield triggers using
  predeparture ability/controller information and the correct new graveyard
  object reference. Verify suppression, replacement to exile, stale references,
  ownership, attachments and snapshot resume.
- [x] Keep unsupported clauses explicit in coverage diagnostics; do not admit
  a paid no-op as complete semantic support.
- [x] Expand production AI decisions for the newly supported actions and actual
  payments without consulting private opposing identities. Check multiple
  archetypes and legal choices; legality alone is not optimal-play evidence.
- [x] Run the 40 canonical tests, focused neighboring cost/target/trigger tests,
  HTTP/SQLite boundaries, complete isolated backend/frontend/browser gates,
  and pinned seed/seat-balanced repeated matches before publication.
- [x] Archive verified evidence on RCHFiles, update README/CHANGELOG/plan and
  Graphify, publish the milestone, and clean completed disposable copies.

Acceptance evidence and bounded support are recorded in
[the repair report](../testing/casting-trigger-repairs.md). General payment
ordering and unrecognized grants/instructions remain outside this milestone.

## Separate performance investigation

The instrumented Blue Control/Ramp reproduction completed at turn 52 with
1,506 decisions. Observed choose-action time totals 493.35 seconds, median
0.0129 seconds, p95 0.8214 seconds, and maximum 20.31 seconds; 55 decisions
exceeded two seconds. These are one instrumented run's observations, not a
production benchmark. Captured stacks identify repeated friendly-destruction
projections through checked actions and stack resolution as a hotspot.

Optimize decision-local reuse or avoid provably redundant projections only
after retaining representative snapshots and baseline decisions. Do not remove
search, cap a slow but valid game as a draw, or force arbitrary win rates.
Evidence is in the verified `release-and-latency-evidence.tgz` beneath
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-repairs/20261004T213559Z/`.

## Acceptance boundaries

No full Magic certification, expert-AI claim, or fixed matchup win-rate target
follows from this batch. Global replacement/layer dependencies, broader
permissions/cost mechanics and long-session competitive quality remain tracked
in the finish plan. Do not merge intentionally failing tests into the published
main gate or mark proposed repairs complete before their actual checks pass.
