# Postcombat resources and qualified continuous effects

Date: 2026-09-30 UTC.

## Implemented

The unblocked-attack shortcut now compares the damage from ready mana creatures
with fixed-cost casts available from the AI's actual hand after combat. A
planning copy advances to postcombat main and clears floating mana; real legal
move generation/payment handles colored, generic, mandatory colorless, flexible
and multi-mana sources, cost increases, selected faces and summoning sickness.
The forecast greedily releases redundant higher-power sources when an equally
valued cast remains payable. Vigilance sources can still attack without losing
their mana. Late-game forced progress cannot simply undo this reservation.
Both seats and ten archetype labels share this path; opposing hands are not read.
Payment permission is unchanged. Land and nonland source readiness now share one
helper rather than duplicated payment/snow collection logic.

Testing vigilance exposed a real layer gap. Qualified continuous subjects now
recognize token/nontoken, permanent-type, color/non-color, supertype and tribal
qualifiers instead of interpreting every modifier as a creature subtype.
Supported scoped keyword grants/removals apply to noncreature permanents too:
Darksteel Forge protects artifacts, Privileged Position protects other
permanents, and Avacyn protects lands as well as creatures. Static layer readers
exclude later activated/triggered effect bodies and quoted granted abilities;
unactivated Mutavault animation and Shadowspear keyword removal no longer apply
as unconditional ongoing layers. Cached parsing uses immutable Oracle strings,
not mutable game state.

## Fixtures and validation

Two new fixture files contain twenty canonical local Scryfall rows each, with
Oracle/source provenance. No gameplay card definitions or built-in decks were
invented or changed. Forty new tests cover both seats, actual postcombat
casting/resolution, finite flexible sources, mandatory colorless payment, taxes,
vigilance, source redundancy, snapshot purity and hidden-information invariance;
continuous tests cover actual token creation, color stacking, protection,
destruction/target checks, effective views and snapshot restoration.

All six continuous regressions fail in an isolated parent checkout and pass
here. Final focused run: 81 passed. Full final-code isolated backend suite:
1,875 passed, 229 warnings, 298.81 seconds. Frontend lint/build/unit checks and
the full Chromium action/choice/simulator/recovery/sideboard/natural AI and human
BO3 harness pass. These runs never use the live SQLite database.

Eight seeded, seat-paired logical games cover Control/Tempo, Tokens/Ramp,
Midrange/Drain and Tribal/Burn. Repeated executions retain identical reported
game results, including full identity-sensitive logs; elapsed timing is excluded.
No timeouts occur. One logged inability to pay is Spell Pierce's optional {2}
resolution payment against Counterspell, also present in the identical parent
trace, not a rejected cast. No cast-cost or invalid-target rejection is logged.
All eight traces are unchanged from the parent smoke; these games therefore do
not establish that the new tactical branch was exercised. The runner does not emit every
internal final-state field. See [compact results](ai-postcombat-mana.json).
This sample does not show how often the new tactical branch is reached or prove
balance, optimality or seasoned-player strength.

## Known Limitations and Next Upgrades

Reservation currently handles unblocked attacks, a single best fixed-cost cast,
and heuristic utility versus damage. It does not forecast postcombat land plays,
multiple casts, combat triggers, opposing responses or variable/costed/conditional
mana and untap engines. The existing damage-at-least-life shortcut is preserved
as pressure, not an engine-proven lethal line.

Qualified subjects read current stored characteristics, not a complete layer-5
color/type/dependency model. Conditional static clauses are excluded rather than
implemented; arbitrary global clauses, granted abilities and ability suppression
still need explicit semantics. The earlier intermittent browser sideboard
timeout and timeout-diagnostic interpreter crash remain unexplained despite
successful later gates. Manual review should assess real tactical decisions and
long-session UX; this milestone does not close the full release plan.
