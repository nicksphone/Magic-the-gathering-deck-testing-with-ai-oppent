# Instant Value Windows

## Observed defect

The completed selection370 Tempo/Dimir replay (seed 545890033, second seat,
decision 524) cast a seven-mana flashback selection spell in the opponent's
upkeep while holding two counters. The following opposing spell could not be
countered. Winning that game does not make this decision optimal.

The shared control draw bias awarded the same 2.4 timing bonus during any
opponent step as during their end step. A canonical both-seat regression
reproduced identical upkeep and end-step biases of 7.6 before the repair.

## Implemented Behavior

- Award that timing bonus only during the opponent's end step, not their upkeep
  or the player's own end step before the opponent untaps.
- For empty-stack opponent-turn instant value spells, price loss of the last
  currently affordable own-hand instant counter/removal option. Use the actual
  checked announcement/payment on a planning copy, including flashback costs.
- Apply the same opportunity cost to ranked actions and strategic lines, for
  every archetype. This changes scores, not rules or the legal-action list.
- Do not penalize existing stack responses, spells also tagged as interaction,
  own-turn lines, end-step/cleanup lines, or conservatively possible lethal
  public creature pressure. No unseen library or opponent-hand identity is used.
- Leave affordable follow-up interaction and existing forced end-step behavior
  intact. Forced closure/inevitability paths already require own main phase.

## Evidence and remaining acceptance

`backend/tests/test_ai_instant_window.py` covers both seats, four archetypes,
canonical Deluge flashback plus Impulse/Anticipate, snapshot purity, stack and
hidden-hand invariants, and actual Master upkeep pass/end-step cast decisions.
The focused 24 cases pass; the final combined decision/search/pass/resource
selection passes all 260 tests after preserving the existing lightweight-state
contract. Runtime `40302dc` subsequently passed 8,674 backend tests and the full
browser suite. It is now part of the consolidated main runtime; see
[integration evidence](backend-consolidation.md).

The completed natural review covers Drain/Tribal, Tokens/Ramp and Tempo/Control:
six unique seeded, seat-balanced games, each repeated twice. All twelve private
decision reconstructions match; the runner reports no determinism failures,
drift labels or anomalies. Ten executions retain the predecessor result/log.
Tempo/Control seat two changes consistently in both repeats, with first decision
divergence at index 524, 634 decisions and a player-one win at turn 23.
Reconstruction establishes reproducibility, not optimality or improved win rate.

This is a bounded heuristic, not an optimal-timing proof. It does not estimate
the opponent's unseen spells, distinguish every removal target, handle all
variable-cost answers, or prove emergency combat outcomes. The six-point
reservation price still requires tactical evaluation of the changed decision;
broader timing, counter-risk estimation and competitive-strength evidence remain
open. No canonical Oracle text, card stats or natural decklists were changed.
