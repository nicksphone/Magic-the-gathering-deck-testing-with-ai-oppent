# Terminal HTTP Fixture Evidence

Five module-scoped HTTP fixtures now reclaim only their explicitly owned runtime
and data roots after normal process termination and verified private archiving.
The helper checks closure, captures every file and empty directory, verifies
archive membership/bytes, and repins original file identities before deletion.
It does not clean up during a restart. Unknown/live/forced process status,
links, archive mutation or incomplete closure fail closed and retain originals.

The four cold fixtures verify actual zero-owner/zero-checkout closure receipts.
The legacy fixture has process-reaped proof only; it is not relabeled as native
capacity closure. Private raw traces and compressed runtime archives stay outside
the public CI metadata upload. No protected game trace is committed.

Startup with no process records `stopped=False`, retains roots and propagates
the original startup error. All five callers honor explicit `MTG_CI_EVIDENCE`;
without it, the new archive destination is the fixture-owned pytest basetemp's
`closed-http-evidence` directory, outside the deleted roots. Preexisting HTTP
stage-environment requirements remain unchanged.

## Qualification

The worker's five whole real HTTP modules execute 78 cases:
70 PASS, 8 original call FAIL, no ERROR/SKIP, 512.37 seconds, exit 1. All five
closed archives verify; four retain 100 actual cold shutdown receipts. The
eight failures are legacy first-restart SQL-hash assertions, not teardown failures.
An independently executed unchanged `a3694abc` 16-case baseline also records
8 PASS / 8 identical call FAIL, 42.46 seconds. Raw SQL and epoch-only operand
proofs remain private. A rotated capacity owner epoch is observed, not erased
from the legacy assertion or represented as whole-suite success.

A separate reviewed follow-up now keeps that raw hash while explicitly proving
the legitimate owner-epoch transition at restart. Its final parent current-source
two-whole-module cohort passes 20 cases, including the original 16 and both
authorization/404 cases. Default same-epoch comparisons remain raw and strict.
The original 78-case failure and unchanged 8/8 baseline above remain historical;
neither is rewritten as a pass. See `legacy-restart-epoch-current.md` for the
exact comparison changes, 113 pure controls and process-only closure limits.

The startup/local-env follow-up passes 21 pure checks in 1.30 seconds after two
expected regressions. Independent parent execution of both whole pure modules
passes 21 in 1.01 seconds, with SQL, sockets and subprocess launch denied before
collection. The new caller controls compile actual fixture function bodies into
explicit inert public fake environments and invoke the real archive helper.
They do not claim actual native startup or replace the 78-case HTTP ledger.

The lifecycle slice preserves all 129 original assertion ASTs, original test
bodies and server methods. The separate restart follow-up explicitly maps only
its declared comparisons and adds stronger pair proofs. The production engine,
ownership/capacity guards, CI reporter and
public upload allowlist are untouched. Independent bounded lifecycle review
clears the original helper/finalizers; the separate caller follow-up adds strict
startup and environment regressions. No hosted ENOSPC causal or full RC claim.
