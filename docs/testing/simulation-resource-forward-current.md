# Forward Simulation Resource Limits

Checkpoint: 2026-10-08. Published rules baseline `ce97fe1` plus the finalized
Stage1 limits and separate request-HTTP413 correction passed one unchanged
26-whole-module union: **591 passes, 2 warnings, 504.66 seconds**, exit 0.
All 591 ordered identities match the previous run; no skips, deselections or
expected failures. The current parent matches all 1,627 protected backend/audit
inputs in that tested source. Later frontend-only changes do not alter them.

The initial union was 588 passes / 3 failures, 621.26 seconds. All three unchanged
lifespan tests stopped at the runner's denial of asyncio's native local self-pipe,
before executing their actual lifespan bodies. That ledger remains immutable.
The separate corrected runner allows only the proven AF_UNIX event-loop
constructor, not arbitrary pairs or network use. Eleven native negatives and a
genuine closed self-pipe positive pass; application denials are empty. SQL,
children and external networking remain denied. Complete FD/thread/direct-child
closure and owned imports pass; the default database stays absent.

All 2,454 source inputs remain byte-equal before/after. The sole generated output
is the real generic token SVG, with the previously qualified exact SHA256. This
is explicit generated-media evidence, not literal zero-files-written isolation.

The increment implements the fixed limits in
`docs/release/STAGE1_RESOURCE_LIMITS.md`. Oversized NEW request JSON returns fixed
HTTP413 before admission changes; prior replay/conflict and shutdown503 ordering
remain. Repository encoding preflight occurs before Session operations and uses
the original checked serialization. Trace/candidate logs and final producer
results are bounded; cooperative deadline failures are honest failures, never
truncated successes or forced game outcomes.

Native canonical 60-Island/60-Plains workloads retain their unchanged 500-tick
cap and natural timeout outcomes. Real Session persistence was spied in these
checks: this is not actual SQLite durability, naturally completed games, AI
strength, exclusive RAM or performance-cause certification.

Evidence: `parent-integration/resource-stage1-ce97-20261008/strongguard-591-terminal/`
and `parent-integration/pure-whole591-corrected-3hMEF9/` under the mounted MTG
archive. Exact Stage1 and HTTP413 donor preimages/manifests are retained separately.

Still required: actual writer/background/cold-restart SQLite qualification,
synchronous resource-error translation and drain, aggregate escrow/quota/retention
and crash/soak gates, hard-allocation/preemption limits and original full-release
requirements. No live server, user database or schema was changed by this gate.
