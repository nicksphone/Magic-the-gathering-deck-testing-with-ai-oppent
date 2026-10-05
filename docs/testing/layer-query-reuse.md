# Read-Only Layer Query Reuse

## Implementation

Printed-ability suppression and static-subject matching reuse scalar results
only inside an existing read-only rules query scope. Unscoped calls retain
ordinary evaluation. No continuous instruction, response branch, card metadata
or deck contents are changed.

Suppression keys include target identity, land-type inclusion and the supplied
loss qualifiers/controllers and source identity when the instruction uses it.
Mutable argument lists are keyed
by their current values, not list identity. One-shot iterators use uncached
evaluation, preserving their original lazy consumption. Subject keys retain
the exact target and qualifier. Query scopes end before mutations; subsequent
departures, controllers, zones and state-based waves are evaluated afresh.

## Evidence

- 3,436 final affected checks pass across 82 files, covering ability loss,
  layers, combat, replacements, state-based actions and AI/information paths.
- 135 compound focused checks pass. Earlier 1,705 suppression-only checks and
  smaller selections overlap; do not add them into a full regression total.
- A retained complete Tribal decision preserves its action, all 17 legal moves
  and original state: current baseline 66.62 seconds, combined caches 55.64
  seconds. This is one comparison, not a statistical latency guarantee.
- Cache tests cover controller/qualifier argument changes, source departure,
  land-type flags, nonbattlefield guards and iterator behavior. Canonical fixture
  Oracle data is unchanged; explicit query-argument tests are not new cards.
- A subsequent unused-source-identity compatibility adjustment passes all 17
  dedicated query tests. It preserves minimal global-loss records rather than
  introducing a new ID-field requirement; the broad count above predates it.

## Known Limitations And Next Upgrades

About 56 seconds remains too slow for interactive use. Nested stack forecasting
and remaining repeated rule reads need further retained-position work. These
changes preserve existing supported semantics; they do not add arbitrary-card
layer fidelity or certify professional AI. The last full backend/browser gate
still applies to frozen integration runtime `91b5dff`, not this later increment.
