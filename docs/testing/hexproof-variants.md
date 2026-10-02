# Source-specific hexproof and object-bound grants

## Engine scope

Supported printed color/type variants and keyword-counter grants now constrain
opposing spell/ability targets using source characteristics. Nonmatching and
friendly sources remain legal. Hexproof is not protection: it does not prevent
damage, block creatures or stop non-targeting effects. It applies to battlefield
permanents, not cards in the graveyard. Existing player hexproof/shroud behavior
is unchanged; arbitrary player variants are not implemented here.

Scryfall's metadata for the tested cards contains both `Hexproof from` and the
`Hexproof` family. Those labels are not two printed abilities and must not
create unrestricted immunity. The shared effective-ability adapter reconstructs
supported qualities from standalone Oracle keyword text, including comma lists.
Ability-family queries still recognize a variant as a hexproof ability. Losing
hexproof or an explicit can't-have override removes its variants, while supported
timestamp rules can restore a newer variant counter after ordinary removal.

Casting, activated/loyalty abilities, modal/divided targets, trigger target
choices and resolution checks pass the actual source to the same legality
operation. Loyalty hint proxies retain source identity without pretending an
ability is a permanent spell. Target hints therefore exclude matching protected
targets for both humans and AI. Supported departed-source trigger choices use
stored last-known colors/types rather than a returning card's new incarnation.
This is not a complete type/color/layer or arbitrary-source LKI implementation.

Resolved battlefield keyword grants now use durable timestamped
`keyword_effects` records, leaving printed metadata and physical counters
unchanged. They preserve independent instances, survive snapshots, expire by
duration and disappear on zone reset. Legacy `granted_keywords` snapshots use
an explicitly inferred timestamp fallback. Supported grant/removal interleaving
is covered by the subsequent [keyword-effect milestone](keyword-effect-timestamps.md);
full dependency and non-keyword suppression fidelity remains unfinished.

## Rules, fixtures and checks

Reference: Wizards' [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
702.11b-f and 122.1b. The fetched rules are retained with test evidence on
RCHFiles. Nine canonical Scryfall fixtures retain IDs, URLs and retrieval dates:
Knight of Malice, Knight of Grace, Eradicator Valkyrie, Swords to Plowshares,
Path to Exile, Doom Blade, Royal Assassin, Ugin and Archetype of Endurance.
They are not invented decks or a certification of every printed clause.

The focused suite covers both seats and friendly/nonmatching sources, real
spell/activation rejection, planeswalker hint filtering, actual resolution,
response-time counter acquisition, snapshot/SQLite restore, cannot-have
overrides, unchanged printed metadata and legacy/zone-reset grant behavior.
The LKI type-change test is explicitly a synthetic object-incarnation fixture,
not a fabricated card or claimed tournament play.

## Acceptance evidence

October 2, 2026: **2,668 backend tests passed** with 291 deprecation warnings in
an isolated source checkout using source-local SQLite, never the live database.
The final focused keyword/AI/counter/proliferation suite passed **239 checks**
with seven warnings. Frontend lint, unit boundaries and TypeScript/Vite build
passed. The final-source sequential Chromium harness passed, including natural
AI and both human BO3 flows. DOM-driven checks are not pointer/visual review.

Four-deck seat-balanced smoke: **12 logical games**, each repeated twice, zero
reported determinism failures, timeouts or drift labels. The same narrow
Aggro/Tempo/Tokens template sample used by the preceding milestone is not a
strength, balance or complete variant-corpus study. Canonical focused fixtures
establish the new semantics. Installed dependencies were reused, not freshly
installed. Failed/superseded checks and final evidence are retained on RCHFiles
under `diagnostics/hexproof-variants/20261002T030740Z/`, alongside official rules,
canonical fixtures and verified closed scratch archives.

## Known Limitations and Next Upgrades

- Arbitrary/conditional qualities, each-characteristic shorthand, player variants,
  as-though targeting overrides and full type/color dependencies remain open.
- The broad keyword-variant preflight flag deliberately remains: recognizing a
  supported quality is not evidence of complete card semantics. Trample over
  planeswalkers and arbitrary granted-ability families need separate fixtures.
- Resolved grants outside the battlefield and general timestamp/dependency
  ordering remain open. Historical metadata-only grants in old snapshots cannot
  be distinguished retrospectively from printed keywords.
- Broader simultaneous replacements, measured strategic AI, operational gates
  and the deferred alpha redesign remain on the finish plan.
