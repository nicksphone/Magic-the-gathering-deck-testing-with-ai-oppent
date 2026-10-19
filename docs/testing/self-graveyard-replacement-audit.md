# Printed Self Graveyard Replacement Audit

Tests/report only, pinned published 9714ee5c44073628db6b9fe456e8a4504e6ae65b.
Baseline tar SHA256: 10f0c6520b4e805b4fe2e249ddafc65d954f9d4a277f8a9fbd6a4da05f59fe3d.
No Jason shuffle-observer or Sagan entry-mill implementation is consumed.

## Canonical Inputs

Full unchanged official bulk objects are in fixtures/self_graveyard_audit/canonical.jsonl
with source hash, exact IDs and API URIs in provenance.json. Darksteel Colossus
and Progenitus print reveal-and-shuffle-into-owner-library replacements from
anywhere. Village Rites, Sickening Dreams and Millstone are actual paid stimuli.
Blood Artist and Doomed Traveler distinguish real dies receipts. Kozilek,
Butcher of Truth prints a graveyard triggered ability, not that replacement.
No names or Oracle texts are rewritten to grant a mechanic. Controlled boards
and foreign-owner/controller positions are explicitly retained test fixtures.

## Ordinary Ledger

Final whole module: 60 executed, 22 PASS / 38 FAIL, 74 warnings, 14.79s, exit1,
600-second bound. No skips, xfails or exclusions. Failures are sole desired
assertions after independently valid actual payments/transitions/restorations:

- 12 paid self destinations: both seats, both self cards, sacrifice/discard/mill.
- 4 foreign-owner sacrifice destinations.
- 4 false Blood Artist dies receipts following replaced sacrifices.
- 8 trusted stack/exile transition seams, not invented legal discard permissions.
- 8 HTTP paid sacrifice destinations across memory/file repositories and both seats.
- 2 separate missing Kozilek graveyard trigger receipts after actual discard.

Positive controls: 4 pure repeated readiness/cost/legal-view/privacy queries,
6 ordinary canonical graveyard transitions, 12 invalid duplicate/foreign/stale
sacrifice selections with full-root equality. Wrong-seat HTTP rejection also
proves root/controller/SQL equality inside all eight HTTP cases before payment.
Actual actions are repeated from identical snapshots with equal RNG/state; JSON
snapshots are also restored in a fresh subprocess. HTTP persists then reloads
the full accepted state through the real repository restore path.

Readiness returns complete metadata but does not prove semantic support.
No RNG/log/zone changes are permitted during queries. Cost payment selection
and root immutability are asserted before desired replacement outcomes.

Initial draft40: 36 FAIL / 4 PASS, 11.09s. Restart comparison used tuple output
against JSON lists and was corrected in tests only; not an engine defect.
Corrected40: 30 FAIL / 10 PASS, 9.81s, all desired assertions reached.
Expanded HTTP draft60: 38 FAIL / 22 PASS, 21.63s, eight failures were a wrong
test restore-helper name. Final uses actual _restore_active_matches and reaches
all eight desired library assertions. Historical logs/source are immutable evidence.

## General Fix Proposal, Not Production

replacement.replace_die_zone and graveyard_destination can express only a
graveyard/exile zone answer. zone_actions.sacrifice_selected then emits death
events when the moved card is GRAVEYARD; discard_simultaneous and Millstone's
mill_cards call put_into_graveyard, which also lacks the printed self procedure.

Compile the generic printed self-reference reveal/shuffle replacement into a
structured replacement plan, not card-name exceptions. The shared authoritative
graveyard-entry executor must perform that plan using original source zone,
owner, controller, incarnation and replacement-choice context. On execution,
reveal then insert into the owner's library and shuffle; do not first enter a
graveyard or emit dies. Keep sacrifice/discard/mill cause events distinct from
actual graveyard/death events. Query/planning only describes candidates, with
no RNG/log/zone mutation; execute only after full chosen payment is validated.
Coordinate the shuffle operation/cause receipt with Jason and zone-event entry
with Sagan instead of duplicating their active work.

Kozilek needs an ordinary respondable graveyard-entry trigger receipt with its
owner/controller context and eventual whole-graveyard shuffle. Its two reds
are a separate trigger/compiler gap, not authorization to auto-shuffle it as a
self replacement. No trigger resolution or full Eldrazi family support is claimed.

## Limits

Future shuffle RNG/reveal/library-membership/no-death assertions after current
destination failures are unreachable, not qualified positives. Stack/exile
seams test supported transition entry points only, not legal spell/cost/timing
stimuli from those zones. No all-rule readiness, natural-match, replacement
ordering against competing effects, token/copy/ability-removal, frontend, AI,
global shuffle or corpus-wide support claim. No production/main/live edits.

Separate six whole neighbor modules: 272 PASS, 77 warnings, 35.39s, exit0,
600-second bound. Additional costs, variable spell costs, discard history,
surveil/mill, replacement/layers and ability-model modules were unchanged.
These positives do not turn the strict new audit REDs green.
