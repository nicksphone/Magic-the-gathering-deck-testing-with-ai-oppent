# Checked current-turn damage sequences

`ai.damage_sequences.winning_damage_action` checks short, unanswered damage
finishes before development or creature-removal heuristics. A fixed printed
damage estimate proposes spells; genuine checked casts, payments and stack
resolution must establish the win. Compound damage/lifegain spells use that
same execution path, not a separate card-name table.

The search is limited to three spells, eight proposals per position and 24
cast expansions. It runs only during the actor's main phase and refuses
opposing stack items, unresolved choices, unsupported-effect diagnostics,
turn/step changes and hidden-library/opposing-hand changes. Own pending spells
can require an explicit priority pass. The next real decision recomputes the
line; opposing passes in these forecasts are a condition, not a guaranteed
opponent response. Printed-damage filtering can miss amplified or otherwise
unrecognized finishes.

The actual decision path retains learned-model validation and checked single
action wins. This addition is a tactical safeguard, not evidence that the
neural policy learned multi-action planning or that the AI is generally expert.
No candidate checkpoint is activated by these tests.

## Regressions

- `test_ai_burn_sequences.py`: paid two-/three-spell finishes, creature and
  development distractors, compound damage/lifegain, insufficient resources,
  genuine resolved prevention and own-stack priority sequencing, both seats.
- `test_ai_damage_sequence_diagnostics.py`: explicitly labelled diagnostic
  fault injection proves that a new unsupported-effect warning invalidates a
  forecast even when simulation copies discard old log history.
- `test_idle_suspend_phase_gate.py`: preserves decision/trace, state, RNG and
  call-count parity against the current route with only Suspend's phase
  optimization removed. Its source pin was rebased without removing checks.

The first 18 sequence tests passed while the two newly added compound-spell
tests failed. Removing the redundant effect-key restriction made all 30 tests
in the sequence and diagnostic modules pass. The earlier 314-case neighboring
cohort passed before that final extension; subsequent whole-cohort receipts
are separate evidence, not inferred from these focused results.

Controlled canonical fixtures are not native training episodes or expert
labels. Native episode traces, preference packets and synthetic full-hand
evidence remain private and are not published as repository fixtures.
