# Bestow Casting and Lifecycle

## Implemented Scope

Ordinary mana-symbol bestow costs produce separate creature and Aura casting
actions. Printed mana cost, colors and Oracle text remain canonical; selecting
bestow changes spell types and grants enchant creature before timing, targets,
cost modifiers and payment are evaluated. Bestow cannot be combined with another
alternative casting cost. Hand and supported temporary exile permissions expose
both modes when legal; a creature-only top-library permission does not expose
the Aura mode.

The Aura mode uses shared attachment targeting, protection and actual payment.
Explicit Aura provenance lets target-specific Aura discounts work without adding
invented instructions to printed Oracle text. Both human seats can select the
cost mode and target. AI materialization uses the existing attachment projection,
and scoring evaluates bestowed characteristics instead of a creature-only view.
This is not proof of optimal strategic mode selection.

Illegal targets at resolution end bestow and let the spell resolve as a creature.
Original-object identity catches targets that leave and return. Copies retain
bestow independently of the original spell; choosing a new target binds its new
identity. An unattached or illegally attached bestowed permanent reverts in place,
and state-based actions immediately check the restored creature. Zone departures
restore printed types. Snapshots retain the bestow state, target and identity;
later activated abilities do not accidentally end bestow.

Canonical Scryfall Leafcrown Dryad and Noble Quarry fixtures retain source IDs and
URIs. Constructed interaction states are not competitive deck templates.

## Validation

`backend/tests/test_bestow.py` covers both seats, base versus bestow payment,
underfunded atomic rejection, Aura-target discounts, actual AI choices, exile
permission expiry, attachment bonuses and keywords, illegal targets, copies,
retargeting, zone changes, fixed-point state-based actions and HTTP/SQLite restore.
`frontend/tests/browser-bestow.mjs` selects bestow, targets, casts, pays, resolves
and reloads through actual App controls for both seats. Existing attachment, cost,
copy and frontend checks run alongside these tests. Final suite and replay counts
are recorded in the changelog: 3,197 isolated backend tests, 89 focused tests and
12 seat-balanced template samples repeated twice with no reported drift/anomaly
or timeout. These template samples are not bestow-corpus or matchup certification.
Sixteen actual checked decisions across four archetypes preserve full hands,
boards, legal actions and outcomes; a ready-creature/unblocked-opponent-at-four
fixture exposes a remaining creature-first preference in Aggro/Tempo.

Rules reference: Wizards Comprehensive Rules, September 25, 2026, CR 702.103a-g
and 601.2. The archived rules document accompanies the preceding activation-cost
milestone evidence on RCHFiles.

## Known Limitations and Next Upgrades

- Phasing-in-unattached behavior and arbitrary type-layer dependencies remain
  unimplemented; the conservative bestow coverage warning stays visible.
- Nonstandard bestow costs, arbitrary graveyard/library casting permissions and
  interactions with other alternative costs require dedicated acceptance cases.
- Verified bestow lifecycle does not certify every other clause on a card.
- AI mode legality and payment are tested, not expert-level planning or matchup
  balance. Broader before/after strategic decision evidence remains necessary.
