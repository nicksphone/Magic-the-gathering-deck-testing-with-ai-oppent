# Exact Seed-Backed Builtin Inventory Admission

The shipped builtin text may use an exact front-name seed key while DeckParser
returns that seed record's full canonical DFC name. Admission compares inventories
through only FALLBACK_CARD_DATA's exact dictionary keys and exact payload names.
Aliases aggregate quantities into one canonical counter for each original board.
There is no prefix, face split, case folding, fuzzy lookup, card-name dispatch,
or inferred unsupported-card permission. Foreign seed cards still fail the
specific builtin inventory comparison. Bool/float quantities and changed counts,
board membership, incomplete faces and malformed printed fields still reject.
The existing ready_for_match check is unchanged. No card body, source, snapshot,
board row, game rule, choice, outcome, trace, budget or source-binding field changes.

Only admit_execution_rows in scripts/matchup_round_robin.py changes. The new
whole test module uses the actual DeckParser/ready_for_match source projections
and full public seed payloads with an inert repository/import seam. It is not a
real SQLRepository/native hydration or game certificate. Both printed aliases
and canonical top names pass for all eleven builtin decks without row mutation.
The existing four whole protocol modules are retained unchanged.

Evidence: initial whole50=48PASS2ERROR (the actual inventory ValueError), retained.
Positive tests converted that rejection to explicit strict assertions: wholeNEW6
4PASS2FAIL0ERROR0SKIP0.250 before production edit. Final wholefive50PASS0FES31.433.
SQL/socket/process canaries deny before test collection; provider/backend/engine
imports are denied. Complete ordinary backend source before/end hashes are equal.

The parent actual native attempt's all11 setup succeeded but no game ran; that
prior receipt remains immutable and is not parity evidence. A future attempt
needs a newly measured complete source map including this increment, fresh parent
review/lease and execution admission. Historical7c5 or775 receipts are not silently
relabelled as this corrected-source/native qualification.
