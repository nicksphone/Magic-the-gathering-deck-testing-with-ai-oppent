# Printed activation and trigger suppression

## Implemented paths

The shared continuous-effect adapter now exposes whether supported battlefield
all-ability loss removes a permanent's printed abilities. Mana capacity/payment,
ordinary activated/loyalty/equip/crew moves and checked activation writes consult
that result. Printed trigger collection, including supported Saga and annihilator
paths, does the same. A later keyword grant restores only that keyword, not all
printed Oracle abilities. Printed card data stays unchanged.

The adapter recognizes the existing bounded all-ability-loss grammar and scope;
it is not an arbitrary Oracle interpreter. Creatures affected by Humility or
Dress Down cannot use their printed mana/activated/triggered abilities. Basic
lands retain mana abilities when not affected; an affected animated basic land
loses those intrinsic abilities too. Noncreature suppression sources still
generate their own supported triggers.

Battlefield departure captures the suppression result in last-known information,
which survives snapshots and SQLite restore. Supported self-death triggers use
that pre-departure result instead of regaining abilities simply by entering the
graveyard. Abilities already on the stack remain independent and resolve after
their source loses abilities. Keyword instance triggers continue to use the
existing effective-keyword adapter, including newer resolution-created grants.

## Rules and canonical fixtures

Wizards' [September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
cover ability removal (113.10), stack independence (113.7a), pre-event trigger
checks (603.10), basic-land abilities (305.6) and layer-six changes (613.1f).
Full dependencies and cross-layer effect continuation require further work.

Six canonical Scryfall rows retain IDs, API URLs and retrieval dates in
`backend/tests/fixtures/ability_suppression.json`: Llanowar Elves, Royal Assassin,
Soul Warden, Blood Artist, Humility and Dress Down. Both-seat tests cover actual
mana capacity, activation legality and atomic rejection, entry/death triggers,
stacked trigger/activation independence, keyword grants and HTTP/SQLite restore.
The animated basic-land characteristic fixture is explicitly synthetic; it does
not invent a spell or claim full land-animation semantics.

## Acceptance evidence

October 2, 2026: **2,716 backend tests passed** with 295 deprecation warnings,
plus **173 focused checks**, frontend lint/unit/build and the full final-source
Chromium harness. Twelve logical seat-balanced smoke games each repeat twice
without reported determinism failures, timeouts or anomaly labels. This narrow
template sample is repeatability evidence, not balance or strength certification.
Tests run against isolated source-local databases, not live user data. Reused
dependencies and DOM-driven browser checks are not clean-install, visual or
arbitrary-card certification. Failed/superseded and final checks, canonical data,
official rules and closed test copies are retained on RCHFiles under
`diagnostics/printed-ability-suppression/20261002T040613Z/`.

## Known Limitations and Next Upgrades

- The subsequent [static-source increment](static-ability-suppression.md) integrates
  additional readers; full static/replacement/prevention/permission suppression
  remains incomplete and requires further integration and golden fixtures.
- Arbitrary gained non-keyword abilities, conditional suppression, dependency
  ordering and effects spanning multiple layers remain unfinished.
- Legacy last-known snapshots do not contain suppression history; missing facts
  cannot be reconstructed precisely. Full simultaneous departure/reentry LKI
  correctness needs separate acceptance.
- Broader AI quality and operational release checks remain open. Alpha UI
  redesign remains deferred.
