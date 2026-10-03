# Attack payment branches and minimum blocking requirements

## Implemented Scope

Two related backend mechanic families extend the shared combat declaration paths.
No competitive deck was changed and no card-name gameplay dispatch was added.

### Mana attack costs

Recognized per-attacker controller/planeswalker tax clauses accept fixed generic,
colored, explicit colorless, snow, ordinary hybrid and Phyrexian mana symbols.
The existing enchantment-count X definition remains supported; other X definitions
remain unknown. Independent sources concatenate costs in attacker/source order.
Costs remain locked before mana activation, with non-vigilant attackers already
tapped. Restricted-mana eligibility, life-payment legality and affordability use
the existing mana planner, not a combat-only payment implementation.

Checked actions require an explicit branch for every hybrid symbol, including
choosing colored mana versus two life for Phyrexian symbols. Missing, wrong-count,
invalid and unaffordable branches reject atomically. Legal hints provide per-attacker,
per-defender cost/symbol views. Both human seats use explicit selectors; changing
the defender or cost invalidates mismatched selections. Branches travel in the
submitted declaration; resulting life/mana state survives snapshots without a new
priority window or a separate mid-cost pending choice. Selector drafts are not
persisted across refresh; reloaded users deliberately select again before payment.

AI finalization uses the same planner's recorded branch allocation, preferring the
first affordable mana alternative before life for the canonical Annex fixture.
It does not propose an attack whose payment consumes its last life or removes a
chosen attacker. This is legality/safety improvement, not optimal resource planning.
Required attacks never force a voluntary tax, including a zero-valued cost.

### Minimum blocking requirements

Static self, enchanted and equipped creature clauses of the form "must be blocked
if able" or "must be blocked by N or more creatures if able" create independent
group requirements. Supported compound clauses retain each requirement, including
canonical Gorm's shortened self-name. A minimum requirement scores once when met;
it does not score once per blocker and it is not a menace restriction. One legal
blocker must block Gorm when two cannot; a one-blocker cap overrides the otherwise
achievable two-blocker requirement. Full source ability loss removes printed
requirements; an independent attached source remains independent.

The exact solver composes group/pair/global requirements with pair eligibility,
menace, capacities and declaration limits. Rational per-blocker bounds account for
saturated thresholds; mixed 101-blocker tests avoid the previous overcounted bound.
Group-only search prefers omitting unnecessary optional blockers, while pinned
human declarations remain valid if they maximize requirements. This is not a
general optimal-combat or worst-case-latency guarantee.

Unknown qualified blocker subsets or compound clauses remain explicit coverage
gaps. The subsequent [domain/temporary cost batch](combat-domain-temporary-costs.md)
implements Collective Restraint. The subsequent [conditional-cost batch](conditional-combat-costs.md)
implements Archangel of Tithes's tax clauses and uses Stormtide Leviathan's
unsupported qualified subject for preflight acceptance. Supporting more taxes must not remove warnings
for genuinely unsupported forms.

## Acceptance

Canonical Gorm, Maarika and Collective Restraint fixtures retain Scryfall provenance;
Annex uses the prior canonical fixture. Grammar-only boundary tests are explicitly
labeled, do not enter the card corpus and are not fabricated competitive decks.
Other abilities on these cards (partner, conditional indestructible, excess-damage
triggers, domain) are not certified by these combat acceptance tests.

`test_combat_minimums_payments.py` covers both seats, individual and combined
thresholds, one-blocker limits, suppression, competing ties, independent exhaustive
assignment comparisons, additional-block capacity, wide boards, explicit branch
rejection, mana/life expenditure, zero-cost optionality, AI safety and HTTP/SQLite
recovery. Existing mana/declaration/coverage suites protect shared consumers.

`browser-combat-branches.mjs` uses actual App/API controls for both seats: the
attack button requires a deliberate branch, an unaffordable mana choice rejects
without revision change, a life choice succeeds, one blocker rejects and two
succeed. This is functional evidence, not a visual UX audit or alpha redesign.

Verified 2026-10-02: 2,977 isolated backend tests passed (316 deprecation warnings),
186 focused tests passed, frontend lint/unit/build and the complete Chromium
harness passed. Four additional both-seat snow grammar probes verify provenance
and atomic rejection. Twelve logical seat-balanced template games, each repeated
twice, resolved without determinism failures, drift labels or reported anomalies.

Sixteen controlled actual AI decision scenarios retain full before-state/actions:
Strong, Master and Master+ paid white mana when available and life otherwise,
then met Gorm's two requirements; Casual passed in four scenarios. These are not
complete competitive games, training or strength evidence. Final evidence, saved
probe runners, official rules, canonical payloads and failed/superseded runs are
archived on RCHFiles `diagnostics/combat-branches-minimums/20261002T231128Z`.
All running test databases stayed in isolated local copies, never on NFS or in
the live checkout; successful disposable artifacts were removed after verification.

## Known Limitations and Next Upgrades

- Nonmana costs, optional additional costs, arbitrary conditional/qualified block taxes,
  individually chosen mana sources and interrupted cost continuations remain open.
  The subsequent domain/temporary-cost batch implements domain attack taxes and
  resolution-created global block mana costs. The conditional-cost batch adds
  supported source/controller predicates and static block costs, not all payments.
- Temporary/granted nonkeyword and qualified-blocker requirements, specific defenders,
  attacker-controlled assignment and general band interactions remain unfinished.
- Exact requirement search can still be exponential. Narrow wide-board cases are
  not arbitrary-board performance acceptance or an operational job-budget guarantee.
- AI spending tradeoffs across combat, second main and racing remain heuristic;
  passing a declaration test is not seasoned-player strength evidence.
- The generic seat-balanced matrix measures bounded repeatability, not these cards'
  usage, competitive win-rate balance or arbitrary Magic correctness. Controlled
  actual AI decisions and focused/browser fixtures supply separate use evidence.
- UI ergonomics/redesign and broader rules/operational release gates remain deferred
  or unfinished as recorded in `plan.md`.

References: [official rules](https://magic.wizards.com/en/rules), September 25, 2026,
107.4f, 201.5c, 508.1d-j and 509.1c; canonical Scryfall Oracle/ruling fixture data.
