# Backend Test Discovery Fixtures

Several backend regressions reuse the committed Brainstorm, Suncleanser,
Suncleanser ABI and domain-paid audit fixtures. Backend `tests/conftest.py` now
resolves those four exact directories. This does not collect their audit cohorts
or the separate opt-in Spree HTTP tests. Production import paths are unchanged.

## Executed Collection

An isolated source copy of `664290a4e4ffb376631442e52f43357b0840f06c`
plus this test-setup change collected the whole backend test directory:
**23,178 nodes, zero collection errors, pytest and wrapper exit zero**.
Pytest reported 67.54 seconds; the runner body including receipts took 71.56
seconds. Zero test phases executed. No nodes were filtered or deselected.

SQL/socket/subprocess native denial was installed before pytest/application
imports. All three SQLite aliases, a socket constructor and Popen were denied
by five controls; no unexpected application denial occurred. Source hashes,
MainThread closure and absent default database were independently checked.

The runner declared `MTG_ISOLATED_TEST_ROOT` to its source-only, no-Git copy and
`ADMISSION_PHASE=backend-collection`. The shipped generic SVG was byte-copied
into the disposable cache before freezing source pins. This is explicitly
prepared collection input, not execution of fresh media bootstrap. No game,
HTTP, SQLite, browser or full test-suite pass is claimed.

The initial setup run collected 23,150 nodes with one missing `test_paid_modal`
import. Its unchanged comparison-runner assertion also rejected the now-intended
audit helper imports. That complete ledger remains preserved. Adding the fourth
exact fixture directory and correcting the collector's expected import inventory
produced the subsequent complete collection; no test assertions changed.

Earlier baseline and opt-in Spree delivery collections both retained exactly
13,141 ordered nodes and the same 236 normalized errors. That comparison proves
no incremental delivery-discovery change under its restrictive configuration,
not a green default suite. Its failures and source manifests remain immutable.

Verified NFS evidence:
`parent-integration/backend-default-discovery-fixture-fix-20261008-b47FhK/` and
`parent-integration/spree-optin-default-collection-comparison-20261008-6Y1IoI/`.
The retained/live database was never opened or modified. Actual gameplay testing
still requires its reviewed isolated SQL, media, process and evidence contracts.
