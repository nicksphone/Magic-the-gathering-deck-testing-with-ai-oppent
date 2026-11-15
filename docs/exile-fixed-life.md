# Complete Exile And Life Gain

An exile instruction with a fixed life reward for its target's controller must
not fall through to a plain-exile substring. The compiler consumes the complete
two-sentence body, including the existing controlled-type mana-value condition.
Unrecognized trailing text in this family produces an unsupported diagnostic,
not partial exile or a partial reward. This is structural grammar, not a card-name
exception.

The compiler preserves the native two-effect sequence: exile, then gain life.
Immediately before that sequence executes, the existing sequence resolver captures
the resolved target's actual controller and prepares the gain payload before any
departure or pending-choice continuation. It reads the actual child target, not a
separate cast-time ID that could become stale after retargeting. The existing
replacement-aware life-gain handler is unchanged. Ownership still determines the
exile-zone list. A target that becomes illegal before resolution neither leaves
nor rewards a player. Power-based life gain retains its existing behavior.

`backend/tests/test_exile_fixed_life.py` uses unchanged canonical fixtures for
paid Lay Down Arms, a real Unsummon response, foreign ownership, Tainted Remedy,
and Alhammarret's Archive. Malformed suffixes are explicitly synthetic parser
negatives. The new module first produced fourteen assertion failures and four
passes. The initial atomic-exile implementation passed those desired outcomes
but broke four existing compound-shape assertions in the broader run; that result
is retained, not reclassified as a pass. The correction preserves the original
two-step contract and leaves the original tests unchanged. These component
results do not qualify a learned policy, general spell-copy retargeting, or all
exile instructions.
