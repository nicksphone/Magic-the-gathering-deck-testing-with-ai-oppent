# Restricted mana and attachment workflows

Date: 2026-09-30 UTC. Scope: supported type-restricted spending clauses and
ordinary fixed-cost equip, not unrestricted Magic certification.

## Rules grounding

Verified against the [official September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt):
106.4 describes step/phase pool expiry; 106.6 separates spending restrictions
from mana type. 702.6a makes ordinary equip a sorcery-timing activated ability
targeting your creature; 301.5b/d distinguishes activation/resolution ownership
from subsequent attachment control. 613 describes continuous characteristic
updates. This implementation covers bounded clauses, not every exception in
those rules (notably reconfigure and special equip variants).

## Reproduced and implemented

Parent code allows ready Renowned Weaponsmith plus Forest to pay for Naturalize,
despite the source's artifact-only spending restriction. Supported restrictions
now travel with produced units in `restricted_mana_pool`, while `mana_pool`
still reports total colors and snow provenance remains independent. Rule data
is copied at production, survives source departure and snapshots, is consumed
only for an eligible purpose, and expires with the rest of the pool.

The shared parser supports explicit spell-type restrictions and corresponding
artifact/type ability permission. Unknown restriction clauses are not treated
as unrestricted. Ready-source planning and floated-pool accounting use the
same purpose/type context. Generic, mandatory colorless, hybrid and snow paths
share that eligibility; partial spending preserves remaining restrictions and
prefers eligible restricted units over unrestricted units of the same type.

Casting contexts and activation contexts are separate from spell cost-modifier
types, avoiding new spell-tax/reduction application to activated abilities.
Generic activations, cycling and equip pass their actual source's types. Other
payments do not gain casting permission. AI legal moves inherit these costs;
unblocked fixed-cost postcombat reservation can retain a supported restricted
tap-only source for a genuinely payable hand spell. Unconditional future board
value still excludes restricted sources; it does not inspect opposing hands.

Tests exposed an equip integration gap: checked actions attempted to compare
the chosen target with a nonexistent top-level move field, rather than its
target list. Admission now uses the declared choices. Ordinary equip pays its
cost and enters the stack, preserves priority and permits response/countering.
Resolution rechecks targets/control, source/target incarnations and attachment
legality; a failed/countered ability does not refund the cost.

Supported static equipped/enchanted/fortified subject clauses now contribute
fixed P/T deltas and keyword grants through the same continuous evaluator used
by targeting, combat, AI and views. Changes follow the attachment, not source
ownership; removal/detachment removes the bonus. Layer traces report these
contributions. Printed characteristics stay unchanged. Public views expose the
attachment ID and restricted-unit purposes; the UI labels restricted pool mana
and runtime contracts reject invalid quantities/types or overlapping snow tags.

## Validation

Twenty-two canonical Scryfall fixture rows supply actual card text and IDs.
No gameplay card definitions or built-in decks were invented or changed.
Forty-six new tests cover both seats, ready/floated restrictions, source departure,
partial/excess payment, casting versus activation, cycling/equip, snow, expiry,
snapshot compatibility, ten-style AI legality/reservation, counter/removal
responses, incarnation/control changes and real attachment bonuses/keywords.

Final focused checks including existing AI/payment regressions: 196 passed.
The final isolated full backend run passes 1,943 tests with 292 deprecation
warnings in 243.40 seconds. Frontend lint/build/unit checks pass, including
restricted-pool quantity/purpose/snow boundary tests. Full final-code Chromium
passes new seat-two mana-label, rejected instant availability, equip stack and
effective attached-stat assertions, plus action/choice, simulator, recovery,
sideboard and natural AI/human BO3 flows. All API tests use disposable source,
database and cache copies, never the live user database.

Eight seeded, seat-paired archetype games repeat their complete reported game
objects and logs across sixteen executions, with no timeout or rejected cast/
target. They are unchanged from the parent: this checks existing behavior,
not coverage of the new restricted sources or equipment. One optional Spell
Pierce payment fails normally, rather than a cast being rejected. The
[compact matrix evidence](restricted-mana-equipment.json) records seeds, hashes,
results and production-source fingerprints. Equality does not compare every
internal final-state field and does not establish balance or expert play.

All 46 new cases fail on the isolated parent. Some failures concern new
interfaces/metadata, so that number alone is not semantic proof; the parent
also directly reproduces the illegal ready-source Naturalize payment on both
seats, before the new fields are involved.

Initial test import/view-key mistakes were corrected. An early browser fixture
had an extra ready Manakin, legitimately making Naturalize payable; tapping that
fixture source made the intended restriction bottleneck real. The larger suite
also exposed minimal planner fixtures without optional Oracle/snow metadata;
read-only defaults preserve their prior unrestricted behavior. Superseded full
runs were not used as passing gates; fresh final code was tested independently.

## Known Limitations and Next Upgrades

Spending clauses are interpreted per source surface, not per individually
selected mana ability. Multiple/granted/conditional/restricted-color abilities,
Powerstone exclusions, chosen subtype predicates, mana spending triggers and
uncounterability bonuses still need richer records. Old snapshots without
production provenance cannot reconstruct restrictions on already floated mana;
start a fresh game when testing this change.

Ordinary equip is not all attachment mechanics: equip variants/additional costs,
reconfigure, fortify activation, arbitrary attached restrictions, granted
activated abilities, source ability suppression and full layer dependencies
remain open. Attached fixed bonuses do not certify characteristic-defined,
conditional or type-changing attachment effects. AI still uses bounded heuristic
postcombat utility, not multi-cast/adversarial expert planning. Small seeded
replays are repeatability evidence, not win-rate/balance/strength certification.
Historical diagnostic interpreter crashes and unrelated network/browser timing
issues are not declared fixed by these gates. Manual review should assess real
tactical play, attachment presentation and long-session ergonomics.
