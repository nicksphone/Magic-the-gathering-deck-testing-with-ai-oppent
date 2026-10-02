# Combat declaration limits and requirements

## Implemented scope

Unconditional numeric static clauses of the form "No more than N creatures can
attack/block each combat" constrain the entire declaration. Independent sources
combine by the smallest limit. "Attack you" limits count only attackers directed
at that source's controller, not their planeswalkers. Block limits count distinct
blocking creatures, not attacker/blocker pairs. Losing printed abilities disables
the source's printed limit. Rules remain application code, not SQL.

Recognized self, attached and global "each combat if able" requirements use the
same current public-board restrictions and keyword readers as combat. Each
applicable requirement contributes separately. Declarations must satisfy the
maximum possible number without violating a restriction, including Menace,
can't-attack/block-alone and additional-block capacity. No payment is forced.

Checked human actions reject invalid or submaximum declarations atomically.
Internal engine calls can complete a compatible partial declaration. Every AI
difficulty finalizes combat intent through the shared constraints, preserving
existing tactical intent among equally weighted legal choices. Pending mechanic,
replacement and trigger choices take precedence over declaration repair.

Legal-move hints and the locked `/matches/{id}/rules-diagnostics` endpoint expose
active limits and source provenance. No snapshot schema migration is required.

## Regression evidence

Canonical Scryfall data and provenance are retained in
`backend/tests/fixtures/declaration_limits.json`. Tests cover Silent Arbiter,
Dueling Grounds, Crawlspace and recognized requirements on Juggernaut, Goblin
Rabblemaster and Invasion Plans. These fixtures are not fabricated decks or
whole-card correctness certificates.

`tests/test_declaration_limits.py` checks both seats, HTTP rejection and unchanged
SQLite state, restored matches, source suppression, planeswalker exceptions,
multiple weighted requirements, Menace, a shared unlimited blocker, 101 required
blockers, all AI difficulties, tactical tie preservation and pending choices.

The guarded browser fixture and `browser-declaration-limits.mjs` exercise the
actual App/API: seat two submits two attackers, sees rejection without a revision
change, then submits one legal attacker. This is functional evidence, not proof
that the deferred alpha UI is usable or visually finished.

Verified 2026-10-02: 2,883 backend tests passed (312 deprecation warnings), 122
focused tests passed, and frontend lint/unit/build plus the full Chromium harness
passed. Twelve logical seat-balanced games, each executed twice, completed with
zero determinism failures, drift labels or reported anomalies. This narrow
template-deck sample does not measure competitive strength or matchup balance.
Final, failed and superseded evidence is preserved separately under RCHFiles
`diagnostics/declaration-limits/20261002T073832Z`. Tests used isolated local SQLite
copies, never the live database; archived SQLite is not used as running storage.

## Known Limitations and Next Upgrades

- Subsequent [payment/target work](combat-payments-requirements.md) implements
  mana attack taxes, deliberate hybrid/Phyrexian branches, Lure-style and static
  minimum-number target requirements. Other attack/block
  costs and conditional numeric limits remain unsupported.
- Mandatory attacks at a particular defender and attacker-controlled block
  assignment remain unfinished. Invasion
  Plans explicitly receives an unsupported assignment-controller coverage tag.
- Other clauses on tested cards are not certified by this milestone; Juggernaut's
  Walls restriction, for example, is outside this acceptance scope.
- The exact required-block search has no arbitrary correctness cutoff but can
  be exponential on pathological boards. A 101-blocker simple-board test is not
  a general latency guarantee. Operational profiling and diagnostics remain open.
- Broader continuous-effect dependencies, arbitrary gained nonkeyword abilities,
  expert AI and universal Magic support remain separate unfinished goals.

Rules reference: [official Comprehensive Rules](https://magic.wizards.com/en/rules),
sections 508.1 and 509.1. Acceptance uses the September 25, 2026 revision.
