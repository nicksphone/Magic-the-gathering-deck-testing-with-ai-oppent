# Current Backend CI Terminal

Published source: `1a8e086964039605a8663a5f4e51d3e3902ffe14`.
Run `38095963507`, job `114341798370`, completed with failure on
`2026-10-11T03:06:33Z`. Frontend and browser jobs retain their separate passes.

## Complete Sanitized Metadata

All 25,682 collected node identities have complete phases, with no duplicate or
missing phases, unexpected nodes, collection errors or metadata-export errors.
The pytest exit code is 1. Test bodies: 24,733 passed / 327 failed. Setup:
540 failed / 82 skipped. Skipped checks are not passes, and these phase counts are
not 867 independent bugs. All failed definitions resolve to committed public
tests; reasons and private parameters are deliberately not exported.

Artifact `11689968766`, `backend-metadata.json`, SHA256:
`e13555df0c17b4bfa18c733ec872b56c1a61af9d8042869fb89c5ecbf601fa1d`.
Only that uploaded allowlisted metadata was downloaded. The protected synthetic
trace and raw private CI logs remain unpublished and were not downloaded.
Verified evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ci/current-1a8-backend-terminal-metadata-20261011-9q6IoDuL/`.

## Verified Legacy Retention Fixture Repair

An isolated source-only checkout with the existing exact declared package
versions reproduces 20 failed / 12 passed in the two retention/safety modules.
The legacy-pruning fixtures created the current owner-accounting tables, so
the production safeguard correctly refused unowned deletion. Removing that
safeguard to satisfy legacy fixtures would be incorrect.

Only two test files change. The legacy fixture explicitly excludes the two
accounting tables; the all-records fixture verifies those tables are empty
before removing them for its legacy-only scenario. All original assertions are
retained. Two additional checks require byte-identical refusal when either
accounting table is present. Production pruning, accounting and restore helpers
are unchanged.

The repaired pair passes 34 checks in 17.37s. The whole release-agent suite plus
resource-capacity and resource-budget modules passes 119 checks in 9.88s, with no
failures, errors or skips. These are separate local component runs, not a new
whole hosted-CI result or current-source release certificate.

## Verified Compiler Trace Fixture Repair

The complete trigger-instruction audit reproduces 18 failed / 18 passed; the
creature-observer audit reproduces 12 failed / 44 passed. Both test-only tracing
wrappers reject the compiler's new keyword-only `raw_entry_oracle` input. This
breaks the observation hook before the unchanged gameplay assertions execute.

Each wrapper now accepts and forwards that exact input, including its existing
default. No production compiler, matcher, event, raw Oracle data or test
assertion changes. All original trace collection remains in place. The original
36-case instruction module passes after repair. The six whole affected compiler,
observer and HTTP modules pass 201 checks in 103.77s, with no failures, errors or
skips. This closes those local fixture regressions, not the entire remote suite.

## Verified Stack And Land Fixture Repairs

Legacy stack-copy and hand-activation fixtures now explicitly declare their
original spell/activated/triggered kind. All 195 original assertions remain.
Production ability-copy and ability-counter handlers additionally refuse
`legacy_unknown` objects rather than treating absence of provenance as an
ability. Fifteen new guard cases and the complete affected 304-case cohort pass
in 112.18s. Source zone is not used as a fallback for missing object kind.

The land-intent scenario explicitly repositions its synthetic scheduler using
the existing guarded fixture helper. All 35 original assertions remain; native
scheduler restore is unchanged and still rejects an invalid phase cursor.
Both whole land modules plus the scheduler-helper guards pass 142 cases in
221.99s. This is not closure of the 540 shared hosted setup failures.

The neighboring priority/counter/payment cohort passes 289 cases in 67.33s.
Three manual spell fixtures declare their original kind. The existing land
rejection runs before spell-only timing admission; unknown nonland types still
fail closed. A test-only cold-restart worker accepts the runner's explicitly
declared, canonical same-owner temporary directory instead of incorrectly
requiring all pytest databases to live inside the source directory. Foreign,
relative and symlink paths still reject. The twenty new regressions also pass
after their separately checked repository placement, with SQL and sockets
denied before collection. All original assertions remain.

## Privacy-Safe Failure Locations

The CI observer records a fixed builtin exception category and at most eight
project frame locations. The exporter admits only paths present in the public
commit, matching full source hashes and valid integer line numbers. It emits no
exception messages, dynamic exception names, parameters, locals, source lines,
private paths or game payloads. Raw failure logs and the protected trace remain
private. All 124 script tests pass in 14.045s, including genuine synthetic
pytest setup/call failures and a custom exception with a sentinel name/message.
Optional write failures cannot disable the mandatory ledger; invalid, null or
ambiguous signatures degrade only diagnostic status, not complete phase
accounting. Original coverage accounting and private-log protections remain
unchanged. Earlier reviewer-found diagnostic bugs and their failing regressions
are preserved in separate evidence, not relabeled as successful runs.

## Remaining Qualification

The full protected backend CI must pass on the final combined source. The shared
540 setup failures have not reproduced in the isolated modules; their cause is
still unknown. The safe diagnostic is intended to identify it, not to relabel
failures or broaden permissions. Additional call failures, strategic AI,
arbitrary-card semantics, deployment and all unproved original release
requirements remain open. These scoped local gates are not a summed whole-suite
result. No safety gate, assertion, hidden input or quality requirement is weakened.
