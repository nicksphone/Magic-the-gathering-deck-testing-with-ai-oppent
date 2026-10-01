# Entry Replacement Ordering and Commit

## Implemented Scope

Compleated entry reductions are now intrinsic options in the shared scalar
counter-replacement event. The affected controller can order the reduction
against supported doubling, halving and plus-one modifiers. Announced Phyrexian
life payments determine the reduction; colored payments add no reduction option.
Each ability applies at most once, and the pending packet survives snapshots
without prematurely entering the permanent. The reduction does not affect later
ordinary loyalty effects or activation costs.

Prepared entry counters commit without checking the incoming permanent's newly
active global counter bans a second time. Existing battlefield bans and the
recipient's applicable self-only entry prohibition still apply during preparation.
After entry, ordinary counter placement consults the now-active global ban.
This distinction is covered using canonical Melira and Tatterkite fixtures.

These boundaries follow [Wizards rules 614.12, 614.17d, 616.1 and
702.150](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.pdf).
This is bounded counter-entry fidelity, not general entry-layer certification.

The shared AI counter-order policy now includes operand-bearing reductions and
evaluates their resulting amount alongside existing scalar operations, without
card-name branches. The human UI uses the existing affected-player replacement
controls; the seat-two browser scenario chooses doubling before reduction and
verifies eight loyalty and once-only entry for canonical Tamiyo.
That scenario prepares a stack object with its announced life-payment payload;
it tests replacement selection/entry through HTTP, not a new full-deck cast flow.
Existing separate mana/browser fixtures exercise hybrid life-payment casting.

## Verification

- Fourteen new regression cases pass. Against the preceding commit, the eight
  ordering/ban cases produce seven failures and one pass; these are retained as
  explicitly historical failure evidence rather than passing acceptance.
- 173 focused counter/payment checks pass. The isolated full suite passes all
  2,396 tests (292 warnings, 303.88 seconds); modified backend files and canonical
  fixtures match the tested copy byte-for-byte. The disposable copy, not the live
  database, receives API/test writes.
- Frontend lint, unit contracts and TypeScript/Vite build pass. Full Chromium
  passes, including the new human seat-two ordering scenario and existing
  recovery/restart, simulator review, sideboard and natural BO3 flows.
- Eight seeded seat-paired games repeat complete results/logs over sixteen
  executions without timeout. This is smoke repeatability, not statistical
  balance or professional-AI evidence.
- Graphify AST refresh passes: 7,448 nodes, 18,612 edges, 319 communities.
Two new canonical fixtures retain Scryfall IDs and bulk provenance. The database
was opened read-only to export them. Test state entry records are explicitly
core-event packets, not invented card text or card statistics.

## Known Limitations and Next Upgrades

[Shared token/copy/return/library routes](entry-routes.md) now reuse preparation.
Unusual entry routes, generalized projected pre-entry characteristics and
simultaneous multi-kind ordering remain unfinished. The AI amount policy does not evaluate
every downstream consequence of counters, including Saga overshoot, loyalty
ability availability and nonlinear board interactions. Current bounded checks
cannot establish unrestricted Magic correctness or seasoned-player performance.
Evidence is retained on RCHFiles under project diagnostics
`entry-replacement-order/`; earlier-revision failures are labeled separately.
