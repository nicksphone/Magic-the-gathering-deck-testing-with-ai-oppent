# Attached predicates and branch selection

Date: 2026-09-30 UTC. Parent: `ac08124072706eae59aaada33169fb41f42540c8`.

## Implemented

Attached fixed/scaling modifiers and known-keyword grants now evaluate supported
prefix/suffix "as long as" conditions against current public state. Conditions
return true, false or unknown. Only a proven false condition selects an
otherwise branch; an unknown condition and its otherwise branch remain warnings.
Additional bonuses and Domain/Threshold ability-word prefixes retain their
actual condition/count rather than becoming unconditional effects.

Supported predicates cover target colors, card types and recognized single-word
creature subtypes; own/opposing colored permanents; minimum public graveyard
size; and minimum source-counter count. Conditions use the source's controller,
even when the attached creature belongs to the opponent. Private counter metadata
does not contribute. Triggered, activated, temporary and quoted granted bodies
are not applied as always-on static modifiers.

Domain scaling reuses the existing distinct-basic-land-type evaluator, so duals
and triomes contribute their actual subtypes rather than number of lands or
available mana colors. Target-color scaling reuses the existing card-color
adapter. Attachment counts include qualifying Auras/Equipment controlled by
either player and count each permanent once, including the source itself.
All changes reach combat, public views, layer traces and shared AI valuation.

The official rule 205.3m creature-subtype registry is packaged offline, with the
[September 25, 2026 rules URL](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
and source hash in `backend/rules_engine/creature_subtypes.json`. It contains
324 unique names, including the compound Time Lord entry. An article followed
by an unknown status/type word is not mistaken for a false subtype predicate.
The current attached-condition grammar still supports only single-word subtypes.

## Evidence

Forty-two canonical Scryfall fixture rows come from read-only local knowledge
data. No card definitions or built-in decks were invented. Twenty-seven new
tests cover both seats, false/true/unknown branches, subtype predicates,
multicolor/empty colors, domain, source/target controller distinction,
attachments, threshold, source counters, public views, snapshots and AI value.
Two earlier diagnostic expectations are replaced because their scaling forms
are now implemented; remaining unknown clauses stay explicitly tested.

On the isolated parent, the new file reports 25 failures and 2 passes. Some
failures involve the new predicate interface, not semantic mismatches. Actual
golden characteristic checks independently reproduce wrong domain, colors,
attachment counts, conditional bonuses and the false otherwise branch.

Final focused checks pass 102 tests. The full isolated production-source backend
suite passes 1,999 tests with 292 deprecation warnings in 306.31 seconds. Frontend
lint, TypeScript/Vite build and runtime/unit gates pass. Installed dependencies
were reused; this is not a clean dependency installation test.

The real UI/API scenario plays Island to increase domain on an enchanted
Ornithopter, then casts/resolves Whip of Erebos. The black permanent enables
Abzan Runemark's vigilance on the opponent's creature because the source's
controller now meets the condition. Printed stats remain intact. The browser's
first new attempt used an incorrect button label; it was corrected to the
actual "Play Land Island" control rather than changing application behavior.

The final complete Chromium rerun passes action/choice scenarios, simulator
preflight/recovery, saved-match refresh/restart, creation recovery, sideboarding
and natural AI/human BO3 flows as well as the new predicate scenario. All API
tests use disposable source, database and cache copies rather than the live
user database.

[Eight seeded seat-paired games](attached-predicates.json) reproduce their full
reported game objects/logs across sixteen executions without timeout or logged
cast/target rejection. All are unchanged from the parent; targeted tests, not
this unchanged smoke matrix, verify the new mechanics. One optional Spell
Pierce payment fails normally rather than a cast being rejected. Seeds, log
hashes and production-source fingerprints are retained. Equality is not a
full internal-state equivalence test, strength rating or balance measurement.

## Known Limitations and Next Upgrades

Predicates are bounded, not arbitrary Oracle interpretation. Compound subtypes,
statuses, negation, complex/composed comparisons, dynamic color/type layers,
source-named counters and granted activated abilities need additional work.
Unsupported attached cost reductions on Strong Back are still reported even
though its attachment-count bonus now works. Armament of Nyx's separate
otherwise prevention instruction is not implemented by this characteristic
evaluator and stays diagnostic when applicable. Recognizing one clause never
certifies an entire card; no warning is not proof of complete support.

Reconfigure still requires both stack-based actions and correct type-layer
projection/restoration. Full ability suppression and layer dependencies remain
open. The broad simulator Domain warning is deliberately retained because
other Domain mechanics are not all covered. Shared AI characteristics improve
specific evaluation inputs, not adversarial search, expert strategy or balance.
Manual review remains necessary for tactical play and long-session ergonomics.
