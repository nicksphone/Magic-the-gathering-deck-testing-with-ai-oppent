# Domain and temporary combat-cost rules

## Combined Backend Scope

This batch implements two related families through shared application-code rules:
domain-scaled static attack costs and resolution-created global attack/block taxes.
SQLite stores snapshots only. No built-in competitive deck was altered.

### Domain attack taxes

The recognized X definition counts distinct Plains/Island/Swamp/Mountain/Forest
subtypes among the current source controller's battlefield lands. Nonbasic dual
lands contribute their basic land types; duplicate types do not increase the count.
Stale departed/control-mismatched zone entries are excluded. Controller changes,
land changes and snapshots feed the same existing domain reader used elsewhere.
Payment amount is fixed before mana activation, using the prior shared attack path.
Zero-valued costs remain optional for must-attack requirements. The canonical
Collective Restraint clause taxes players, not planeswalkers.

Coverage removes the blanket domain warning only when every domain-prefixed clause
matches this supported attack-tax definition. Other domain uses remain independently
classified; no universal domain/type-layer certification follows.

### Temporary attack and block mana taxes

Recognized resolving instructions of the form "This turn, creatures can't attack /
block unless their controller pays [mana] for each attacking / blocking creature
they control" create independent game-wide rule effects. The compiler resolves
announced X into each effect; countering the actual activated ability creates no
effect and does not refund its already-paid activation cost.

Each row retains kind, locked mana cost, original controller, source identity/name,
resolution timestamp and cleanup turn. Effects affect later creatures and either
player, survive source suppression/departure and serialize through saved matches.
They expire during the shared cleanup boundary. Old snapshots default to no effects.
They are not object-bound keyword grants: source removal must not cancel a resolved
rule change, and later creatures must not bypass it.

Block costs use the same mana/life/restricted-resource planner as other costs.
They charge once per distinct chosen blocker, not once per attacker-blocker pair.
Chosen mana creatures may tap to pay and still become blockers. Objects sacrificed
or otherwise departed while paying never become blockers. Restrictions are checked
before locked payment; an initially legal menace group can retain a single surviving
blocker after a cost sacrifice. Invalid incoming assignments cannot be excused by
their proposed blocker's subsequent departure. Existing band propagation is retained.

Tax payment is voluntary, including zero costs. The requirement solver does not
force additional taxed blockers. Volunteered blockers still maximize applicable
requirements without forcing payment for other creatures. Explicit hybrid/life
branches use the checked-action contract and both-seat selectors; mismatched or
unaffordable payments reject without authoritative memory/SQLite mutation.

Later tax resolutions change future declarations, not already-declared blockers.
Legal hints expose active taxes and per-blocker costs; diagnostics include public
battlefield clauses and already-resolved cost effects, including departed sources.

### AI planning

All difficulties finalize requested blocks against actual shared cost affordability
and requirements. Bounded activation planning parses the effect grammar rather than
card names: defensive attack taxes are evaluated in beginning of combat; offensive
block taxes after the AI has declared attackers, before advancing to blocks.
The projection uses the actual activated-cost payment path, public creature/mana
capacity, current taxes and source-independent effect data.

It scores the reduction in greedily affordable opposing declarations and penalizes
activation spending. The smallest useful X wins equal comparisons; irrelevant or
ineffective activations are filtered instead of repeatedly spending mana. The X
search budget of 20 limits this AI heuristic only, not engine legality. Counterplay,
hidden responses, exact combat assignment, defensive zero-cost avoidance of Lure,
mana-source branching and second-main resource planning remain deeper-AI work.

## Acceptance And Evidence

Canonical War Tax, War Cadence, Archangel of Tithes and Wall of Glare data retain
Scryfall fetch provenance. Collective Restraint and Hallowed Fountain reuse prior
canonical fixtures. Explicit grammar cross-products are test boundaries, not new
cards or invented competitive decks. Other abilities on these fixtures are not
automatically certified by combat-cost acceptance.

Focused tests cover both seats, actual activated stack resolution/countering,
announced X, source loss, cleanup, legacy/new snapshots, domain duplicates/control,
zero costs, later creatures, additive effects, tapped mana blockers, multi-block
charging, cost sacrifice, initially invalid intent, restricted resources, paid
requirements, explicit branches, actual HTTP X activation and SQLite restoration.

The actual App/browser flow checks both seats for domain payment rejection/retry
and actual X activation followed by block payment. A chosen Elf taps for its cost
and still blocks. Preflight originally used Archangel of Tithes's conditional
taxes; the [subsequent conditional-cost batch](conditional-combat-costs.md) implements
those clauses and uses Stormtide Leviathan's unsupported qualified subject instead.
Creature metadata readiness remains enforced; the fixture
must supply real power/toughness rather than bypass admission validation.

Frozen-source validation: 3,011 isolated backend tests passed (322 deprecation
warnings); 202 focused checks, frontend lint/unit/build and the full Chromium
suite passed. Twelve logical seat-balanced template games repeated twice resolved
with no determinism failures, drift labels or reported anomalies. Sixteen actual
controlled AI scenarios produced twelve X=1 activations with valid opposing
declarations and four Casual passes. Generic template replays establish
repeatability only, not card-use, balanced win rates or seasoned-player strength.
Controlled decision traces provide separate use evidence.

Verified logs, canonical payloads, decision traces, source snapshots and retained
failed/superseded runs are archived under RCHFiles
`diagnostics/combat-domain-temporary/20261002T234826Z`. The first browser run failed
on missing canonical creature metadata in its fixture; correcting that fixture
made the full suite pass without relaxing the admission gate. No live database
was used by these tests, and no fresh dependency installation was tested.

## Known Limitations and Next Upgrades

- Arbitrary conditional/qualified block taxes, nonmana costs, optional additional costs,
  player-selected mana sources and interrupted payment continuations remain open.
  Supported source/controller conditions and static block taxes are covered by
  the subsequent conditional-cost batch; this does not close general payments.
- General type/color/dependency layers are not complete: domain reads the engine's
  current stored land characteristics, not a certified arbitrary type-change layer.
- Broader pre-declaration timing, simultaneous cost triggers/replacements, gained
  nonkeyword requirements, specific defenders and complex bands need acceptance.
- Exact blocker requirement search can remain exponential. Narrow regression boards
  and an AI X budget do not establish arbitrary-board latency or resource quotas.
- The AI tax heuristic is not an optimal opponent policy or trained neural network.
  Full competitive strength, supported-corpus certification and operational gates
  remain unfinished in `plan.md`.
- Alpha UI redesign/visual usability review remains deferred.

References: [official rules](https://magic.wizards.com/en/rules), September 25, 2026,
508.1, 509.1c-i and 611.2c; canonical War Cadence Oracle/rulings supplied by Scryfall.
