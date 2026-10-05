# Printed Life Locks and Ability Suppression

Status: unpublished integration candidate. Latest optimized-source qualification
is running; the preceding combined source passed its full gate.

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

## Integration and Query Performance

The combined `38888f1` source preserves published life-conversion scenarios and
passes 7,988 backend tests in all 323 test files with 623 source/fixture hashes
verified per shard. Frontend tests, lint, build and the complete browser harness
pass, including all three natural BO3 controller modes and four life-lock cases.
This gate does not certify the subsequent performance edit.

Review found unnecessary global ability-layer scans for battlefield cards whose
printed text cannot impose the queried life restriction. The shared iterator now
accepts an optional text prefilter; relevant sources still undergo the same
suppression and ordering checks. Other callers retain the default behavior.
Three structural regressions fail before this optimization and pass afterward;
207 overlapping checks pass, including relevant-source suppression and HTTP
recovery. A synthetic 32-permanent, 200-query measurement fell from 0.383 seconds
to 0.00619 seconds (about 62 times faster for this query workload). This is not
a whole-game speed or AI-strength measurement. Source records were unchanged.

The latest optimized source is frozen independently for full backend/browser
qualification. Promotion remains withheld until that source passes; do not
substitute the preceding combined gate for current-source evidence.

## Remaining Acceptance

- Run the full latest-source regression gate in isolated clean source copies.
- Continue conditional prohibitions, characteristic-changing effects and
  context-specific payment prohibitions distinct from losing life.
- Validate public views and human/AI decisions against effective restrictions.
- Keep this candidate separate from the prior frozen resolution-timing gate;
  that gate cannot certify this later replacement-runtime edit.
