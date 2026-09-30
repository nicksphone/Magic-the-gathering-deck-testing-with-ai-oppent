# Attached scaling and honest static diagnostics

Date: 2026-09-30 UTC. Parent: `60c05d990daee97f9d026cfc1825f03f3a90deb4`.
This is supported-corpus progress, not arbitrary-card or expert-AI certification.

## Reproduction and Changes

The parent matches the beginning of a printed attached modifier and applies it
as a fixed bonus. All That Glitters, Ethereal Armor, Cranial Plating and similar
cards therefore get only one increment regardless of resources. Conditional
keyword text can likewise become an unconditional grant.

Attached clauses now require a complete supported form. Battlefield counts use
the attachment's current controller, not the creature's controller. Supported
type unions count each permanent once, including artifact/enchantment cards.
Basic land subtypes and Gates are counted from current land type lines. The
supported "other creature" count excludes the attached target. Selected/all
source-counter counts exclude private engine metadata. Counts feed the same
continuous evaluator used by combat, public views, layer traces and AI creature
valuation; evaluating or restoring a snapshot does not change authoritative state.

Keywords are recognized as complete known-keyword lists, not words inside a
conditional or quoted ability. A known P/T clause can still apply when a
separate granted-ability clause is unknown. Unknown attached subject clauses
are listed in layer diagnostics and the source's public `effect_warnings`.
Both human seats see an "Unsupported static effect" indicator with clause
details in its tooltip. Runtime response checks reject non-string warnings.

Twenty-eight fixture rows come from the existing provenance-backed Scryfall
knowledge table, read-only. No cards or built-in deck definitions were invented
or changed. Thirty-one new tests cover both seats, scaling resources, counters,
control changes, multitype union counting, snapshots, public stats, AI valuation,
layer traces, source departure and unknown clauses. Parent testing reports
27 failures and 4 passes; some failures are new diagnostic-interface checks,
so the count itself is not semantic proof. Scaling assertions independently
reproduce the incorrect flat bonuses.

The actual human UI/API scenario starts with a 5/5 enchanted creature, targets
Sol Ring with Naturalize, then observes 4/4 after resolution while printed stats
remain 1/1. It also checks the unknown-static warning. An initial fixture left
Unholy Strength unattached; state-based actions correctly removed it, producing
an additional decrease. The fixture now attaches that Aura legally. This was
test setup, not an engine failure or a reason to disable state-based actions.

## Validation

The isolated production-source backend suite passes 1,974 tests with 292
deprecation warnings in 190.59 seconds. Final focused attachment/payment tests
pass all 77 cases. Frontend lint, TypeScript/Vite build and unit/runtime-contract
checks pass. The full Chromium harness passes the new scaling/removal/warning
scenario plus actions, choices, simulator recovery, saved-match refresh and
process restart, sideboarding and natural AI/human BO3 flows. Tests use disposable
source/database/cache copies, never the live user database. Dependencies are
the already-installed environment; this is not a fresh-install validation.

[Eight seeded, seat-paired games](attached-scaling.json) repeat their complete
reported game objects/logs across sixteen executions, without timeout or logged
cast/target rejection. They are unchanged from the parent, so they check existing
behavior rather than independently exercise the new attachment mechanics.
One optional Spell Pierce payment fails normally, not as a rejected cast.
Source fingerprints, seeds and hashes are retained. This is not a full internal
state equivalence test, statistical matchup estimate or professional-AI verdict.

## Known Limitations and Next Upgrades

These diagnostics cover detected attached subject clauses, not every static
ability. The existing static reader still excludes conditional prefixes,
activated/triggered bodies and quoted abilities. No warning is not a certificate
of complete card support. Domain, attachment counts, target-color counts,
conditional grants, granted activated abilities and arbitrary source-named
counter clauses remain unsupported here.

Reconfigure remains a distinct implementation task: its two activated actions
must use priority/stack responses and durable choices, while attachment changes
must apply the creature-type exception and restoration through an explicit type
layer. Simply allowing creature Equipment to attach is not sufficient. Fortify,
special equip costs, subtype/type-changing effects, timestamp dependencies and
full ability suppression remain open.

AI receives corrected current characteristics, not new adversarial attachment
planning. Small repeated games test regression/repeatability, not balance or
professional-player strength. Manual review should assess tactical decisions,
warnings, hover readability and long-session presentation.
