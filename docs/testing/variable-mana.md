# State-aware variable mana

Date: 2026-09-30 UTC.

## Reproduced and fixed

The parent source parser counted the printed {G} symbol, not its quantity
expression. A ready Elvish Archdruid with two own Elves produced one green;
a ready Gyre Sage with no counters also produced one. Summoning sickness was
explicitly disabled for these probes; sick sources correctly produce nothing.

The shared nonland source evaluator now supports single-color output scaling
with a recognized battlefield selector (own or all battlefield permanents),
named counters on the source, or the source's effective power. Self references
use the actual source name/short name or printed "this creature/permanent",
not a card-name whitelist. Zero/negative quantities yield no usable output.
Unrecognized quantity clauses no longer silently fall back to one printed
symbol. Stateless resource analysis returns unknown variable capacity as empty;
AI valuation and attack reservation pass public state to obtain actual capacity.

Manual immediate mana actions, automatic payment, remaining floating mana,
public mana amounts and AI resource retention use the same calculations.
Flexible alternatives remain finite sources. Readiness, sickness and actual
cost checks remain separate from retention value; this does not grant an
activation or change human spell legality.

## Verification

Fourteen canonical cached Scryfall rows with provenance supply fixtures; no
printed cards or built-in decks were invented or changed. Twenty-two new cases
cover both seats, own/all battlefield counting, removal updates, power buffs
and counters, zero-output rejection, real casting/payment and excess mana,
readiness, snapshots/views and postcombat reservation across ten style labels.
The new test file fails on the parent; the explicit ready-source probes above
establish semantic defects separately from its new helper-signature assertions.

Final focused run: 87 passed. Full final production-source suite in a separate
isolated checkout: 1,897 passed, 292 deprecation warnings, 230.85 seconds.
Frontend lint/build/unit checks pass. The initially overlapping focused/full
runs were not used as the acceptance gate; the full run was restarted in its
own copy. Initial tests used a wrong view field/stale copy-on-write card
reference; those test errors were corrected before the passing gates.

Eight seed/seat-paired logical games repeated across sixteen executions match
all reported game fields and complete identity-sensitive logs, excluding elapsed
time. No timeout, cast-cost or target rejection is logged. Two Tribal/Burn traces
change from the parent, with real Archdruid payment logs producing two through
seven green. Other six traces match. A normal failed Spell Pierce optional
payment remains normal counter resolution. See [compact results](variable-mana.json).
This is not every internal final-state field, a broad matrix or expert-play
certification; differing traces do not establish better strategy or balance.

## Browser-fixture follow-up

The sideboard browser gate again timed out during its pending operation.
Source/probes show its empty-cache setup requested live Scryfall synchronization
for Forest and Island. The copied test server now caches three canonical basic
land fixtures with packaged placeholder media before the scenario. The same
real HTTP sideboard endpoint succeeds with zero network-sync calls under a
blocking network spy; parent setup attempted both names. No production hydration
path is mocked or changed. This removes a test dependency, not proof that every
historical timeout or production network delay has the same cause.
The complete final-code Chromium rerun passes action/choice, simulator,
refresh/process-restart recovery, sideboarding and natural AI/human BO3 flows.

## Known Limitations and Next Upgrades

The supported selectors share the existing printed subject matcher, not a full
layer-4/changeling/Kindred type system. Color-dependent mixed output (for example
Bloom Tender), granted/multiple abilities, spending restrictions, conditional
activation and paid untap engines need explicit models. Zero-output activations
with incidental triggers are not modeled by an unavailable mana-color button.
Power/counter valuation does not forecast future growth, responses or multi-cast
turns. Live missing-card synchronization can still depend on network timeouts;
the fixture fix does not solve that product issue. The separate diagnostic
interpreter crash remains unverified. Manual review should assess tactical
choices and long-session presentation before claiming a finished pro-level app.
