# Continuous Source Reuse

## Implementation

Within existing immutable rules query scopes, continuous-effect evaluation
shares the timestamp-ordered battlefield list, its position map and source
printed-ability activity flags. Power/toughness setters, additive modifiers and
keyword grants/removals consume the same ordered source view.

Target-specific conditions, attachment applicability, layer timestamps and
supported continuation of combined ability-loss/base-stat instructions remain
evaluated by the existing handlers. No response branch or state-based action is
removed. New scopes after departures, controller changes and other mutations
compute fresh results. Returned list/dict ordering views are defensive copies;
the internal source tuple is for read-only engine use, not client mutation.

## Evidence

The updated predecessor profile identifies 94,510 battlefield-order sorts and
3,109,703 suppression calls in one retained decision. Profiling overhead makes
its 119.84-second decision unsuitable as an ordinary latency baseline.

Eight new tests cover both seats, suppression/source departure, controller and
timestamp changes, defensive ordering views and effective-stat/keyword/trace
parity with an unshared source scan. The first affected selection passes 228
checks. The final combined suite passes 3,545 checks across 85 files in an
isolated local source copy. Selections overlap; this is affected-suite evidence,
not a new full regression total. The batch is integrated into main.

The retained unprofiled candidate preserves the complete action, 17 legal moves
and original snapshot: 30.00 seconds versus an archived predecessor measurement
of 37.55 seconds. This is one comparison, not a statistical latency guarantee
or decision-quality improvement.

The profile, decision comparison, test logs and verified source copies are
archived on NFS under the October 5 strategic-draw diagnostics,
`continuous-source-reuse`. The initial profiler launcher collided with Python's
standard `profile` module; renaming that disposable launcher fixed the tool
error before the successful measurement. Application code was not involved.

## Known Limitations And Next Upgrades

Thirty seconds remains too slow for interactive play. Nested forecasting and
settlement still dominate the decision. Broader rules, professional AI and
release readiness remain unfinished. The last full backend/browser integration
gate is frozen runtime `91b5dff`, not this affected-suite increment.
