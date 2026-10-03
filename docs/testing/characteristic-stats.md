# Resource-Defined Creature Characteristics

## Implemented Scope

Shared continuous-effect evaluation recognizes complete self-stat statements
counting cards in hands, cards or supported card types in graveyards, distinct
normal card types in graveyards, and supported permanents controlled. Definitions
apply in every zone. Battlefield-only self modifiers remain battlefield-only;
base-setting effects do not leak into hand, library, graveyard or exile views.

Canonical fixtures exercise Tarmogoyf, Nighthawk Scavenger, Boneyard Wurm,
Terravore, Mortivore, Lord of Extinction, Consuming Aberration, Lhurgoyf,
Rubblehulk, Multani, Yavimaya's Avatar, Death's Shadow, Overbeing of Myth and
Multani, Maro-Sorcerer. This validates the exercised stat clauses, not every
ability of these cards. Supporting cards are canonical data, not invented
competitive decks. All 19 records match saved Scryfall responses.

Printed expressions (`*`, `1+*`, numeric strings) are distinct from numeric base
and effective stats. Snapshots, public views, face selection, prototype overlays
and supported permanent copies carry those expressions. When a recognized
defining ability is removed, an undefined star contributes zero to its supported
printed calculation: Tarmogoyf becomes 0/1, not 0/0. Counters and later modifiers
still apply. Explicit type lines preserve Kindred and Battle, while excluding
supertypes/subtypes from distinct-card-type counts. Tokens do not count as cards
in graveyards.

Damage marks now apply to Creature permanents with nonnumeric printed toughness;
lethal checks use effective toughness. Unknown toughness is not invented as zero.
Copies without known numeric stats use offline generic art rather than crashing
or searching for fabricated 0/0 token stats. Battlefield noncreatures have no
effective P/T; their printed metadata is retained separately.

## AI Boundary

Cast, closure and library-choice valuation use a shared static entry projection
for actual game/card instances. It removes the entrant from its previous zone,
uses the casting player's battlefield/resources and evaluates ordinary layers
without mutating the authoritative state. Per-decision memoization retains proxy
identity safely. Incomplete legacy test doubles retain printed-stat scoring.
Triggered damage target ranking uses effective remaining toughness and respects
indestructible, rather than treating `None` as a killable zero-toughness creature.

This is not a forecast of costs, entry choices/counters, triggered payoffs,
replacement choices, unknown draws or opposing responses. It does not certify
expert-level play or justify automatically discarding every apparent 0/0 entry.

## Validation

- Initial canonical probes: 30 failures, 2 passes; saved before implementation.
- Focused rules/copy/face/damage selection: 329 passed before AI additions.
- Expanded AI regression selection: 625 passed after fixing incomplete test-double
  compatibility; the failed 13-case run is retained.
- Final characteristic selection: 249 passed, including names-only cached HTTP
  starts, SQLite restore, all-zone views, suppression, copies and damage.
- Production decisions: both seats, three difficulties and eight archetypes cast
  a payable canonical variable-stat threat through checked actions.
- Frontend lint, runtime contracts and TypeScript/production build passed.
- Complete Chromium harness passed, including six new both-seat stat/cast/reload
  cases, recovery, sideboarding, AI BO3 and both human controller modes.
- Dimir Control/Tempo/Tokens/Ramp matrix: twelve BO1 samples in both seat orders,
  each repeated twice; zero reported anomaly/timeout/drift, 497.359 seconds.
- Default template matrix: twelve seat-balanced BO1 samples, each repeated
  twice; zero reported anomaly/timeout/drift, 511.276 seconds. Actual selection
  was Aetherdrift/Foundations Aggro, Duskmourn Tempo and Bloomburrow Tokens
  templates, not the initially intended Burn/Midrange coverage. Explicit
  Mono Red Aggro/Burn/Midrange testing passed separately: six seat-balanced
  BO1 samples, repeated twice; zero reported anomaly/timeout/drift, 96.002 seconds.
- Full backend run: 5,036 passed, one split-identity failure. The factory now
  retains both split halves outside the stack without treating double-faced
  cards the same way. The 287-check stat/split/modal/inference selection passes.
  The repaired-source full suite passed: 5,037 tests, 450 deprecation warnings,
  801.25 seconds. Complete Chromium also passed again on the repaired source.

All three matrices together contain 30 samples and 60 executions, not 60
independent balance observations. They are repeatability smoke tests, not
decision-optimality or win-rate evidence. Dependencies were reused; this batch
does not establish fresh-install or network-release readiness.

Failed/final logs, isolated source/database copies, canonical responses,
browser evidence and the complete source snapshot are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/characteristic-stats/20261003T193237Z/`.
Archives were content-compared and SHA-256 checked before disposable local
checkouts were removed. The pre-existing untracked user plan is preserved
separately and is not part of the application commit.

The first Chromium run exposed an existing test race: controls disappeared while
the mutation was pending, before payment completed. The test now waits for the
authoritative declaration before asserting payment; no payment rule was relaxed.
The pre-compatibility full-suite run was deliberately interrupted after 13 known
failures and 2,886 passes. A fresh final-source copy is used for the final gate.

## References and Remaining Gaps

Rules and rulings were checked against the [September 25, 2026 Comprehensive
Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
(107.2, 208.2a, 208.3, 604.2-3 and 613.4), and canonical
[Scryfall card data and rulings](https://scryfall.com/docs/api/cards).

Arbitrary conditional definitions, unusual resource predicates, all static layers,
full zone-change resets, cost/entry-aware tactical prediction and whole-card
certification remain open. Unsupported count expressions remain unknown instead
of matching only a misleading substring. Missing-metadata fallback heuristics
still exist. Older snapshots lacking printed-expression fields retain `None`;
start fresh games for canonical metadata rather than assuming a migration.

UI redesign, competitive human ergonomics, long-session/network release gates
and broad statistical AI strength remain separate unfinished work.
