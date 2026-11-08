# November 8 retention and storage-safety qualification

Both whole unchanged release-storage modules pass on
`0144789fabb1c333e00f5177008fdfe9a25648ba`: 27 ordinary cases in
`backend/tests/release_agent/test_retention.py` and seven in `test_safety.py`.
The single combined command reports 34 passes, zero failures/errors/skips and
five deprecation warnings in 9.51 seconds. This qualifies the storage component;
the earlier full-backend failure, hosted CI and all RC gates remain open.

## Actual operations and bounds

The cohort retains age/keep boundaries, active and malformed-record protection,
incoming foreign-key protection, trigger refusal, lock and commit rollback,
unrelated application-record equality, read-only and network-filesystem refusal,
and refusal to delete from owner-accounted storage. It also retains the original
partial-delete fault and all three original pruning CLI calls. There are no
keyword filters, extra skips, changed assertions or ASGI timer adjustments.

The parent makes 135 real SQLite connections to 34 distinct owned file targets,
with zero memory connections. Three CLI children make one further connection to
one of those same files. All 136 native handles match guarded returns; no
constructor failures or audit/authorizer rejections occur during the cohort.
The direct worker is reaped and its owned process group is absent after normal
exit, closing remaining process-owned handles. Guarded runner time is 9.773
seconds, JUnit time 9.512 seconds and supervisor time 12.002 seconds.

All 5,128 frozen public regular files, including 2,697 backend files, verify
against SHA-256 and actual Git blob IDs. Source, tests, runner/control versions,
JUnit, child records and closure receipts remain bound. The reused Python
environment is not a clean-install qualification. No AI decisions or new natural
games are used; the supported-record fixture constructs its original static
application state.

## Exact test admissions

Read-write SQLite URIs are admitted only for the same owned disposable paths as
ordinary writable connections. All three connect aliases retain the guarded
native entry and install an authorizer after initialization and before returning
a connection. ATTACH/DETACH, extension/file functions and writable directory
pragmas remain denied. Network, nested children, foreign databases and protected
artifact bodies remain forbidden. These bounds cover the inspected code and
SQL primitives; they are not a general filesystem or custom-function sandbox.

One original test intentionally supplies its local `FailingConnection` subclass
to fail the second DELETE. Before construction, admission checks the exact
frozen test frame, local class identity, database fixture, direct native base,
inherited constructor and authorizer, and absence of additional class overrides.
Its `execute` code signature must equal the method compiled from the frozen
source and retain the correct `__class__` closure. Only one such admission is
allowed. The actual test then executes both deletes, receives its original
injected error and verifies that both rows survive rollback. Other factories
remain forbidden.

The CLI gate admits only the three original ordered calls from their exact
test frame: missing required database, read-only dry run on its fixture, and
invalid retention configuration with `--apply`. It checks the interpreter,
module, arguments, fixture path, working directory and inherited bootstrap.
Python user-site startup is disabled before parent and child startup. Every
child installs the guard before importing the CLI, limited to its declared
database path. Child SQL counts are respectively zero, one and zero.

Pytest success alone is insufficient: the runner separately requires three clean
child reports matching its command admissions and exactly one accepted original
fault-factory record. Missing, denied, mismatched or incomplete evidence forces
a nonzero result even where an original CLI assertion expects failure.

## Controls, review and remaining work

Fresh version-bound controls exercise eighteen expected audit denials, five
denied SQL primitives, all three native connect aliases and an actual owned
read-write URI. An unqualified subclass's constructor never executes. Command
metadata controls accept the three exact shapes and reject six altered shapes;
receipt controls reject thirteen missing/faulty child sets and two missing/excess
factory records. These controls are separate from the 34 application cases.
They start no CLI child and do not claim the actual fault-factory positive;
that is supplied by the unchanged cohort itself.

Independent prelaunch review approves the known-source bounds. A subsequent
metadata/source auditor verifies the closed execution without database-body,
protected-artifact or runtime IO. Independent final review approves the result
and documentation without findings. Private
execution packets remain in
`/home/nick/mtg-rc-evidence-20261108/retention-safety-qualification`;
databases and raw logs are not published. The earlier
[restore CLI component](restore-cli-qualification-20261108.md) has its own source
and execution boundary. Neither component retroactively turns the earlier
81-pass full-suite prefix into a successful full-suite run.
