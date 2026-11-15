# November 8 restore CLI qualification

The whole unchanged `backend/tests/release_agent/test_restore.py` module passes
all eleven ordinary tests, with zero failures, errors or skips. This renews the
backup/restore component on `8fecbcbe509817f8982a1ddcc4da64847c604522` and
qualifies the four original restore-only CLI subprocess calls. It does not
complete the full backend suite, clean installation, hosted CI or an RC gate.

## Execution and source boundary

The source packet contains 5,127 Git-tracked public regular files, including
2,697 backend files. SHA-256 and actual Git blob IDs match the commit before
execution and in the final audit. No product, test or CLI assertion changed.
The module runs without a keyword filter, skip, fail-fast option or ASGI timer
adjustment, using the reused Python 3.12 environment. Pytest reports 5.25 seconds
and forty existing deprecation warnings; the complete guarded runner takes
5.568 seconds and its supervisor 6.001 seconds.

The parent observes 28 real SQLite connections to fourteen distinct owned file
targets, with zero memory connections. The four children observe four further
connections to three distinct owned file targets. Parent and child sets overlap;
their file counts are not added as a distinct-file total. All native handles
match guarded returns. After normal completion the direct worker is reaped and
the owned process group is absent, closing its remaining handles.

## Child and database admission

Only the original Python module command is admitted, with `--backup` and
`--restore` paths inside the exact calling test's real `tmp_path`. The original
restore-only test calls it three times, checking a missing backup, successful
restore and destination collision. The corrupt-backup test calls it once.
Argument shape, interpreter, module, test frame, filenames, call counts, current
directory and inherited bootstrap are checked. Nested children are forbidden.

Both parent and children disable Python user-site startup before execution and
check the environment value and interpreter flag. The child bootstrap installs
the same SQLite guard before importing the CLI. Its targets are limited to its
two command paths. All three SQLite connect aliases require the guarded native
entry and install an authorizer after initialization but before returning the
connection. Custom factories, ATTACH/DETACH, extension loading, file functions
and writable directory pragmas are denied. Network operations are denied.
These are bounds for the inspected code and SQL primitives, not a general
filesystem or custom-function sandbox.

The original CLI tests intentionally expect some nonzero exits. Accordingly,
pytest success alone cannot qualify this execution: exactly four child reports
must separately match the parent's admitted command multiset and verify clean
audit/authorizer records, unchanged source, disabled user-site startup, no nested
children or constructor failures, and matching native handles/returns. Missing
or faulty child evidence forces the runner to fail independently of pytest.

Fresh controls bind the exact guard, bootstrap, receipt validator and control
hashes. They exercise seventeen expected audit denials, five denied SQL
primitives, two positive command-coordinate controls and eleven rejected missing
or faulty child-report scenarios. These are separate guard controls, not
additional application test passes or CLI children.

## Retained failures and review

The first cohort epoch reports nine passes and two harness failures, with zero
CLI children admitted. Its matcher expected full function names in temporary
directory names. Installed pytest normalizes and truncates these names to thirty
characters; both CLI function names have thirty-one. The separately declared
second epoch corrects that prefix and additionally binds the actual test-frame
fixture path. Sources, assertions, commands and resource bounds remain unchanged.
The nine earlier passes overlap the final eleven and are not added to them.

Earlier control attempts remain separate: an initial command-prefix negative
did not reach the test-frame check; its stronger replacement initially reused an
owned control database and stopped at an existing-table setup error. A fresh
fixture fixed that setup. Independent prelaunch review then required separate
child-report validation, disabled user-site startup and exact control bindings;
fresh controls exercised those corrections before either cohort launch.

Final source, JUnit, child reports, runner/control pins and process closure verify
without database-body reads, AI calls or new natural games. Independent read-only
final review approves the result and documentation. Its minor verifier timing-label
finding is corrected without rerunning application work; earlier metadata is
retained separately. Private packets are retained under
`/home/nick/mtg-rc-evidence-20261108/restore-cli-qualification` and the separate
`restore-cli-qualification-v2` directory. Disposable databases and raw logs are
not published. The preceding full-suite 81-pass prefix still ends at its original
CLI-child denial; this component result does not turn that execution green.
