# Condition-aware static combat constraints

## Implemented scope

Attack/block restrictions and blocking capacity now share a pure query over
the creature and current battlefield sources. Printed source ability loss
disables the source's clauses; recipient ability loss does not erase an
independent Aura or enchantment's restriction. Multiple additional-blocker
effects add together. Numeric blocker requirements use the shared number parser.

Supported recipients are self, attached creature/permanent, and recognized
global type/color/subtype subjects with controller scopes. Supported conditions
include controller land counts, defending-player basic land subtypes, global
basic land subtype counts, named +/- power/toughness counter thresholds, and
the existing bounded attachment predicates. Conditions are evaluated against
current state, not cached mutable game state. Only parsed immutable text is cached.
Self-reference also retains the existing `CARDNAME` diagnostic-template spelling;
it is not treated as another permanent's name or a global subject.

Pacifism and Bonds of Faith cover attachment restrictions and the Human/otherwise
branch. Sea Serpent and Harbor Serpent cover land conditions; Slumbering Dragon
covers counter thresholds. Steel Leaf Champion uses effective blocker power;
Hinterland Drake's artifact qualifier is pair-specific, not a blanket block ban.
Bedlam covers a global prohibition, and multiple Brave the Sands stack their
additional-blocking permission. These are canonical Scryfall clauses, not
invented deck additions. Other clauses on these cards are not certified by these
tests (including Sea Serpent's sacrifice condition).

The same queries feed checked combat actions and existing AI combat legality
helpers. Engine layer traces expose active source/clause provenance and unresolved
combat clauses. The [coverage increment](combat-coverage-diagnostics.md) now
exposes known static gaps through preflight/completeness and a read-only live
HTTP inspector; a dedicated in-match visual inspector remains deferred.

## Validation

`tests/test_conditional_combat.py` exercises both seats, mutable thresholds,
source/recipient suppression, snapshots, read-only diagnostics, effective power,
and real Aura casts followed by rejected checked attacks. Synthetic grammar and
characteristic mutations are explicitly labeled test boundaries, never cards
imported into competitive decks. Existing combat provenance, attachment and
land-threshold tests are included in focused regression checks.
Both-seat HTTP counter-gate rejections compare complete memory/database snapshots,
then restore from SQLite and verify the legal attack after the threshold changes.

Tests run in isolated source copies with local SQLite, not the live database.
Seeded seat-balanced replay checks establish bounded repeatability, not expert
AI play, universal semantics or a required matchup win rate.

Verified 2026-10-02: 2,828 full backend tests passed (305 deprecation warnings);
83 focused combat/diagnostic checks passed. Frontend lint, unit checks and build
passed. Four built-in decks produced 12 logical seat-balanced single games,
each repeated twice, with zero determinism failures, drift labels or reported
anomalies. Failed/superseded runs are preserved separately in the evidence archive.
The final Chromium harness passed recovery, sideboarding and natural AI,
human-vs-AI and human-vs-human BO3 flows. A startup restoration race found during
validation was fixed by gating Start until ready; this is functional maintenance,
not an alpha UI redesign or visual usability certification.

## Known Limitations and Next Upgrades

- Arbitrary compound conditions, paid attack/block taxes, and general granted
  nonkeyword abilities remain unsupported. Unknown predicates are not applied
  as unconditional restrictions; diagnostics must be consulted.
- Continuous type/color changes, dependency ordering, multiplayer defending
  players, and complete restrictions-versus-requirements optimization need
  separate acceptance fixtures.
- General human diagnostic warning presentation and broader AI planning remain
  open; the alpha UI redesign is deferred in favor of backend work.
