# Lethal-State Query Order

## Implementation

The shared state-based creature check now asks whether damage is lethal before
evaluating indestructible. Undamaged creatures and creatures with only nonlethal
damage do not need this expensive continuous-keyword query.

Effective toughness is still evaluated first. Zero/negative toughness remains
lethal regardless of indestructible; missing toughness is not classified as
lethal. Positive-toughness creatures with lethal marked damage or a deathtouch
mark still query current indestructible, including granted/suppressed abilities.
No rules, card metadata, forecast branches or caches are added or removed.

## Validation

The eighty dedicated cases cover both seats, zero/negative/positive/missing
toughness, marked damage, deathtouch and indestructible. They verify both the
result and whether the layer query is required. The first focused run passes
89 checks including existing combat and AI query-boundary tests.

The final affected suite passes 2,422 checks across 58 files in an isolated local
source copy, including the existing death/replacement, suppression, shield,
combat and AI-search suites. These overlap earlier checks, not a new full-suite
total. This change is integrated into main.
One retained decision preserves the full action, 17 legal moves and original
state: 37.55 seconds versus the archived predecessor's 51.48 seconds. This is
not a fresh concurrent baseline, statistical guarantee or strategic improvement.

Logs, retained-decision parity and the verified source archive are stored on NFS
under the October 5 strategic-draw diagnostics, `lethal-query-order`.

## Known Limitations And Next Upgrades

Approximately 38 seconds remains too slow for interactive use. Broader rules,
response planning and release acceptance remain unfinished. The last full
backend/browser gate is still frozen integration runtime `91b5dff`; narrow
performance evidence does not supersede that qualification scope.
