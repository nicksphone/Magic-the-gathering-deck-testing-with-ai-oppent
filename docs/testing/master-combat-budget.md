# Shared Master Combat Work Allowance

## Reproduced Problem

On the frozen `97f9c309` Drain/Tribal Master comparison, one accepted attack
decision took 102.603 seconds and another took 87.997 seconds. A separate bounded
profile traced multiplying strategic materialization, attack, defense and
next-combat forecasts. Its timings overlap and the profile did not complete;
they are not additive or a measured cache-hit rate.

## Correction

The existing synchronous decision scope now shares one mutable combat allowance
across nested choices: Master 128 attempts, MasterPlus 256. Strong, normal and
casual retain their existing unlimited behavior. These are provisional work
limits, not millisecond guarantees or a demonstrated optimal search depth.

Native attack/block projections and their follow-up forecasts debit before
execution. A successful final debit can still complete. A subsequent denied
attempt marks exhaustion. Empty attack/block declarations are completed choices,
not unknown results. A partial complete-defense search returns unknown and
cannot certify a forced win. Strategic search retains completed, native-checked
incumbents and otherwise uses its existing same-difficulty legal fallback.

Review reproduced two additional gaps before correction: already-blocked setup
forecasts bypassed admission, and rejected board-ineligible leaf queries spent
work unnecessarily. Six added cases first failed, then all 36 focused tests
passed. No new state cache, wall-clock-dependent choice, model, card rule,
payment behavior, action schema or saved-state schema was introduced.

## Executed Qualification

- 21 whole pure modules: **649 passed plus six subtests**, 734.90 seconds, exit 0.
  Native SQL, sockets and subprocesses were denied before project imports.
- Two unchanged whole combat/HTTP modules: **114 passed**, 89.67 seconds, exit 0,
  against a fresh owned local database. Unexpected I/O was empty, source hashes
  matched, and disposal left no database descriptors, jobs or new threads.
- Six independent canonical review cases passed, including last-token completion
  through the corrected declared-block forecast.
- The exact retained slow position selected the same native-checked attack in
  **11.307 seconds**. A hidden-identity/library-order variant selected the same
  action in 11.133 seconds. Root state and RNG remained unchanged. This is one
  retained position, not a universal ninefold performance improvement.
- All 4,330 candidate files matched after execution; 4,326 inherited files retain
  their baseline bytes/modes. The only production changes are the AI agent and
  existing decision-scope module. Restoring the nine owned agent methods, scope
  function and additive helper/import reconstructs both original module ASTs.

The pure and HTTP cohorts are separate runs on identical production bytes, not
a claimed single 763-case run. Historical guard errors, a CPU-interrupted cohort,
the missing audit-output environment, and a cancelled duplicate launch remain
preserved. Their partial results are not relabelled complete passes.

## Same-Budget Master Games

Both mirrored comparisons retain the original canonical 60-card Drain/Tribal
mains, seed `2026110517`, Master difficulty, no learned model, native validation
and per-action hands. Limits remain 600 shared series seconds, 595/600 soft/hard
CPU seconds, 1,200 wall seconds and 6,000 ticks per game. Supplied sideboards are
empty, so these are core comparisons, not sideboarding or API BO3 acceptance.

The first candidate series completed naturally 2-0 in 321.35 CPU seconds,
323.75 wall seconds, with 967 checked/committed actions. The frozen baseline
completed that series in 309.58 CPU seconds: this is not a blanket speedup.

The reverse candidate completed two games, reached 1-1, and hit the original
resource limit during game three: 594.80 CPU seconds, 597.81 wall seconds. Its
winner is unavailable, not a draw or loss. The old reverse ended unfinished with
exit 137; the new bounded result does not retroactively complete it.

## Live Component Delivery

On 2026-11-05, the preview switched from `97f9c309` to `f9b3d123` after a separate
preparation review. All 4,331 installed regular files were attested to Git blobs
and modes. The existing runtime, environment, frontend and database path remained
unchanged. Before starting the new code, the closed 367,837,184-byte database
passed its local integrity check and its protected NFS backup matched bytes.
The database was never restored or overwritten by the delivery script.

The new backend passed health, preserved all 1,254 saved match IDs, restored two
historical GET samples identically, and retained identical sampled images and
all 148 copied cache files. Rollback is restricted to code; old overrides/installations
remain available. No experimental weights or 64-unit override were activated.
This is operational delivery of a tested component, not overall AI acceptance.

## Remaining Work

The allowance implementation has bounded regression evidence, but overall AI
performance/strength acceptance is open. A lower-allowance development comparison
must retain legal choices, tactical behavior and hidden-information boundaries.
The separate 64-unit override retained the same attack in 8.70 seconds but also
hit the original reverse-series limit in game three at 1-1. It was not promoted
to the source default or live app, and it is not an approved learned model.

A follow-up diagnostic observed 79 of 102 materializations beginning after
sticky denial, including all 63 repeated materializations. Instrumented timings
are not production savings. The next scoped correction must stop discarded
speculation while preserving completed incumbents, ordinary legal fallback and
the shared learned-ranking route; those properties remain to be qualified.
General Forge adoption and reliable human-choice replay remain separate,
unfinished work.

Generated hands, traces and SQLite evidence remain in protected project storage,
not public fixtures.
