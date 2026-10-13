# AI Plan Acceptance Progress

Checked against published `8ad9724fb69641a731f39ed7a2074962f5dce57c` on
2026-10-13. This records requirements, not a completion percentage. The five
phases in [the AI plan](../plans/2026-09-09-ai-knowledge-base.md) are a subproject;
they do not replace the three release gates in [plan.md](../../plan.md).

## Implementation And Acceptance Are Different

| Phase | Existing implementation or observed evidence | Required acceptance still open |
| --- | --- | --- |
| 0: Measurement | Baseline reporter, decision-quality aggregation, and the committed pre-baseline exist. | The pre-baseline explicitly marks `bad_blocks` unavailable. Establish comparable observed metrics before claiming the complete before/after benchmark. |
| 1: Knowledge | Models, repository, canonical seed, sync and completeness CLI exist. On immutable current `8ad9724f`, the actual default 149-name CLI and separate complete 155-name report both pass; real owned repository ingestion checks 155 shipped identities, 443 rulings and 35 verified empty ruling lists. Profiling updates 155 rows, then zero on repetition. | The fresh image directory has zero local-image/placeholder files despite cached identity coverage. Additional stored/user-deck coverage, local images and deployment are not proved by shipped-corpus results. |
| 2: Tactical profiles | Deterministic derivation, persisted profile transport, production tag consumers, checked removal and blocking improvements exist. | Finish matched seed/seat-balanced A/B counters and current whole-source acceptance; component scenarios alone do not establish better play. |
| 3: Matchup knowledge | Round-robin runner, deterministic learned-profile loader/deriver and contextual-prior consumer are implemented. Ten genuine equal-budget reference/observed games matched. | The actual 110-series run ends incomplete: 100 resolved series, ten resource-limited series, exit 3. A separate same-limit one-series diagnostic observes a shared-budget deadline at 600.29 seconds, not proof of every old limit cause. Complete admitted data, learned/context artifacts and non-regression comparisons remain required. |
| 4: AI improvements | Canonical lethal and interaction-hold controls are integrated. A reviewed combined cohort passes 2,998 cases; separate cold HTTP/restart and genuine six-game, both-seat BO3 evidence includes nine actual different-card sideboard swap units. | These bounded results do not measure better play. Complete the specified matched seed/seat quality comparisons, before/after strength checks and final tuning acceptance. |

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
3. Diagnose the completed matrix's resource-limited series without changing
   rules, weights, winners or clocks; qualify complete data before deriving
   learned/context artifacts. The incomplete matrix is not training input.
4. Run matched before/after decision-quality and strength measurements, then
   complete current-source CI and the outstanding original release gates.

No phase, release gate or total-project percentage is certified by this note.
