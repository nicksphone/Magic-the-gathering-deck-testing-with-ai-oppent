# Targeted Draw Replacement Safety

This follow-up modifies the Forge Team/Card-Forge `DrawAi`; their full upstream
copyright and GPL-3.0-or-later headers remain in the copied source. `LICENSE`
retains the upstream licence. The complete source pre/postimages, zero-fuzz
patch and unchanged canonical scripts are included. This is our modification
of their implementation, not a card engine or AI authored from scratch here.

The first draw draft fixed an opponent-target veto and an equality boundary,
but four new cases exposed unsafe decking predictions. Jace's replacement can
win instead of losing, and Spirit of the Labyrinth can stop the required second
draw. Separate actual paid native executions established these outcomes.

The generic correction requires `opponent.canDraw(librarySize + 1)` and checks
known, active Draw replacements for native WinsGame instructions. Card visibility
is checked before replacement-body access; native suppression, zone and affected
player filters remain. The instruction traversal is identity-cycle-safe. It does
not evaluate an empty-library condition against the earlier nonempty library,
enumerate unknown replacement bodies, or use Jace/Maniac card-name branches.

The unchanged original 12, prior ten safety checks, eight replacement checks and
four new positive checks give **34 AI passes**. The draft had four failures in
this same cohort. The positive controls retain Teferi's Ageless Insight decking
and actual paid Jace departure followed by a legal decking win. Four separate
explicit-target replacement executions pass but are **not AI-choice passes**.

Each fresh JVM uses one declared seed before model initialization, unchanged
native clocks and actual selected abilities, payments, stack resolution and
outcomes. Full canonical cards were pinned before fixtures. No named-card patch,
forced cast, seed search, model replacement or live adoption is involved.

This is a conservative structural guard, not complete conditional-branch or
replacement-outcome analysis. Broader natural-game quality, draw replacement
interactions and hidden-input fairness still need review. The initial draft and
all failing ledgers are retained, not relabelled as passing.

See the [combined runtime qualification](../../../../../docs/testing/native-linked-draw-ai.md)
for the independently rebuilt linked-damage/draw composition and app scope.
