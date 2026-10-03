# Exhaustive and announced-X spell payments

## Scope

Shared printed additional-cost parsing recognizes `discard your hand`,
`sacrifice all permanents you control`, and `discard X cards`. No card-name
payment or effect dispatch is added. Canonical Kaervek's Spite and Sickening
Dreams exercise actual payment, stack and resolution paths in both seats;
Lotus Petal and Blood Artist exercise payment timing and departing watchers.

Exhaustive payments use every currently eligible resource, not a caller-selected
subset. The casting spell is excluded from hand discard. Resources are recomputed
after mana abilities: a Lotus Petal sacrificed for mana is not sacrificed again.
Discard X requires an announced nonnegative X and exactly that many distinct owned
hand cards, excluding the spell. X is bounded by the available hand, not mana.
Checked actions reject wrong counts, duplicates, source/opponent cards and missing
X without mutating authoritative state. An empty hand/battlefield is a legal
exhaustive payment. Additional costs remain mandatory for authorized free casts;
countering a paid spell does not refund them; copies do not pay them again.

Shared discard/sacrifice operations retain events, actual destination and
simultaneous-departure watchers. Snapshots preserve X and stack effects. Public
legal-move options expose typed flags and eligible cards. Both human seats see
mandatory-all warnings and deliberate X-card selection; frontend boundary tests
reject malformed flag values.

## AI boundary

All difficulties materialize payable X using existing public-board effect scores
minus hand-retention loss. Tested minimal lethal X is retained; a symmetric sweep
that immediately loses to self-damage is rejected. Exhaustive sacrifice includes
all resource opportunity costs and uses the existing bounded unanswered engine
projection to reject tested nonwinning board destruction. A proved immediate
finish is retained. Unknown choices remain unknown, not fabricated safe outcomes.

These are supplied-legal-move decision tests, not autonomous sequencing or proof
of optimal timing, hidden-information reasoning or tournament-level play.

A separate checked diagnostic traces twelve autonomous public-board sequences
(both seats, all difficulties, both spells). Each plays a land, casts the tested
finisher and completes two priority passes. Hand, mana, actions and full logs are
retained. The opposing player is deliberately scripted to pass; this is bounded
sequencing evidence, not performance against resistance or a full-match sample.

## Canonical evidence and checklist

`backend/tests/fixtures/variable_spell_costs.json` retains Scryfall/Oracle IDs and
source URLs. Fresh full responses are archived with test evidence. Real Firestorm,
Nostalgic Dreams and Devastating Dreams remain explicitly blocked: X recipient
cardinality and random payment are not implemented by recognizing a price.
Rites of Spring is deliberately not classified as an additional-cost card; its
Oracle discard happens during resolution and linked search needs separate work.
These fixtures do not add fabricated decks or change built-in matchup balance.

Timing reference: [official Comprehensive Rules, effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
601.2g-h. Mana abilities precede payment; the engine's fixed payment ordering does
not implement the full player-chosen cost-order rule.

- [x] Exact normal/free payments, both seats, empty resources and copy/counter cases.
- [x] Actual symmetric damage, fixed targeted life loss and snapshot resolution.
- [x] Mana-source sacrifice before exhaustive payment and simultaneous death payoffs.
- [x] HTTP legal flags and rejected-payment in-memory/SQLite atomicity.
- [x] All-difficulty public-board payment decisions and canonical unsupported forms.
- [x] Frontend lint, runtime contracts and production build.
- [x] Complete isolated Chromium regression, including four new both-seat cases.
- [x] Full isolated backend suite and seat-balanced repeated replay smoke.
- [x] Verified archive, Graphify refresh and published milestone.

Focused validation: 58 new cost/effect/AI/HTTP checks passed. The earlier combined
169-case run includes existing clause and qualified-cost regressions. Frontend
lint, boundary tests and production build pass; the complete Chromium suite passes
with four new payment cases, restart/recovery, sideboarding and all three natural
BO3 modes. Its first new scenario failed because the test assumed prefixed player
target values rather than numeric seats; the selector was corrected, assertions
retained, and the entire browser suite rerun successfully.

The four-template seat-balanced replay smoke completed twelve logical BO1 samples,
each repeated twice (488.464 seconds), with zero reported determinism failures,
timeouts, anomaly labels or drift. These template samples do not exercise the new
cards by random chance and are not a broad archetype quality/balance measurement.
The canonical tests and decision traces establish the new paths directly.

Full isolated backend: **4,502 passed**, 339 deprecation warnings, 737.25 seconds.
Production code is byte-identical across backend, browser and replay copies;
tests ran against source-local disposable databases, not the live database.
Verified source/evidence archives are under RCHFiles at
`diagnostics/variable-spell-costs/20261003T152208Z/`, including initial failures,
canonical responses, twelve full decision traces and browser profiles. Graphify
AST refresh reports 9,370 nodes / 24,039 edges / 408 communities with no API cost.

## Known Limitations and Next Upgrades

General player-chosen payment order and interrupted payment continuations remain
unfinished. The existing fixed life/discard/sacrifice order is unchanged; arbitrary
payment-dependent replacements are not certified. Independent mandatory resource
groups, optional/variable/random sacrifices, X recipient lists, linked discard-to-
search counts, exile/reveal/return/tap costs and broader qualification filters
remain open. Ordinary X effect inference does not certify every X-discard card.
The AI guard is an immediate public-state check, not adversarial long-term search.
Installed dependencies are reused; fresh installation and release security are
separate gates. Do not infer complete Magic support from these bounded tests.
