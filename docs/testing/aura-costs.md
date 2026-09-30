# Target-aware Aura costs and enchant constraints

Date: 2026-09-30 UTC. Parent: `1e31ea94d4c64fa735e9f56f2e055749f654f55b`.

## Implemented

Supported global Aura-spell generic reductions and reductions targeting an
enchanted creature or the source creature use current source control and the
declared target. Reductions stack with supported taxes, preserve colored mana
requirements and do not apply to artifacts, non-Aura spells or activations.
Shared cost context reaches admission and actual payment. Paid costs remain
paid if the reduction source leaves or a counterspell stops the Aura.

A shared casting helper filters payable targets and maps each to compatible
cost-option IDs. Normal hand, permitted exile, escape and selected-face paths
use the helper instead of checking affordability before considering targets.
Human controls require a selected payable target/option combination. Ordinary
unaffordable non-Aura spells retain cost-before-target scanning; no target-aware
board scan is necessary for them.

Casting hints for an Aura use only its enchant instruction, not its later
triggered/activated/static abilities. Target admission and attachment checks
share supported types, artifact-creature intersection, type unions, basic/
nonbasic/nonland/noncreature qualifiers and control restrictions. Protection,
hexproof and shroud remain shared checks. Unknown enchant restrictions are not
silently interpreted as permission to enchant any permanent: they produce a
preflight warning and no broadened target list.

Shared AI projections use real accepted costs and immediate attachment effects
to select beneficial or harmful attachments from public state. They preserve
exile/graveyard permissions and resolve immediate cast triggers above the Aura
before valuing it. Unfinished paid spells are not scored as completed buffs.
This is bounded tactical planning, not opponent-response search or expert-play
certification. Strong Back's implemented Aura cost clause no longer warns;
unknown clauses on other cards remain diagnostic.

The official [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
were freshly fetched and compared with these boundaries: 303.4a/c define Aura
target/attachment constraints, and 601.2c/f place declared targets before total
cost determination and lock the resulting total. Download SHA-256:
`8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`.
The web reader failed on the text URL; the direct HTTPS fetch succeeded.

## Evidence

Thirty-seven canonical Scryfall fixture rows were extracted from read-only local
knowledge data. No card definitions or built-in decks were invented/rebalanced.
Forty-two new tests cover both seats, controller ownership, taxes, colored and
restricted mana, rejected-state purity, source departure, countering, shroud,
snapshots, actual escape and impulse-draw permission, enchant scope, unknown
restrictions, source-flag preservation, heroic and attachment decisions across
ten archetype labels.

The isolated parent directly reproduces three failures: discounted Octopus
Umbra is absent from legal moves, All That Glitters exposes Sol Ring instead
of the opponent's creature, and Ossification exposes a creature instead of its
basic land. These are casting-constraint reproductions, not tests certifying
all later abilities of those cards.

The real seat-two browser scenario requires a payable Aura target, filters out
the unpayable Elf, spends two blue mana on discounted Octopus Umbra, resolves
the stack and shows Dreadmaw power 12 while the Elf stays 1. A new test initially
assumed generic costs would not spend already floated blue mana; the fixture was
corrected to ready Islands rather than changing legitimate colored-for-generic
payment. Source-zone flags were also fixed and retested.

All API/backend/browser tests use isolated source/database/cache copies, not
the user's live database. Dependencies are reused; this is not a clean install
or fresh advisory scan. The final-source full backend suite passes 2,062 tests
with 292 existing deprecation warnings in 254.56 seconds. The broader focused
set passes 178 tests with one deprecation warning. Frontend lint, TypeScript/
Vite build and runtime/unit gates pass. The final complete Chromium harness
passes the new Aura scenario, existing actions/choices, simulator preflight/
recovery, saved-match refresh/process restart, creation recovery, sideboarding
and natural AI/human BO3 flows.

[Eight seeded seat-paired games](aura-costs.json) repeat identical complete
reported game objects/logs across sixteen final-source executions, unchanged
from the parent without timeout or logged cast/target rejection. Production
file hashes are checked against the isolated execution source. Optional Spell
Pierce payment failure is a normal payment decision, not rejected casting.
These unchanged smoke results do not exercise the new Aura fixtures; targeted
canonical and browser tests verify their supported mechanics. Timing is not a
controlled performance comparison, and equality is not all-internal-state
equivalence or professional-play certification.

## Known Limitations and Next Upgrades

Enchant subtypes/statuses/numeric predicates and more complex comparisons remain
unsupported. Chained to the Rocks' Mountain constraint is explicitly flagged,
not approximated as any land. Player Auras and unrestricted enchant grammar are
not complete. Selected-face routing shares the helper, but these real fixtures
do not separately certify an Aura modal-face family.

Variable Aura X optimization, alternative-cost/resource opportunity planning,
stack-response exposure, granted activated abilities, arbitrary prevention and
full ability/type/dependency layers remain open. Multiple-cost admission does
not certify kicker's extra effects. Working casting or characteristic clauses
do not establish full ETB, return-from-exile or umbra-armor fidelity for every
fixture card. Existing ward timing/payment approximation also needs separate
rules-fidelity work. AI projections are not trained professional-play evidence,
and a small deterministic smoke matrix is not a balance measurement.
