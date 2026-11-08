# Optional archive collection boundary

The optional saved-decision cases in `test_ai_opaque_top_choose_horizon.py`
previously evaluated `not NATURAL.exists()` while importing their module. An
unreadable mounted archive raised `PermissionError(13)` during collection,
preventing unrelated public tests from collecting.

The same condition is now a lazy pytest expression, evaluated when each archived
case enters setup. The archive path, original skip reason, parameterization and
entire test body are unchanged. An absent archive retains its existing explicit
skip, an available archive admits the case, and a permission error remains a
visible setup error. No permission error is converted into absence, no new skip
or xfail is introduced, and no archive permission or assertion is bypassed.
Availability is checked later, so changes between collection and setup are also
observed at setup. Production backend and audit code remain exactly `cc29147b`.

## Regression and affected-module execution

Four metadata controls execute the actual module and pytest's actual condition
evaluator using synthetic archive metadata. They verify module import without
an archive probe and the absent/available/unreadable outcomes. Unchanged source
reports three failures and one pass; the correction passes all four in 0.93
seconds, with all 2,697 bound backend files unchanged and no SQL, socket, child or
archive-body operation. The controls do not execute the archived test body.

A two-whole-module command, with declared `--maxfail=1`, then reports **106
passes and one setup error** in 11.79 seconds. The passes include the four new
controls and 102 existing public opaque-selection/agent fixture cases. These
are separate from natural gameplay or strength acceptance. The first archived
variant, `Aggro-1-433`, retains the real mounted-path `PermissionError` during
skip-condition evaluation. There are no skips, call failures or hidden xfails;
the remaining archived variants are unexecuted after fail-fast. This is an
incomplete affected-module result, not an archive or full-suite pass.

## Full backend entry and explicit IO boundaries

Full backend discovery is attempted without module or keyword filters, retaining
`--maxfail=1`. With strict preimport SQL/socket/child denial, it now completes
collection and runs 72 passing cases before
`tests/regression_agent_wave2/test_restart_and_additional.py::test_pending_modal_discard_choice_survives_sqlite_restart`
fails at the declared SQLite boundary. This is a harness restriction rather than
an identified production regression. The original collection failure and this
later failure remain separate retained epochs.

A fresh full-entry epoch allows only disposable bootstrap/pytest database targets
and literal process-local memory, with the existing test-loop timer. Its SQLite
return guard follows the existing built-browser server pattern: all three connect
aliases install an authorizer after native initialization and before return;
direct native constructors, custom factories and foreign targets are denied.
ATTACH/DETACH, extension/file functions and directory-changing pragmas are denied.
This is a bounded known-source qualification guard, not a general filesystem or
custom-function sandbox. Custom-factory tests would encounter another declared
boundary if reached.

The actual extracted guard passes normal operations on three memory connections
and one owned file connection. Five SQL primitive attempts and six native-entry,
factory, URI or foreign-target attempts are rejected; foreign files are not
created and all four control connections close. Earlier canary failures are
retained: installing an authorizer at the premature native-handle event raises
`ProgrammingError`; the next fixture's uncommitted transaction prevents VACUUM
from reaching the intended authorization check. Corrected controls commit first
and require authorization-specific errors. A later scope-label-only edit has
identical guard-function ASTs and does not rerun the canaries.

This owned-SQL full-entry epoch reports **81 passes and one failure**, with 28
warnings, in 70.31 seconds. It reaches
`tests/release_agent/test_restore.py::test_cli_error_and_restore_only`, where the
all-children-forbidden policy denies `subprocess.Popen` before a CLI child starts.
Twenty-five SQLite connections use eleven distinct owned file targets; all 25
native handles have authorized returns, with no constructor failure or SQL
primitive denial. No ASGI loop is instantiated in this executed prefix, so the
installed timer supplies no new HTTP qualification. Later tests are unexecuted;
this result does not identify every remaining full-suite failure.

The executed test sets overlap; their passing counts must not be added into
a unique-test total. Dependencies are reused. All 5,126 frozen public source
inputs remain unchanged across the three supervised epochs. Each worker exits
nonzero for its recorded failure, is reaped normally and leaves no process group,
without an outer timeout or forced cleanup. Original test assertions and declared
runtime guards are retained throughout. No real archive body is opened.

Independent read-only review accepts the source, tests and bounded evidence
for commit/export with no blocker. Parent verification proves
the one-condition AST change, unchanged production code, JUnit outcomes, source
and guard pins, observed SQL targets and physical process closure without more
application or private-payload reads. Evidence remains private under
`/home/nick/mtg-rc-evidence-20261108/optional-archive-collection/`.
The original matrix keeps its frozen source, roster and limits. Original release
and AI/data gates remain open; hosted current-head CI is still required.
