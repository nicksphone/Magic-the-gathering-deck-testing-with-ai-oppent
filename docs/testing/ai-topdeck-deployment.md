# Unknown-Library Deployment Decisions

## Cause And Shared Repair

The strategic horizon correctly refused to resolve unknown library choices, but
charged deployment costs without crediting their possible benefit. It could pass
with a payable top-library deployment spell despite a useful remaining deck.

For supported creature/permanent top-library deployment, estimate eligible hits
from the pilot's submitted list minus observed own inventory. Use an exact
hypergeometric expectation of the best capped printed-value hits. No unseen card
identities/order, opposing submitted list, hypothetical ETB outcome or gameplay
object is consulted or invented. Public entry prohibitions and type/mana-value
caps still apply. Instant deployment respects existing interaction reservation.

Canonical mana value is distinct from payment: Reaper King's five two-or-color
hybrid symbols have mana value ten, not five. The estimate uses the same shared
mana-value function as the rules, preserving snow and hybrid symbol accounting.

## Executed Evidence

- Exact historical prefix: 754 lines, turn 19 precombat main, Master Ramp versus
  Tokens. Before: pass on seven repeats. After: Storm cast on seven repeats.
  Root immutable and deterministic; priors match production byte-for-byte.
- Exact-config worker median: 0.335 seconds before, 0.331 after. This is one
  retained decision, not a whole-match latency or expert-strength claim.
- Isolated live-code and composed-code gates each passed 536 affected tests.
- After review corrected mana-value accounting, the isolated live-code delta
  gate passed 188 tests; worker's corresponding delta gate also passed 188.
- Coverage includes both seats, fourteen archetypes, opaque library identity/order
  changes, snapshot reload, affordable/unpayable casts, MV whiffs, entry prohibition,
  selection spells and modest instant deployment that must preserve counter mana.

Evidence: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/holding-spells/`.
Private historical snapshots stay out of committed fixtures.

## Remaining Limits

This is bounded evaluation, not learned policy or complete card semantics.
Unreconciled inventory, known ordered candidates, mixed library-changing effects
and unsupported face models receive no guessed benefit. Printed creature values
do not fully model synergies, future interaction or ETB effects. Natural multi-deck
diagnostics and the broader training/data groundwork remain unfinished. The saved
decision proves a missed payable spell, not guaranteed survival or balanced wins.
