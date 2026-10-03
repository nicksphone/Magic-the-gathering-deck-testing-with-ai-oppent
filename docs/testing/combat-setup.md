# Public-Board Combat Setup Planning

## Implemented Scope

Master and Master Plus can forecast one precombat setup action followed by a
bounded public-board combat. Casting, equipping and supported activated/loyalty
actions use real costs, target materialization and stack resolution. They advance
through actual beginning-of-combat triggers, attack declarations, defensive block
search and both damage windows instead of adding printed power numbers.

The planner runs before archetype-specific threat-first/cheap-development
heuristics. Tempo's threat-first reader now uses the selected spell face and
casting mode rather than the physical card's creature types. An already-winning
board passes toward combat instead of spending another card unnecessarily.

Attack search and setup planning share the same projected attack-line helper,
including locked payments, original declarations, block requirements, damage
allocation and state-based outcomes. The planner is bounded to at most three
own creatures, two opposing creatures and sixteen setup moves. Searches outside
those bounds retain existing heuristics; they are not claimed optimal.

Known unsupported combat clauses, unresolved choices and explicit Oracle inference
failures prevent a claimed forecast. New hand/library changes during resolution
are unknown, not a reason to choose a line using hidden draws. Forecasts assume
unannounced instant-speed responses are absent; counter/removal risk under hidden
information remains a separate planning gap.

## Evidence

Canonical fixtures cover bestow (Leafcrown Dryad), an ordinary Aura (Rancor),
Equipment (Bonesplitter), temporary pump (Giant Growth) and blocker removal
(Go for the Throat). These are constructed interaction states, not tournament
decks or invented card data.

Sixty actual before/after decisions span both seats and Aggro, Tempo, Control,
Ramp, Tokens and Tribal. The published `4457201` baseline wins fifty of the fixed
combat continuations; the revised implementation wins sixty. Full hands, public
boards, legal moves, reasons, actual payments and combat outcomes are retained on
RCHFiles. This is a decision-quality fixture result, not a matchup win rate.

An additional 140-decision probe includes all fourteen recognized archetype
labels with the same five families and both seats. It improves from 116 to 140
winning fixed combat continuations, preserving the previously correct lines.
Measured maximum selection times in this probe are 0.133 seconds at baseline and
0.172 seconds currently; these are fixture measurements, not a service-level or
large-board performance guarantee.

`backend/tests/test_ai_combat_setup.py` covers actual selections, sickness/tapping,
funding, defensive blocks, postcombat timing, resource preservation and unknown
choices/draws. Both-seat HTTP autoplay chooses bestow, pays, survives SQLite
restore and completes real combat. The focused wider combat regression passes
309 tests. The isolated full suite passes 3,267 tests (338 deprecation warnings,
439.79 seconds); frontend lint/unit/build and complete Chromium recovery,
sideboard and natural BO3 flows pass. Thirty logical seat-balanced samples over
six decks, each executed twice, finish with no timeout, determinism failure,
drift label or reported anomaly. They cover Aggro, Tempo, Tokens, Ramp and
Control templates/decks, not arbitrary-corpus strength or balance certification.

## Known Limitations and Next Upgrades

- Wider boards, multi-action setup sequences and exhaustive target alternatives.
- Adversarial responses and threat representations without peeking at hidden cards.
- General unsupported-effect detection beyond existing explicit diagnostics.
- Strong/Casual adoption with deliberate performance/strength acceptance criteria.
- Long-run matchup strength, balance and arbitrary-card rules certification.
