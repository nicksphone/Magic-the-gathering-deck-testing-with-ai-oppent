# Mana Multiplier Query Prefilter

## Contract

Mana output checks first parse the existing supported multiplier instructions.
Only a source with such an instruction needs an ability-suppression query.
The same parser, controller scope and suppression function remain authoritative;
independent sources still multiply together. No card metadata, legal actions,
search depth or persistent state cache changes.

This addresses a measured repeated-query cost in complex-board AI search. It
does not fix every slow decision or establish expert-level play.

## Current Evidence

- Twelve canonical cases: six query-count failures before repair and all twelve
  pass afterward as part of a 293-check selection. Both seats, actual Mana
  Reflection/Nyxbloom Ancient, opposing sources, Humility/Dress Down, temporary
  ability loss, source departure and controller changes are covered. Golden card
  data comes from existing fixtures; constructed positions are not new decks.
- The broader mana/payment/resource selection passes 495 checks.
- One reconstructed natural Tribal position, instrumented ABBA comparison:
  baseline 56.17/56.49 seconds and 3,953,310 suppression calls; prefilter
  52.50/52.78 seconds and 3,757,758 calls. All four choose the same action and
  leave authoritative state unchanged. Concurrent load and instrumentation make
  these local measurements, not a general throughput claim.
- Frozen runtime `03c00b1` is under complete backend and browser qualification.
  Neither a running job nor selected checks establish full acceptance. Main
  remains unchanged until these gates and fresh strategic decision review pass.

## Remaining Acceptance

- Complete every recursive backend test on source-hash-verified, initially
  database-empty copies and finish the actual browser/restart gate.
- Retain frozen-input, paired-seat natural replay and strict reconstruction
  evidence for the strategic candidate beneath this optimization.
- Inspect representative complex-board timings before claiming broad speedup;
  retain explicit-loss query behavior and no hidden-information leakage.

Completed evidence belongs on verified RCHFiles NFS under
`diagnostics/strategic-draw-counts/20261005T102232Z`; active source and SQLite
remain local. Do not archive/delete running copies or restart quiet jobs.
