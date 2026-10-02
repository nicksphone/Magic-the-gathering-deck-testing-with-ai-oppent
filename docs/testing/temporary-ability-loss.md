# Temporary ability loss and base stats

## Implemented increment

Recognized unconditional end-of-turn instructions now create object-bound
all-ability-loss effects and optional base-power/toughness setters. The two
parts share their actual resolution timestamp. Base setters compete with
supported static setters in layer 7b; counters and recognized modifiers remain
in layer 7c. Printed card metadata is not rewritten. Effective combat stats,
public views and layer traces read the same effects.

Targeted loss disables the previously supported printed mana, activation,
trigger, static and replacement readers. Later keyword grants can restore a
keyword without restoring printed Oracle abilities. Cleanup expires these
records alongside damage removal, and zone changes discard them. Snapshot JSON
preserves timestamps, duration, source and incarnation; older snapshots default
to an empty base-stat effect list.

The recognized player-wide instruction captures current creatures only, not
future entrants. Merfolk Trickster's bounded entry instruction preserves its
tap-then-loss sequence and declared target through human selection and snapshot
resume. It is compiled only after a legal target is chosen, not reduced to the
first sentence or an arbitrary automatic target.

Split second is checked across spell stack objects, including saved spell-copy
characteristics. It prevents casts and supported nonmana activations (generic,
cycling, crew, equipment, loyalty and ninjutsu); legal moves and direct checked
writes agree. Mana actions, triggered abilities and priority passing remain
available. An ability object does not acquire split second merely because its
source has that keyword.

The AI's bounded public-board target projection recognizes targeted temporary
loss/base-stat changes. It evaluates detached state without executing later
card draws or mutating authoritative state. This is not a full combat or
multi-turn strategic search.

## Canonical data and rules

`backend/tests/fixtures/temporary_ability_loss.json` retains canonical Scryfall
IDs, retrieval dates and API URLs for Humble, Ovinize, Merfolk Trickster and
Sudden Spoiling. Existing canonical Shark Typhoon/Smuggler's Copter fixtures
exercise cycling/crew restrictions. Fixture board setups are not tournament
decks or evidence of matchup balance. No card-name gameplay dispatch is added.

References: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules),
September 25, 2026 text, 702.61 (split second), 613.1f/613.4b/613.4c (layers),
613.7b (resolution timestamp), 611.2c (affected objects), 113.7a (stack
independence), 400.7 (new objects) and 514.2 (simultaneous cleanup).

## Validation

Both-seat fixtures exercise actual casts, counters and timestamp conflicts,
late keyword grants, zone incarnation, frozen recipients, human and automatic
entry targets, AI projection, spell-copy characteristics and atomic HTTP writes
across SQLite restart. The first focused run exposed the standalone split-second
line and ETB multi-sentence gaps; both were repaired rather than weakening the
expected behavior. Final focused coverage: 100 passing checks.

October 2, 2026: the final isolated full suite passes **2,761 tests** with 297
deprecation warnings (293.25 seconds). Frontend lint/unit/build and the full
final-engine Chromium harness pass. Twelve logical seat-balanced smoke games
each repeat twice, with no reported drift, timeouts or anomaly labels.
Failed/superseded and final checks, fixtures and closed source copies are retained
on RCHFiles under `diagnostics/temporary-ability-loss/20261002T050905Z/`.
Tests use isolated local databases and reused dependencies; neither clean
installation nor visual UI certification is claimed. Alpha UI redesign remains
deferred.

## Known Limitations and Next Upgrades

- Grammar remains bounded: conditional losses, arbitrary durations, gained
  non-keyword abilities, type/color/text changes and a general dependency graph
  require further work. The shared printed-suppression readers are not a full
  Magic ability interpreter.
- The tap-then-loss trigger continuation is recognized explicitly; arbitrary
  multi-sentence triggered instructions are not certified by this fixture.
- Unsupported special actions and unusual mana-ability classifications remain
  subject to existing corpus preflight limitations. This increment does not
  certify every interaction with split second.
- Broad AI strength, long-run corpus replay/restart evidence and operational
  release gates remain open. Small repeated matches establish repeatability,
  not optimal play or guaranteed win-rate bounds.
