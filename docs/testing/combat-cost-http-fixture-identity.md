# Combat-Cost HTTP Fixture Identity

This test-only repair was qualified from immutable `f102874f` in an isolated
source checkout. It changes five HTTP setup functions in these four modules:

- `test_combat_domain_temporary_costs.py`
- `test_conditional_combat_costs.py`
- `test_recipient_combat.py`
- `test_combat_minimums_payments.py`

The fixtures previously replaced a Factory-born state's ID after its private
stock facts had captured the genuine birth ID. Snapshot serialization correctly
rejected that mismatch before the intended combat/payment assertions ran.

The repaired setups use the existing trusted `adopt_fixture_state` helper. It
validates the incoming state, retains its genuine ID and captured stock facts,
and moves the explicit HTTP controller/registry/persistence binding. No facts
are cleared or rewritten, and no production validator or shared helper changes.

## Measured Whole-Module Results

Both runs used the same 159 original node identities and order, without filters,
skips, retries or assertion changes:

- Baseline: 143 passed, 16 failed, zero errors/skips; 95.38 seconds, 82 warnings.
- Candidate: 159 passed, zero failures/errors/skips; 106.38 seconds, 98 warnings.

All 169 original assertion ASTs and the other 51 functions/classes are unchanged.
The original action, paid-cost, atomic-rejection, diagnostics, full snapshot and
SQLite restore checks remain authoritative. Default fixtures, canonical cards,
Factory behavior, RNG, gameplay rules, AI policy and runtime packages are unchanged.

## Resource And Scope Boundary

The existing physical guard was reused with only finite root/roster/count/output
metadata changes: 900 seconds work plus 15 seconds cleanup, private network/IPC,
read-only host/runtime and explicitly owned writable paths. Its native SQL
admission predicates were unchanged. These tests use in-process HTTP clients,
not an independently qualified browser or network listener.

Candidate source/runtime/input pins matched before and after execution. All 112
observed native SQL handles closed; jobs, new threads and owned descriptors were
quiet. Both known PIDs were absent, and external fuser checks were empty for all
18 remaining SQL/backup/lock files and the owner directories. The fixture SQL
lease was released after those checks.

This qualifies only the declared four-module fixture correction. It is not a
whole-CI, browser/TLS, all-combat-mechanics, AI-strength or benchmark completion
claim. The failed baseline remains separate evidence.
