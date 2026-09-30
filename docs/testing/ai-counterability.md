# AI Counterability Decisions

Counter targeting now uses the engine's shared spell-counterability check. Among opposing legal stack targets it prefers a counterable object before comparing threat scores. The AI declines supported single-effect spell counters when all eligible spells are protected, including preselected targets. This is an AI decision guard, not a change to human cast legality.

Single-effect classification uses full Oracle-clause matching after reminder text removal. It covers ordinary typed spell counters, printed mana-value bounds and the supported "unless its controller pays" wording. Extra clauses and compound selected modes are not treated as pure counters. Modal scoring reduces a pure counter mode's value when it has no effective target; independently useful modes remain available. Ability targets do not inherit their source's spell-only protection.

## Reproduced Before and After

The baseline is `6a8119f`. Canonical fixtures use Carnage Tyrant, Allosaurus Shepherd, Cultivate, Lightning Bolt, Counterspell, Negate, Spell Pierce, Stifle and Cryptic Command.

| State | Baseline decision | Updated decision |
| --- | --- | --- |
| Carnage Tyrant alone on stack | Spend Counterspell on the protected spell | Hold Counterspell |
| Cultivate protected by battlefield Shepherd | Spend Counterspell on protected Cultivate | Hold Counterspell |
| Protected Tyrant and opposing Lightning Bolt | Counter the higher-scoring protected Tyrant | Counter Lightning Bolt |
| Protected Shepherd spell and battlefield Spinner | Cryptic counter/draw | Cryptic draw/return |

The comparison retained full initial snapshots, legal moves and both decisions; neither agent mutated the queried state. These are deterministic decision fixtures, not full-game balance evidence. The 17 new tests fail 15 cases against the baseline and pass against the updated agent. They cover three difficulties across Control, Tempo and Midrange, repeated hold decisions, tax counters, mixed stacks, legal Stifle materialization, compound counter/draw preservation, mode resolution and preselected-target bypass prevention.

Run the tracked regressions from an isolated source/database copy:

```sh
python -m pytest -q tests/test_ai_counterability.py tests/test_ai_decisions.py tests/test_copy_stack_characteristics.py tests/test_counterability_scope.py
```

## Verification

The isolated backend suite passes 1,610 tests. Frontend lint, build and unit checks and the full Chromium harness pass. A three-game seeded BO3 replay reports zero determinism failures, drift or anomaly labels.

Eight verbose games use Tempo/Dimir seeds 710-711 and Tribal/Blue Control seeds 720-721, with both seat orders. All finish by life loss without timeout or logged cast-time target/mana-cost rejection. The existing decision-quality proxies report zero missed lands, lethal misses, bad blocks or stall streaks. Dimir wins all four Tempo games; Blue Control wins three of four Tribal games. This small sample neither establishes matchup balance nor proves optimal decisions. Both hands and boards are present in the game traces; full stack-object evidence is a remaining diagnostic task, so these proxies do not certify counter timing throughout the matches.

Manual log follow-up found an uncovered resource error at Dimir/Tempo seed 711 with Dimir in seat one: Dimir queued two Fatal Pushes and two Go for the Throats against one Sprite Dragon before passing priority. Tempo countered one Go for the Throat; the other destroyed the Dragon, leaving both Pushes without a legal target. This is not a cast-legality failure, but it is poor removal conservation and demonstrates a blind spot in the current quality proxies. Pending-removal awareness is the next active AI task. Ordinary counter-tax nonpayment and target invalidation at resolution also occur in these traces; they are not automatically engine errors.

## Known Limitations and Next Upgrades

This guard is bounded by the engine's currently supported counterability clauses. It does not certify temporary/mana-granted protection, ability-removal dependencies or every conditional counter grammar. Unrecognized compound text is retained rather than silently classified as a pure counter. Valuing arbitrary secondary effects, planning protection removal before a counter, broad archetype decision-quality matrices and expert-level play remain open. There are no card-name branches in the production decision code.
