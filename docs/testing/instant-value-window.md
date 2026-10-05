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
contract. Exact-source full and natural qualification remain pending.

This is a bounded heuristic, not an optimal-timing proof. It does not estimate
the opponent's unseen spells, distinguish every removal target, handle all
variable-cost answers, or prove emergency combat outcomes. The six-point
reservation price requires natural before/after review; broader timing,
counter-risk estimation, forced-choice parity, exact-source full qualification
and deterministic seat-balanced matches remain open. No canonical Oracle text,
card stats, natural decklists or win rates were changed. Main/live are unchanged.
