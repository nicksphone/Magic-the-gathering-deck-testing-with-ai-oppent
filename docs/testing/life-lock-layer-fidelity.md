# Printed Life Locks and Ability Suppression

Status: separate unpublished backend candidate. Qualification remains open.

## Shared Repair

Life-total locks and printed gain/loss prohibitions now use the existing
ability-aware battlefield iterator. A permanent that loses all its printed
abilities no longer imposes those printed prohibitions. Turn-scoped prohibitions
remain independent. Controller checks and recognized clause scope are unchanged;
this is not a new general Oracle parser or complete continuous-layer model.

The canonical Platinum Emperion fixture reproduces 16 failures before repair:
both seats, direct and snapshot-restored suppression, and gain, loss, damage or
life payment. The shared repair passes a 168-check overlapping selection,
including existing life locks, conversion, AI targeting, ability suppression,
damage replacement and HTTP continuations. No card metadata is altered.

## Expanded Evidence

- The initial clean source gate passes 7,964 tests in all 322 recursively
  discovered test files. Each of four shards matches all 618 frozen source and
  fixture hashes at `2751fbe`; databases are absent at launch.
- Expanded canonical tests include unchanged Scryfall Rampaging Ferocidon and
  Erebos records, with response hashes and retrieval provenance. Against the
  pre-repair runtime the expanded file has 34 failures and four passes. The
  repaired overlapping selection passes 322 checks, including suppression
  expiry, control changes, turn prohibitions and immutable public AI forecasts.
- Two HTTP cases pay Erebos's actual mana/life activation cost after suppression
  and SQLite restoration; the preceding illegal activation preserves complete
  state/database snapshots. The first run mutated a detached test reference
  after rejection restored the authoritative state. Correcting that fixture,
  not changing the engine, makes both cases pass.
- Four browser cases cover both seats, blocked payment under an active printed
  lock and a paid activation after suppression, reload during its stack window,
  priority passes and the resulting draw. No card text is edited or fabricated.
- These supplements are outside the first frozen full gate. Integration with
  published `0000fe6` preserves both sets of browser scenarios and requires a
  fresh combined source gate before promotion. This is not complete Erebos or
  Ferocidon semantics, all conditional life restrictions or arbitrary Oracle support.

## Remaining Acceptance

- Run the full latest-source regression gate in isolated clean source copies.
- Continue conditional prohibitions, characteristic-changing effects and
  context-specific payment prohibitions distinct from losing life.
- Validate public views and human/AI decisions against effective restrictions.
- Keep this candidate separate from the prior frozen resolution-timing gate;
  that gate cannot certify this later replacement-runtime edit.
