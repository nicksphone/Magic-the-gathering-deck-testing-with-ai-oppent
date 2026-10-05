# Selective Hand Acquisition

## Rules and Planner Contract

Recognize complete fixed-count instructions that look at cards, put a specified
number into hand, and put the rest on the bottom. Reuse the existing selection
handler and durable bottom-order choice, rather than treating this as drawing.
Mana-spent selection retains actual casting expenditure; fixed-count selection
also works on copies and free casts. No card names select implementation paths.

The strategic opt-in can settle unfiltered selection using actual rules on an
isolated masked copy. Arbitrary opaque alternatives are interchangeable for count
valuation only; it never invents playable cards or sees their identity. It may
settle the same count for an opponent without revealing that hand. Remaining
unknown cards can move to the bottom without claiming knowledge of their order.
The legacy internal `opaque_draw_counts` keyword covers these non-draw transfers
as well; actual draw operations/triggers/restrictions remain separate.

Default projections and certainty helpers remain conservative. Known selection
options, filtered creature hits, unrelated pending choices and unsupported stack
instructions do not gain this permission. Library/card conservation and unchanged
original hand prefixes are checked after projection. Real AI selection once cards
are legally inspected still uses the existing visible-card choice policy.

## Evidence

- Six unaltered Scryfall responses and hashes/provenance are retained under
  `backend/tests/fixtures/opaque_selection/`. Impulse, Anticipate, Memory Deluge
  and Dig Through Time supply actual printed instructions; Counterspell and
  Collected Company exercise counter and filtered-selection boundaries.
- Initial canonical matrix: 42 failures / two passes before repair. Adding
  full-mana Dig Through Time exposed a standalone casting-keyword parsing gap;
  that line is not a resolving instruction. Delve payment is **not implemented**.
- Latest focused selection: 528 checks pass, including 112 new cases covering
  both seats, five strategic styles, actual Master casts, copies, counters, short
  libraries, draw restrictions, hidden-order invariance, opposing counts,
  known-card fallback and free-cast policy. Selections overlap earlier runs.
- Eight HTTP/SQLite cases pass for both human seats: paid casting, wrong-actor
  rejection with unchanged state/database, selection, deliberate bottom order
  and restart recovery. These use constructed fixtures, not tournament decks.
- Frozen runtime `370f368` passes 8,516 backend tests across all 342 recursive
  test files, checked exactly once, with 670 matching source hashes and four
  initially database-free copies. The existing complete browser suite passes,
  including all three natural BO3 modes and restart recovery.
- Eight additional Chromium scenarios pass for both seats and all four spells:
  paid casting, inspected selection, reload during choices, deliberate bottom
  ordering where required, full resolution and final reload. The first run
  exposed ambiguous duplicate-name selection in the test driver; selecting the
  intended option position fixes the test without changing production code.
  These scenarios are now part of the default browser harness.
- Main stays unchanged pending combined natural decision review. The completed
  strategic replay matrix used predecessor `80062da`, not this newer runtime;
  it cannot certify these new effects or expert AI strength.

Oracle data is canonical, not invented. Memory Deluge's mana-spent/copy behavior
also follows the official
[Innistrad Remastered release notes](https://media.wizards.com/2024/downloads/INR_Release_Notes_hzvmSd7KJG/EN_MTGINR_ReleaseNotes_20240903.pdf).

## Remaining Work

- Retain strict natural replay/reconstruction and per-decision review before
  rolling into main. Sparse seeded games do not establish AI strength or balance.
- Implement and audit casting-resource mechanics such as delve, convoke and
  improvise. Fully paid resolution here must not be mistaken for those payments.
- Extend filtered/conditional acquisition and known-library planning using
  explicit uncertainty, not fabricated hit counts or unseen average card objects.

Evidence is archived on verified RCHFiles NFS in
`diagnostics/strategic-draw-counts/20261005T102232Z`. Active source and SQLite
remain local; running jobs are not restarted on quiet logs.
