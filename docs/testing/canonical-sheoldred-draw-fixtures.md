# Canonical Sheoldred Draw Fixtures

Over an isolated `cdba5196d90b984995718c96a5e2ea8326600b10` archive,
`test_draw_triggers_no_recursive_draw.py` now materializes its named Sheoldred
positive from the complete committed official row. Previously its helper
renamed an Island and supplied only the two draw clauses, omitting deathtouch
and the remaining printed characteristics.

The unchanged `canonical_positive_fixtures.raw_card` loader checks complete
seed155 SHA-256
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
Its committed provenance records the 2026-10-12 Scryfall collection intake,
HTTP 200 responses and no Oracle modification. Sheoldred's full sorted compact
object SHA-256 is
`a6e9b1b3748becaaed1316a4ac7ea8c2ae340de41dada04189816990d2901b5f`.
No provider request, RAW rewrite, production or shared-helper edit was needed.

A separate seeded Factory materializes the full row. Its never-drawn library
template supplies the trusted battlefield pose, preserving the existing card
ID, ownership/control, instance order, zone-change sequence and original
summoning-sickness value. The original game RNG, starting decks and captured
stock facts are unchanged. This direct synthetic pose does not certify stock
admission, a paid cast, entry triggers or an actual card draw.

Both original test names, all five assertion statements and all event and
resolution calls remain byte-exact. Outside the helper, the only edits remove
the two handwritten Oracle arguments from fixture calls; no expectation
operands change. Original direct `draw_card` event operands remain unchanged.
The helper has no external callers in the source baseline.

## Observed Component Acceptance

- RED: the two whole modules (original plus new consumer fidelity) produced
  5 passed / 2 genuine fidelity failures in 1.48 seconds. Both original tests
  passed; the new observations exposed their actual incomplete named sources.
- GREEN: the same two whole modules produced 7 passed in 1.47 seconds.
- Final: all four whole modules produced 16 passed in 2.54 seconds, with no
  failures, errors or skips. The unchanged neighbors were
  `test_each_player_draw.py` and `test_draw_restrictions.py`.

The new fidelity module wraps the actual original helper/event calls, delegates
to their real implementations and observes the source before the event. It
checks full canonical facts, original runtime identity and event operands,
RNG/stock/deck preservation, independent objects and complete RAW/provenance
pins. It does not substitute a draw resolver or call a chooser.

All runs used the existing 300-second precollection pure audit guard, eight
physical SQL/socket/child/provider negative controls and no test filters. Each
run preserved all 3,388 source files and 2,946 runtime files plus four links;
there were no unexpected events, FD changes, children or non-main threads.
Neither source-default nor routed databases were created. The documentation
and administrative AST graph update followed the final gate.

This is bounded fixture acceptance, not whole-project, Phase 1, browser,
native-game or SQL qualification.
