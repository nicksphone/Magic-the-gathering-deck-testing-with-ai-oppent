# Current 155-Card Inventory

Pinned source: `352f3b86579f216f7ce52f34070dffa9811c1063`. The unchanged whole
inventory module ran eight ordinary passes in 5.67 seconds, exit 0. All 2,496
recorded source-file hashes matched before/after, no database was created,
descriptor maps matched and extra threads were absent. Nine precollection
native-denial controls and the module's three intentional SQL/socket/child
denial tests passed. No production, fixture or coverage-warning code changed.

The runtime-hydrated offline preflight reports 155 metadata-ready cards across
11 built-in decks, six cards with known admission gaps and 149 without a known
gap. The six are:

- Archangel of Wrath: kicker.
- Springheart Nantuko: bestow.
- Suncleanser: conditional static instruction/predicate and counter prohibition.
- The Wandering Emperor: conditional static instruction/predicate.
- Veil of Summer: keyword counter variant fidelity.
- Volatile Stormdrake: keyword counter variant fidelity.

These are conservative admission diagnostics, not six independently proven
runtime bugs. Existing paid component qualifications do not automatically clear
them or prove every printed instruction. All 155 report records explicitly keep
`complete_card_semantics` as `unverified`.

## Separate Canonical And Runtime Views

The raw-canonical view retains 171 surfaces and 315 printed lines, 138 exact
printing joins and 17 exact-name representative Oracle joins (not identical
printing IDs). It reports 153 metadata-ready records, 12 diagnostic-gap cards
and 143 without a known gap. The hydrated view retains 171 surfaces and 332
lines. These counts must not be interchanged: six hydrated gap cards does not
mean only six raw-canonical diagnostics or 149 fully supported cards. The report
retains all original root/face text, mismatches and unsupported contract lines.

The first complete run passed all eight game/test assertions in 5.74 seconds
but its wrapper exited 1: the final denial counter expected the raw socket
event label rather than the guarded-constructor label actually observed.
That ledger is preserved. Only that expected wrapper label was corrected;
the guard, tests, product and assertions were unchanged for the successful
whole-module run. Both inventory reports are exactly equal. The first run
generated 155 bounded SVGs through the real hydration path; the final run reused
those assets and generated none. This is not an ASGI cold-start/media gate.

Evidence: `parent-integration/inventory-current352f-eight-20261008/` under
the MTG NFS archive, including both receipts, the independent verification and
byte-verified source tar. No SQL/HTTP/browser, expert-AI, arbitrary-deck or
release-completion claim follows from this inventory.
