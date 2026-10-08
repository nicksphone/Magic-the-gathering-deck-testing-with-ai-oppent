# Late-Game AI Combat Safety

Base: immutable `602e9c8`, with the same rules/AI bytes as `13973bd`.
This is a measured decision-quality repair, not expert strength or release acceptance.

## Defect And Repair

On full canonical Archangel of Wrath versus Atraxa boards in both seats, the
actual master Control policy waited at turn 19 but attacked at turn 20. A real
checked attack/block/combat replay put the attacker in the graveyard, left the
blocker on the battlefield and increased the opponent's life. Query roots were
unchanged. The only reason for the changed decision was the late-game progress
route: when the normal combat evaluator chose no attackers, a fallback bypassed
it based on keyword presence or power alone.

The repair deletes that fallback and its sole call. The existing combat evaluator
still selects attacks; the turn counter can no longer override a refusal.
No weights, card-name rules, hidden-information access, search depth, engine rules,
public schema or action validation changed. AST comparison verifies every other
agent definition unchanged. Both-seat tapped-blocker controls still choose and
execute profitable attacks. The full canonical rows and provenance are retained.

## Actual Gates

- Original policy plus six NEW controls, five whole modules: 180 passes and two
  desired turn-20 failures, 32.08 seconds, exit 1.
- Corrected policy with original legacy test: 179 passes and one historical
  expectation failure, 32.57 seconds, exit 1; four NEW controls at this stage.
- Corrected policy with expectation-only legacy adaptation: 181 passes and one
  mock-fixture failure, 32.51 seconds, exit 1.
- Final policy and actual-state legacy fixture: five whole modules, 182 ordinary
  passes, 32.72 seconds, exit zero; no skips, xfails or deselections.

The original five-module ordered case list is preserved except the explicit
single legacy test rename. That test formerly required a 3/3 to attack a 4/4 at
turn 26. Its expected action now holds instead; all original board values are
preserved, converted to actual MatchState/PlayerState/CardInstance models so
the planner can execute real rules rather than a duck-typed mock approximation.
This adaptation is a separately preserved diff, not a hidden policy workaround.
All other old test bodies remain unchanged. Every raw failure ledger is retained.

The runner installed native SQL/socket/child denial before project imports.
Four constructor/launch controls failed closed; no unexpected I/O occurred and
source hashes matched before/after each final gate. This is a pure cohort, not
application-lifespan, SQLite, browser, physical-resource or operator acceptance.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-late-progress-safety-product-20261008-qDCbHC/`.
The independent baseline audit is also retained under
`diagnostics/ai-progress-attack-baseline-20261008-qDCbHC/`.
The separate six-game archetype probe used the old immutable policy; five games
completed and the sixth hit its declared wall bound (exit 124). It is not
retroactively relabeled as a post-repair run. Full-game policy comparison,
broader decision benchmarks and current mixed/browser acceptance remain open.
