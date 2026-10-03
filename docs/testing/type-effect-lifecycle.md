# Resolution-created type effects and animation lifecycles

## Implemented Scope

Crew and supported indefinite 0/0 land animation now record object-bound,
timestamped type additions with a separate copiable type baseline. Existing
readers retain a materialized `card.types` view; this is not a complete pure
layer-four query system. Cleanup removes only expiring additions, preserving
independent effects. Departures restore the baseline while last-known battlefield
information retains the actual creature types, stats and keywords for triggers.

Land animation no longer overwrites printed stats or intrinsic keyword arrays.
Its base-stat setter and keyword grants reuse the existing resolution effect
records with the same timestamp. Their indefinite duration survives cleanup and
their target incarnation prevents re-entry leakage. Ability-loss/base-stat
interactions now follow the tested timestamp ordering in both directions.

Supported token copies exclude crew/animation type additions and noncopiable
animation stat/keyword changes. Noncreature Vehicle copies retain their printed
stats so they can later be crewed. Same-object face changes rebase the underlying
types without erasing later effects; departure clears additions before restoring
the front face. The supported linked-exile copy path also rebases type additions.

Legacy crew snapshots contain enough explicit flags to restore contributed types.
Registering another effect adopts those flags without making temporary Creature
types copiable; unknown legacy timing is explicitly marked `legacy_inferred`.
Old unrecorded land animations lack that provenance and cannot be reconstructed
reliably; start a new match to exercise the new animation lifecycle. No guessed
card-specific migration is applied.

Grounding: nine fresh Scryfall card responses, plus the official
[Comprehensive Rules effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
sections 205.1b, 400.7, 611.2a, 702.122a and 707.2. Canonical cards test mechanic
boundaries, not certification of their entire Oracle text. Effect-composition
primitives are explicitly labeled and never added to production decks as cards.

## Acceptance Checklist

- [x] Reproduce crew, animation, copy and departure failures before repair.
- [x] Verify both seats, hand/exile/graveyard destinations, printed restoration,
  last-known characteristics and single/simultaneous creature-death triggers.
- [x] Verify cleanup composition, face rebase, front restoration, legacy crew
  snapshots and both timestamp orders against Humility.
- [x] Verify copy characteristics and subsequent Vehicle crew.
- [x] Announce and resolve crew/loyalty through HTTP, restore SQLite snapshots and
  check effective characteristics and subsequent departure for both human seats.
- [x] Complete fresh-cache full backend suite, frontend gates, complete Chromium
  and explicitly selected seat-balanced repeated matchup matrix.
- [x] Refresh Graphify and archive verified evidence on RCHFiles.

The initial 20-case baseline failed all 20 cases. The first repaired broader
selection passed 157 cases and exposed three old assertions of mutated intrinsic
data; those now assert effective values and unchanged printed fields instead.
An expanded test initially used the wrong layer-trace response key; corrected
acceptance uses `applied_layers` and verifies read purity. The 488-case repaired
selection passes. Four further legacy re-crew/composition cases failed before
repair; the final 48-case lifecycle/HTTP/trigger selection and nine existing
Vehicle tests pass together (57 checks). The preliminary full suite passed 5,278
checks before those four additions; final-source acceptance is recorded below.

Final-source checks: 5,282 backend tests pass (537 deprecation warnings,
988.77 seconds), with lint, runtime contracts and production build passing.
The complete Chromium harness passes both-seat action/payment fixtures, restore,
sideboarding and natural human-vs-human, human-vs-AI and AI-vs-AI best-of-three
flows. A preliminary Bestow fixture read state before its write completed; it
now waits for authoritative stack/revision acknowledgments and retains the exact
four-mana payment assertion. Both repaired complete browser runs pass.

Ramp/Midrange/Tokens/Dimir Control run all six pairs in both seat orders, one seed
per pairing, each sample repeated twice: twelve samples/24 executions, 447.383
seconds, no reported anomaly, timeout or determinism drift. The earlier matrix
also passed. These small replay samples establish repeatability, not AI strength
or balanced matchup percentages. Final test checkouts match backend source bytes.

Canonical responses, rules grounding, failing and passing logs, isolated source,
browser artifacts and preserved user work are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/type-effect-lifecycle/20261003T232938Z/`.
Archive contents are byte-compared before disposable local artifacts are removed;
publication and cleanup records accompany the evidence.

## Known Limitations and Next Upgrades

Conditional type changes/devotion, subtype replacement, type removal, arbitrary
static/global animations, dependency ordering and full copy-layer fidelity remain
open. This increment supports resolution-created type additions only; its
materialized compatibility view must not be mistaken for arbitrary layer support.
Entry/response-aware AI planning and matchup balance remain unverified. The alpha
UI redesign is still deferred; browser fixture gates are not ergonomic review.
