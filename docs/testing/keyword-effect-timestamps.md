# Resolution-created keyword effects

## Supported scope

Battlefield keyword grants and removals now retain their own creation timestamp,
duration, original object incarnation and available source identity. They do not
modify printed keywords or become physical counters. Supported layer-six
evaluation interleaves these records with counter-kind and static/attached
effect timestamps; explicit cannot-have restrictions still prevail.

Cleanup expires end-of-turn records, preserving indefinite effects and physical
counters. Zone changes clear records; retiming the same object does not.
Snapshots and SQLite restart preserve effects and pending spell sequences.
Old `granted_keywords` snapshots remain readable, but their missing historical
resolution timestamps are labeled `legacy_inferred`, not reconstructed facts.
Legacy end-of-turn counter markers remain compatible until cleanup.

The bounded Oracle grammar handles supported target/self keyword gain/loss
instructions through end of turn and retains following clauses. Shared team
instructions use one creation timestamp and affect only eligible current
objects. Standalone untap instructions no longer match the tap parser;
control-change/untap/haste sequences preserve all three operations. Existing
land-animation handlers retain their integrated untap instead of duplicating it.
Optional two-way tap/untap instructions remain explicit known gaps, not guessed
actions.

AI target ranking projects recognized keyword changes on a detached public-board
copy. Later draw clauses are not executed during scoring. Unknown sequences use
existing fallback ranking. This is bounded board evaluation, not response search,
hidden-information access or proof of expert play.

## Canonical fixtures and rules

`backend/tests/fixtures/keyword_effect_timestamps.json` retains Scryfall IDs,
API URLs and retrieval dates for Jump, Leap, Canopy Claws, Act of Treason and
Twiddle. Existing canonical Humility, Archetype and creature fixtures exercise
grant/removal ordering. Synthetic state/instruction tests are explicitly labeled;
none are invented decks or balance evidence.

Reference: Wizards' [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
613.7b (resolution timestamp), 613.7c (counter-kind retiming), 613.7e
(attachment timestamp) and 613.8 (dependencies). This increment does not implement
all dependencies or simultaneous timestamp ordering choices.

## Validation

Focused tests cover both seats, real casts and targets, competing grants/removals,
counter retiming, effect expiry, unchanged printed data, source provenance,
incarnation changes, snapshot/HTTP/SQLite continuation and AI projection safety.
The canonical control-change test also checks actual untap and haste, rather
than only which handler key was selected.

October 2, 2026: **2,698 backend tests passed** with 293 deprecation warnings,
plus **271 focused checks**, using isolated source-local SQLite databases. The
frontend lint/unit/build gates and full final-source Chromium harness passed.
Twelve logical seat-balanced smoke games each repeat twice without reported
determinism drift, timeouts or anomaly labels. This small template sample does
not establish balance or expert play; canonical fixtures validate this increment.
Dependencies were reused, not freshly installed. Browser checks use DOM clicks,
not pointer/visual certification. Failed/superseded and final evidence is retained
under RCHFiles `diagnostics/keyword-effect-timestamps/20261002T035328Z/`.

## Known Limitations and Next Upgrades

- Full non-keyword ability suppression, type/color changes, dependencies and
  simultaneous timestamp ordering remain unfinished.
- Conditional/arbitrary grants, non-battlefield effects, generalized duration
  management and overlapping control-change layers need separate acceptance.
- Optional tap/untap choice support remains absent and is surfaced by preflight.
- Legacy snapshot timing cannot be inferred exactly from absent historical data.
- Broad AI strength, statistical matchup validation and operational release
  gates remain open. Alpha UI redesign is deliberately deferred.
