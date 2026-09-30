# Repeatable mana-resource valuation

Date: 2026-09-30 UTC.

Follow-ups: [postcombat reservation](ai-postcombat-mana.md) and
[state-aware variable mana](variable-mana.md) extend this initial fixed-output
valuation. The original verification and limitations below are historical, not
a claim that these later bounded increments remain unimplemented.

## Implemented

Payment and valuation share one parser for supported printed nonland mana
outputs. `nonland_mana_outputs` still checks tapping, activated costs and
summoning sickness/haste before authorizing payment. The new
`repeatable_nonland_mana_outputs` instead reports a bounded printed capacity;
it never grants permission to pay or activate an ability.

AI uses this capacity for creature and artifact board/sacrifice value and
creature cast/threat value. The public controller's land count adjusts the
resource bonus: two points per mana below four lands, 0.75 at four or more.
These are explicit heuristic weights, not measured optimal policy. The
estimate does not read opponent hand contents or treat temporary readiness
as permanent loss of an engine. Selected cast surfaces reach the helper.
Flexible-color outputs are alternatives; use the maximum amount, not the sum.

The unconditional bonus excludes additional mana/life/discard/sacrifice or
other unsupported costs, printed spending/activation restrictions and sources
that do not normally untap. Their existing payment implementation is not
rewritten or certified by this valuation exclusion.

## Fixtures and validation

`backend/tests/fixtures/mana_resources.json` contains thirteen actual local
Scryfall canonical rows with source and Oracle-ID provenance. No printed card
or built-in list was invented or changed. Cases include Llanowar Elves,
Avacyn's Pilgrim, Boreal Druid, Palladium Myr, Birds of Paradise, Gilded Lotus,
Sol Ring, Springleaf Drum, Skirk Prospector, Renowned Weaponsmith and Basalt
Monolith; Grizzly Bears and Swamp provide nonresource/public-land baselines.

Tests cover fixed colored/colorless outputs, flexible alternatives, amounts,
strict payment readiness, snapshot purity, artifact board integration,
resource scarcity across ten archetype labels, and unchanged resource values
after adding a hidden opposing hand card. Final focused checks: 81 passed.
Full final-code backend suite in an isolated source/database copy: 1,835
passed, 292 existing deprecation warnings, 222.03 seconds. Frontend lint,
build and unit boundary tests pass. Full final-code Chromium harness passes
action/choice, simulator, recovery, sideboarding and natural AI/human BO3s.

Eight seeded logical games repeat across sixteen executions with identical
complete identity-sensitive results, no timeout and no logged cost/target
rejection. Both seats cover Control/Tempo, Tokens/Ramp, Midrange/Drain and
Tribal/Burn. Three traces differ from the prior recurring-payoff milestone;
changed traces are not evidence of improved optimality. See [compact results](ai-mana-resources.json).
Both LAN endpoints return HTTP 200. The earlier milestone's intermittent
browser sideboard timeout and separate diagnostic interpreter crash remain
unverified; successful subsequent gates do not establish their causes.

## Known Limitations and Next Upgrades

This is not a full resource planner. Land count does not capture hand-cost or
color bottlenecks, permanent-type restrictions, available untap effects,
mana-development horizon, attack/block opportunity cost or adverse board
changes. Conditional/variable mana, paid untap and single-use resources need
separate utility/cost models. General ability suppression, granted abilities
and multi-ability sources are not certified by printed-capacity recognition.
No activation/payment rules were loosened, and no expert-play or balance
claim follows from a small deterministic matchup sample.
