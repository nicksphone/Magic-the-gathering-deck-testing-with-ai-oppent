# Loyalty Counter Costs

Positive loyalty activation costs now use the same scalar counter-event resolver
as registered counter effects. The ability is announced on the stack before its
cost is paid. Ward and other staged triggers wait until payment and replacement
choices finish; state-based actions do not run during an unfinished cost.

The initial event is a cost, not an effect. Doubling Season alone does not double
it. Vorinclex and Lae'zel can modify it; a replacement can then make the event
eligible for an effect-only modifier. A replacement reducing the added counters
to zero still pays the announced cost. Negative loyalty costs remove counters
and are not treated as counter placement. These distinctions follow rules
118.11 and 614.16 in [Wizards' Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf).

Competing order uses existing human/AI replacement controls. Snapshots retain the
announced ability, used modifiers, once-per-turn reservation, staged triggers and
activation controller. Resumption does not announce or pay the ability twice.

## Checks

- 116 focused checks pass, including 12 new cases with canonical Elspeth, Ugin,
  counter-modifier and Tolarian Terror data. Seat-two Ugin checks ward staging
  through multiple choices and snapshot recovery.
- Frontend lint, unit contracts and TypeScript/Vite build pass.
- The final full backend suite passes: 2,336 tests, 292 warnings, 227.18 seconds,
  in an isolated tracked-source checkout. An earlier run with 11 new tests
  passed 2,335; it is superseded by the final 12-case run.
- The full existing Chromium harness passes, including both-seat actions,
  replacement controls, recovery, sideboarding and natural BO3 flows. It does
  not add a new loyalty-specific browser scenario.
- A separate HTTP probe announces seat-two Ugin, restores its pending cost via
  the startup SQLite restore helper, then submits two AI-selected order choices
  through the human action contract. Loyalty reaches 19 and ward is placed above
  the single announced ability. This is not a live-process restart test or an
  autonomous full-match strength measurement.
- A seat-balanced six-game/two-series BO3 smoke replay reports zero determinism
  failures, empty drift labels and empty anomaly counts. This is not statistical
  balance or broad strategic-quality evidence.
- Graphify AST refresh passes: 7,354 nodes, 18,375 edges, 314 communities.
- Detailed logs live in the RCHFiles project diagnostics folder under
  `loyalty-counter-costs/`; active test checkouts remain local and disposable.

## Remaining Scope

Initial loyalty on entry is a different event and remains unfinished. General
counter-placement costs, pre-entry replacement packets, turn-based Saga lore,
multi-kind counter events, movement, spending and proliferation remain open.
This increment does not certify all planeswalker cards or professional AI play.
