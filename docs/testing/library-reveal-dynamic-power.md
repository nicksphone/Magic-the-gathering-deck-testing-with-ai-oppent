# Library Reveal Dynamic Power

The reveal-to-hand selector now uses the existing nullable characteristic query
when a creature has no fixed numeric power. A real characteristic-defining
ability therefore applies in the library, using its owner's resources rather
than a stale controller field. Unknown power remains ineligible for a power
threshold; the combat convenience helper that treats unknown as zero is not
used. Existing fixed numeric conversion and mana-value-first ordering remain.
The automatic secondary power comparison uses the same derived value.

Only `effects/handlers.py::topdeck_reveal_creature_to_hand` changes. All bytes
outside that function are identical to published `b7201869`. No continuous-rule,
API, schema, scoring coefficient, card-name branch or original test is changed.

The new 22-case module first reports 12 failures and ten passes, then passes all
22 after the correction. It uses the committed complete Adeline seed and full
official Centaur Courser data. Both seats cover zero/two/three controlled
creatures, stale controller versus library owner, snapshot restoration and a
checked private selection, and a genuine equal-mana-value comparison. Unknown,
malformed and numeric-string compatibility cases are explicitly internal
protocol inputs, not claimed canonical card fixtures.

One subsequent declaration passes all 1,254 ordinary cases in 66 whole modules
in 144.58 seconds, including every earlier 1,224 identity, the new 22 cases and
eight existing pure library neighbors. No failures, errors, skips or exclusions;
the two dependency deprecation warnings remain. A first wider attempt passed
1,246 and failed eight because its isolated intake omitted the committed root
Twinshot Sniper RAW file. Restoring that exact Git blob, with its unchanged
test-side SHA, produced the final result without product/test/runtime changes.
That failed intake ledger remains distinct.

Seven native denial controls, source preservation, exact FD sets and empty
child/thread/database checks pass. The fresh locked runtime retains all 3,674
files, four links and 429 directories. This is a core selector/composed pure
regression qualification, not a new HTTP, natural-game, hosted-CI or Phase 1
completion claim. The separate library fixture migration and its remaining
literal-scope issues are still open.
