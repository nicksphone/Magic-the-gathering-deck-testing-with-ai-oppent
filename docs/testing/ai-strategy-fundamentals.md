# AI strategy fundamentals

Basic strategic mistakes are AI-readiness failures, even when actions are legal.
Neither a large regression count nor the decision-performance benchmark proves
that the AI pilots complete decks well.

## Policy correction

The anti-stall fallback previously discarded strategic ranking in favor of
separate burn, tempo and cheap-cast preferences. A payable Cultivate could rank
first yet lose to Consider, consuming the mana needed to ramp that turn. Burn
also lacked the aggressive creature-development bias used by Aggro and Tempo.

Conversion now retains the ranked order and existing legality/reservation
filters. The duplicate cheap-cast override in pass recovery is removed. A
potentially lethal printed damage amount is only a prefilter: a materialized
action gets priority only when the checked unanswered-action forecast confirms
a win. Unknown or nonwinning forecasts fall through, rather than eliminating
the candidate. This is not a claim that the opponent cannot respond.

Only three methods in `backend/ai/agent.py` change: `_cast_bias`,
`_best_proactive_non_pass` and `_avoid_pass_with_main_phase_options`.
Game rules, card facts, difficulty settings and hidden-information boundaries
are unchanged.

## Bounded evidence

`test_ai_strategy_fundamentals.py` contains 40 canonical controlled cases across
both seats and Strong/Master:

- Burn, Aggro and Tempo resolve Swiftspear before nonlethal burn, then deal five
  actual damage through prowess and checked combat, rather than four.
- With one available mana and the opponent at three life, those same styles
  take the checked immediate burn win instead of developing a creature.
- Control counters a real paid lethal Bolt instead of cantripping.
- Midrange removes Sheoldred rather than the small mana creature beside it.
- Ramp resolves Cultivate into a real additional land and a land in hand;
  direct pass recovery retains that ranked choice over the cheap cantrip.

The decision checks also exercise snapshot restoration, unchanged authoritative
state and hidden-library-order invariance. They do not use the AI's own scores
as the outcome oracle.

The final isolated gate passes 422 cases in eleven complete AI modules,
including the prior Burn, real lifegain-prevention, suspend, combat, resource,
recurring-engine and public-forecast regressions. The runner denies SQL,
socket and process launches; its denial ledger is empty. No live game actions
are taken by these tests.

Historical draft fixture errors and intermediate policy failures are retained
privately with the test evidence, not relabeled as successful gates.

## Remaining limitation

These are basic tactical and sequencing goldens, not a full-game, matchup,
sideboarding, combo, competitive-strength or all-archetype certificate. Full
matches still need review for avoidable mistakes, not just wins or legality.
The immediate-win preference described here applies when the conversion
fallback is reached; this change is not universal tactical search.
