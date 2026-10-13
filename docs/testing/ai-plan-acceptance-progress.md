# AI Plan Acceptance Progress

Checked against published `837bf5137a2adaa62a32942ccbde15a568c43545` on
2026-10-13. This records requirements, not a completion percentage. The five
phases in [the AI plan](../plans/2026-09-09-ai-knowledge-base.md) are a subproject;
they do not replace the three release gates in [plan.md](../../plan.md).

## Implementation And Acceptance Are Different

| Phase | Existing implementation or observed evidence | Required acceptance still open |
| --- | --- | --- |
| 0: Measurement | Baseline reporter, decision-quality aggregation, and the committed pre-baseline exist. | The pre-baseline explicitly marks `bad_blocks` unavailable. Establish comparable observed metrics before claiming the complete before/after benchmark. |
| 1: Knowledge | Models, repository, canonical seed, sync and completeness CLI exist. Real owned repository ingestion checks all 155 shipped identities, 443 rulings and 35 verified empty ruling lists. | The report's additive fields and cached double-faced image identity require their corrected composition. Additional stored/user-deck coverage and deployment are not proved by shipped-corpus results. |
| 2: Tactical profiles | Deterministic derivation, persisted profile transport, production tag consumers, checked removal and blocking improvements exist. | Finish matched seed/seat-balanced A/B counters and current whole-source acceptance; component scenarios alone do not establish better play. |
| 3: Matchup knowledge | Round-robin runner, deterministic learned-profile loader/deriver and contextual-prior consumer are implemented. Ten genuine equal-budget reference/observed games matched. | The full 110-series matrix is running separately, not terminal evidence. Validate its actual receipts, generate the learned table and contextual priors, and complete non-regression comparisons. No learned table is published yet. |
| 4: AI improvements | Canonical lethal scenarios and the published interaction-hold correction have component evidence. Play-ordering and private-fact sideboard changes have isolated tests and remain under composition review. | Complete current-source integration, real sideboarding/restart and natural BO3 swaps; then run the specified measured A/B and final tuning acceptance. |

Thus "phases 2, 3 and 4 are unstarted" is not an accurate description of the
code. "Those phases are complete" is also unsupported. A commit count cannot
resolve this distinction, and these phases are not equal units of effort.

## Evidence Boundaries

- [Current clean install and shipped knowledge](current-clean-install-knowledge-acceptance.md)
  describes the separate exact-source install and real repository/CLI executions.
- [Phase 3 groundwork](ai-phase3-groundwork-current.md) distinguishes tested
  producer/consumer protocols from genuine terminal matchup data.
- [Interaction hold](../qualification/task42-stable-counter-filter.md) documents
  checked canonical decisions and the current 591-case composed component.
- [Release acceptance](release-acceptance-status.md) keeps whole application,
  browser, LAN, operations and broader rules requirements separate.

The committed `docs/plans/baselines/2026-09-09-pre.json` is retained exactly.
Its `unavailable_metrics.bad_blocks` value is missing measurement, not a zero
bad-block result. Later measurements need comparable definitions, source,
seed/seat schedules and explicit unavailable counters; do not manufacture a
zero to make an A/B comparison pass.

## Next Acceptance Milestones

1. Integrate independently reviewed corrections while retaining the published
   counter policy and all prior test assertions.
2. Qualify real sideboard transitions, owned SQLite/HTTP and cold restart,
   including the original mixed-I/O tests and a naturally played BO3 swap.
3. Inspect the full matrix only after its actual terminal and resource closure;
   derive learned/context artifacts from genuine admitted data.
4. Run matched before/after decision-quality and strength measurements, then
   complete current-source CI and the outstanding original release gates.

No phase, release gate or total-project percentage is certified by this note.
