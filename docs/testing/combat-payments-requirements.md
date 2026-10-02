# Combat payments and target-specific blocking

## Combined backend batch

This records the original numeric/Lure acceptance. The subsequent
[mana-branch/minimum-requirement batch](combat-branches-minimums.md) extends
current support; historical counts below are not the newer batch's evidence.

Two related mechanic families share declaration validation, AI finalization and
diagnostics. Gameplay remains application code; SQLite stores snapshots only.

### Numeric attack payments

- Fixed generic mana taxes per creature attacking the source's controller.
- Clauses that also protect planeswalkers controlled by that player.
- X defined by the current number of enchantments the source's controller controls.
- Independent sources add their costs. Printed source suppression disables them.
- Costs are locked before mana abilities. Non-vigilant attackers tap before
  payment, so they cannot generate mana for their own attack; vigilance permits it.
- The existing mana planner pays a combat cost, not a spell/activation cost.
  Spell discounts and creature-spell-only mana cannot pay it.
- Checked declarations are atomic on failure. Successful payment is committed
  once before attack events. Must-attack requirements never force voluntary taxes;
  an available untaxed planeswalker can still make attacking obligatory.
- A creature sacrificed to generate mana for a locked cost never becomes attacking
  and emits no attack trigger. Human legal cost choices are retained; AI avoids
  proposing an attack whose chosen creatures disappear during its payment plan.

### Target-specific blocking requirements

Supported static "All creatures able to block [this/enchanted/equipped creature]
do so" clauses create independent source-target requirements. Blocking a different
attacker does not satisfy them. Recipient ability loss does not remove an Aura's
or Equipment's independent requirement; source loss does.

The declaration solver maximizes requirements while respecting pair eligibility,
Menace, alone restrictions, distinct-creature limits and additional/unlimited block
capacity. Its upper bound now accounts for each blocker's capacity and each target's
weight. There is no arbitrary legality cutoff; pathological exact-search latency
remains an operational risk.

### AI, trace and coverage integration

All AI difficulties finalize proposed attacks against actual affordability and
finalize blocks against shared maximum requirements. An unpayable attack becomes
a legal alternative/no-attack declaration rather than a repeated invalid action.
This prevents invalid actions; it does not prove optimal tax spending or combat.

Legal moves and the public-only locked rules-diagnostics endpoint expose active
taxes and source-target block requirements. Logs distinguish combat-cost mana
activation, actual attack payments and satisfied targeted blocking requirements.
These are use signals, not proof that every unplayed mechanic was exercised.

Blocker declaration precedes the active player's priority window. Passing cannot
bypass required attackers/blockers; a legal empty declaration is recorded before
priority resumes. Existing first/double-strike and lifelink assertions are retained.

Coverage uses the implemented clause parsers: supported mana taxes stop producing
false unsupported-payment warnings. Norn's Annex is now handled by the later
branch-payment batch. Collective Restraint's domain-dependent tax remains
unsupported and retains simulator exploratory review. No all-card certification follows.

## Acceptance contracts

Canonical Scryfall fixtures retain fetch provenance. Existing tax data is in
`combat_coverage.json`; the new six-card fixture is
`combat_payments_requirements.json`. No built-in competitive deck was altered.

`tests/test_combat_payments_requirements.py` exercises both families, both seats,
HTTP/SQLite restoration, complete rejection snapshots, actual mana expenditure,
actual required blocks, source/recipient suppression, tax/requirement conflicts,
planeswalker exceptions, restricted mana, vigilance and all four AI difficulties.
Large competing-target boards verify capacity-aware upper bounds.

`browser-combat-payments-requirements.mjs` uses the actual App/API to reject an
unpayable two-attacker declaration, pay for one attacker, reject a missing required
block and submit a legal block. The separate preflight check now uses canonical
Collective Restraint to ensure unsupported payments warn without admitting a job.
These are functional flows, not the deferred UI redesign or a visual usability audit.

Verified 2026-10-02: 2,922 full backend tests passed (314 deprecation warnings),
189 focused tests passed, and frontend lint/unit/build plus full Chromium passed.
Twelve logical seat-balanced games, each run twice, completed with zero determinism
failures, drift labels or reported anomalies. The generic template matrix is not
evidence that every new card was played; focused canonical states and the browser
flow supply actual-use evidence for the two new families.

`mechanic-use-final.json` and its saved runner retain actual two-seat AI decisions
on controlled public-board states: Strong, Master and Master+ paid and fulfilled
the targeted block; Casual passed. This is not a complete competitive game or
training/strength measurement. Final and failed/superseded runs are preserved
separately on RCHFiles `diagnostics/combat-payments-requirements/20261002T081732Z`.
All running test SQLite files stayed local and isolated from the live database.

## Known Limitations and Next Upgrades

- Nonmana life/sacrifice/discard costs, conditional taxes, block payments and
  optional additional attack costs remain unfinished. The later batch handles
  recognized mana/Phyrexian branches and zero-valued optionality.
- Specific-defender attack requirements, temporary/granted nonkeyword requirements,
  qualified blocker subsets and attacker-chosen block assignment remain unfinished.
  The later batch handles static "must be blocked" and minimum-number requirements.
  Unknown targeted-block clauses receive explicit coverage gaps.
- Full dependency/type/color layers, arbitrary gained nonkeyword abilities,
  complex band interactions and pre-entry rules are not certified.
- Exact blocker search can still be exponential. Simple 101-blocker tests are not
  a general latency guarantee; broader profiling and job budgets remain necessary.
- Generic archetype replays establish bounded repeatability only. A card present
  in a deck or hand but never used is not mechanic acceptance or AI-training evidence.

Reference: [official Comprehensive Rules](https://magic.wizards.com/en/rules),
508.1 and 509.1, September 25, 2026 revision.
