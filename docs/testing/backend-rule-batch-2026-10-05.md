# Rules And Human Inspection Batch

## Qualified scope

- Shared affinity reductions across legal moves, payment and actual AI choices.
- Domain consumes effective land types; printed changeling uses the shared type
  layer rather than disappearing when its ability is later suppressed.
- Supported self-sacrifice mana costs, sacrificed-source last-known mana amounts,
  and independent self-death triggers. Intervening-if self-death clauses remain
  explicitly unsupported, rather than becoming unconditional effects.
- Private top-card inspection and zero-hit acknowledgement.
- Bounded revolt destruction and delirium damage alternatives at resolution.
- Persistent simulator row admission quota, preserving existing retry receipts.

No cards or decks were rebalanced. Canonical fixtures preserve source provenance.
Conditional grants, arbitrary Oracle semantics and expert AI remain unfinished.

## Evidence

The full recursive backend suite passes 9,464 tests across 374 modules. Four
initially database-free copies ran independent partitions. The initial first
partition had two outdated Humility/changeling expectations; those failed logs
are retained. After correcting the expectations, the complete first partition
was rerun in another fresh copy and passed 1,752 tests. Other passing partitions
contain 2,465, 2,886 and 2,361 tests. Production code did not change for that rerun.

779 backend source/test/fixture files were checked against the qualification
manifest, with the single documented test correction. The evidence includes
source hashes, all partition logs, correction hashes and accepted result counts.
Earlier overlapping-database exploratory runs are retained but are not counted
as qualification.

Frontend unit tests, lint and production build pass on Vite 6.4.3. Deliberate
dependency migration passed its separate complete browser harness and refreshed
full/runtime npm advisory scans with zero findings; this is not network security
certification. The combined inspection flow passes eight actual HTTP scenarios
and four browser flows after restart/reload. Attack All has its separate 15-case
browser gate and captured-payload engine replay.

Local evidence archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/affinity-batch/`.
The complete combined browser gate subsequently exited 0 with 466 PASS lines,
including restart/recovery, sideboarding and completed AI, human-versus-AI and
human-versus-human BO3 flows. Human BO3 completion uses the documented Island-only
opponent fixture; it verifies application flow, not competitive decision quality.
The backend browser snapshot precedes the final shared mana-value correction;
that correction has its own 188-test affected gate.

The composed delta gate passed 595 tests across fourteen modules: affinity,
domain, changeling, self-sacrifice mana, private inspections, conditional
resolution, job quota, bounded next-combat racing, unknown-library deployment,
Cathar rules/HTTP and AI-hand debugging. This is not a rerun of the full suite
after every subsequent increment. The 7,367-test AI/rules interaction gate and
536-test deployment gate are separately recorded.

The private-inspection harness has a separate HTTP/browser restart gate. Making
it self-isolating from a normal Git checkout and wiring it into CI remains open;
it was not part of the 466-line combined run. Dedicated Cathar browser acceptance,
natural strategic evaluation, training and broad release/security gates remain
unfinished. No professional-AI or arbitrary-card completeness is claimed.
