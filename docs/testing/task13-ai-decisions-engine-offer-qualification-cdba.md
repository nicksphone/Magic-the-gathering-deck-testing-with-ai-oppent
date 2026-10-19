# Canonical AI fixtures: real two-offer qualification

This test/data-only candidate is based on immutable
`cdba5196d90b984995718c96a5e2ea8326600b10`. It supersedes the separate
153/4, 158/4, and 160/4 HOLD candidates without modifying their roots or archives.
It is not global Task 1.3 closure, an AI strength certificate, or a natural game.

## Exact Original Fixture Adaptations

Only the two original lethal-line tests receive initial pooled red mana 1,
PRECOMBAT_MAIN, active player 1, and priority player 1. This is an explicit
initial policy pose, not naturally produced mana or phase progression.

Their move list still has exactly two entries, in pass-then-cast order. The
original cast type, Lightning Bolt name, and selected hand-card ID remain
explicit. Its other metadata comes from the actual RulesEngine.legal_moves
offer matching that same type and card ID; no other hand card is offered.
No target hints, cost options, printed costs, or targets are fabricated.

The separate already-approved exact Thalia and March identity corrections and
complete canonical fixture materialization remain. All 94 original test names
and 180 assertion ASTs are preserved. The three-land March protocol test is
unchanged and still does not certify a legal exile. No production, AI policy,
weight, limit, shared loader, or runtime dependency is changed.

## Why The Offer Matters

The separate unchanged-source diagnostic executed four chooser calls. Direct
checked casts and engine-offered AI casts both paid the real red cost and dealt
three damage, for both difficulties. Minimal handwritten offers were removed
before ranking by the friendly-target filter because target_hints was absent.
This was not an observed policy, timing, or payment-engine bug.

New fidelity controls capture each actual original test before its AI consumer.
They witness the real engine query, exact matching offer, unchanged two-offer
shape, actual target candidates, and actual base cost. Minimal-offer refusal is
explicitly a malformed protocol control, not a natural-game regression claim.

## Actual Whole-Module Evidence

Both whole modules run without filters, conftest, skips, or xfails under the
same 300s TERM + 15s KILL pure ceiling.

| Epoch | Passed | Failed | Seconds |
| --- | ---: | ---: | ---: |
| Before the two offer expressions | 160 | 6 | 16.91 |
| Real offers, before negative setup correction | 164 | 2 | 16.76 |
| Final | 166 | 0 | 16.51 |

The intermediate two failures are preserved: the NEW untap negative changed
the captured state to UNTAP but retained stale main-phase offers. Its setup now
refreshes actual engine offers after changing the step and additionally
asserts no cast is offered. Its original pass/rejection/no-consumption
assertions remain unchanged. This is not an engine or AI behavior edit.

Both final positive controls execute real checked casts, consume pooled R1,
place Bolt on the stack, pass priority to real resolution, deal three damage,
produce winner 1, and move Bolt to the graveyard. Both untap negatives retain
real checked-action rejection with no mana, life, or zone mutation.

The inherited 164-case roster remains the exact ordered prefix of final 166.
All seven preimport SQL/socket/process/provider denial controls pass in each
epoch. Source/runtime maps match; no database file, unexpected denial, FD
difference, extra thread, or remaining child is observed.

Qualified interpreter:
`/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, actual
`/usr/bin/python3.12`, sys.prefix
`/home/nick/mtg-deck-testing-lab/backend/.venv`. The full 2946-file prefix maps
remain equal, SHA256
`fa2d9f799d5aaa33c560320a72fb62d1625ac639e93a0e9c7c1d936cd1556cf2`.

The sparse packet contains the complete patch over cdba, the offer-only delta,
the cumulative two-mana/two-timing/two-offer adaptation delta, exact preimages,
postimage pins, assertion/byte inverses, ordered rosters, all JUnit/log epochs,
runtime maps, and source STOP. Independent parent review precedes integration.
