# Legacy Land Route Audit

## Parent Candidate Follow-Up

The separate all-four mana intent guard is now composed in the isolated parent
candidate. Its 261-case gate passes with no skips, exclusions or expected failures:
all twelve field-drop regressions pass unchanged, together with the raw-route,
typed-payment, actual-AI, public-hint and consumption-reservation controls.
The original 48-pass/12-fail audit below is historical baseline evidence, preserved
in its immutable archive. An earlier parent full-audit attempt reached its
120-second bound after 34 passes; that partial run is not a complete baseline or
diagnosed performance bug. No live deployment is claimed.

NEW tests/report only over frozen mana composition. No production fix is included.

Dedicated tap_land_for_mana and tap_lands_bulk use nonempty tap_only_outputs
and preferred_free_spec(tap_only=True). Funded Tower sacrifice-B, Coffers paid-B,
filter branches and paid Coffers/Sphere-C cannot bypass via these routes.
Both-seat core/HTTP rejected requests preserve root/controller/SQLite dumps.
For filter lands under Sphere, a free-C and a paid mixed ability can advertise the
same final C; traced executor indices prove only the free tap-only index executes,
with branch fuel preserved. Fixed Simic Growth Chamber GU under Sphere is valid
tap-only production, not a paid-ability bypass. Basic Forest explicit and raw-HTTP
omitted colors remain accepted; training intentionally requires an explicit color.

Confirmed separate consumer defect: legacy lookup_intent strips requested
ability_index, output_bundle and unknown_choice through complete_action. Strict
encoded lookup and raw HTTP reject those exact requests. Twelve unxfail strict
regression cases (both routes, both seats, three fields) intentionally remain red;
do not describe the whole audit as passing or silently normalize the fields away.

Proposed narrow followup, NOT implemented: extend the existing training mana
lookup_intent allowlist guard to all four mana action types using each matching
Action model's fields plus explicitly known presentation fields. Reject requested
fields outside that set BEFORE complete_action. Keep optional raw-HTTP colors,
known required_choices presentation, strict indexed selected actions and internal
executor None planning unchanged. No cast/mana/executor/API edits are needed.

This consumer issue does not prove raw HTTP can activate a paid/non-tap-only
ability. No mixed-output redesign, GUI, full-hand performance or neural claim.
