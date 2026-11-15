# Native SQL loading boundary — November 9, 2026

Status: **full backend failed/incomplete; RC unfinished**.
Source65cfeae1f55ad25d8eda9383b599a32166c251cf keeps backend tree
95df5186a5c229cfcde8b092afc9c1ec0e24a0ec. Application and original test source,
assertions and ordering remain unchanged. The [previous attempt](native-backend-execution-boundary-20261109.md)
and its historical template-window limitation remain retained.

## Native loading contract

A new real inert SQLModel control creates its own public literal row, disposes
the writer and loads through a fresh engine and Session.get. Under the previous
gate it reproduces PermissionError at native
`sqlalchemy.orm.loading.load_on_pk_identity`, definition line527, after one
authorized writer request/event. Adding only that exact native source file to
the SourceLoader code-identity registry makes the restart pass. The registry now
has twelve declared SQL adapter files; no package-prefix permission is added.

Both the direct and full-guard controls pass all three phases with two authorized
SQL requests/handle audit events, three observer denials and nine metadata routes.
Those routes include exact native loading, clone, foreign-frame, source-line,
dispatcher, thread, inactive/closed-phase and three protected/unowned/URI-path
predicates. Native source asserts its own public inert row; tooling receives only
primitive control metadata and never reads statements, rows or handles.

The permanent first-phase template latch remains intact. Existing URI, lifecycle,
teardown-fault, framework and generated-code controls pass too. Thirteen preflight
checks use exclusively retained opaque stdout/stderr, and a pure terminal audit
makes fourteen total boundary audits. No original application replay is used for
delivery or to pad coverage.

## New original full attempt

The unfiltered `tests` declaration collects exactly all 36,739 original nodes in
their prior order: 1,645 passing collection reports and zero deselections.

| Recorded outcome | Count |
| --- | ---: |
| Passing setup | 78 |
| Passing call | 77 |
| Failed call | 1 |
| Passing teardown | 78 |
| Authorized SQL requests / handle audit events | 25 / 25 |
| SQL denials | 0 |
| Native reference requests | 1,305 |

The formerly rejected
`tests/regression_agent_wave2/test_restart_and_additional.py::test_pending_modal_discard_choice_survives_sqlite_restart`
now passes under its unchanged native assertions. These are original test
outcomes, not new unique gameplay or expert-strength coverage.

The new failed call is
`tests/release_agent/test_restore.py::test_cli_error_and_restore_only`, with
PermissionError. Its first denial is an `open` event for a descriptor whose
readlink metadata is `pipe:[120522167]`. The current guard resolves that pseudo
name under `source/backend` and rejects it as a source-file input. Public native
subprocess source wraps captured pipes before the process-launch audit; this
explains the next missing descriptor contract. No launch audit is reached in
the retained entry, and the guard still denies every child launch. No pipe or
child output content is inspected by tooling. Descriptor/child authority is not
expanded after this failure; later backend outcomes remain unknown.

The worker reports18.804419995 seconds; normal process closure takes
22.015662368 seconds. Its22,768,649 output bytes remain opaque. The direct child
is reaped and its owned process group is absent, with no leftover group, outer
stop, supervisor exception or cleanup termination. Limits remain CPU120/125,
inner180/outer210 seconds,4GiB,128MiB,retries0,maxfail1; plain assertions remain
active, with no site/user site, plugin autoload, bytecode or pytest cache.

Local code events record calls/normal returns: choose_action8/8,
MatchFactory.from_decks186/186, checked_action287/264 and
deserialize_match_snapshot69/69. No return body is read. These counts establish
neither unique decision counts nor playing strength. Loader/monitor ownership
restores, global profiling stays unset and unrelated observer callbacks are zero.
The first-phase template latch is true and binding is disabled after closure;
the corrected gate now has execution evidence on this entry. Earlier epoch
source/pins remain untouched and are not retroactively qualified.

## Input and proof limits

The5,206-entry Git binding admits only1,818 public bodies:1,745 Python sources
and73 public resources. Its3,388 excluded bodies stay metadata-bound;960 native
reference leaves link original inputs without tooling reads/hashes/copies.
Admitted public bytes and reference stat/readlink metadata verify unchanged.
Five separately named public CI source/config files are source-only intake,
outside the runtime catalog; their original evidence observers are not executed.

SQL resource checks precede usable construction, while handle audit arguments
stay unread. Request/event counts establish neither constructor returns nor
individual closes. Native tests alone consume their fixtures and generated
databases; tooling does not inspect state/snapshot/action/decision/trace/model/
profile/owner/database bodies, actual failure values/tracebacks or opaque logs/XML.
Controlled source identity is not installed dependency integrity or hostile-code,
race or descriptor-bypass containment. Final result receipts precede interpreter
shutdown and do not certify every later atexit callback.

Earlier actual snapshot-pinning breaches and direct auditor-diagnostic violations
remain nonconforming history. The previous native execution's between-phase
template window remains unknown; this new gate does not erase that limitation.

## Original goal and next work

Fresh GitHub repository metadata reports zero forks/network members. A
fork-inclusive repository-name search returns only upstream. The earlier88-branch
reconciliation stays retained; these reads do not establish inaccessible/private
work completeness. No remote mutation occurs.

Next work needs an exact native pipe/child contract with inert pre-body observer
and resource controls, followed by original full acceptance. All three RC gates,
five-phase AI/data work and thirteen expert styles remain required. Full backend,
native/Forge, cold TCP, browser/LAN/TLS/devices, complete canonical data and actual
expert benchmarks, matrix partials/flags, exact Vite/Caddy prerequisites, clean
install/build/deploy and current hosted CI remain open. No hidden skips, assertion
weakening, matrix replay, reset caps or archived broad pinners are authorized.

External evidence: `/home/nick/mtg-rc-evidence-20261108/native-sql-loading-work`;
terminal epoch: sibling `native-sql-loading-v1`. One fresh final review and exact
public local patch exports are bound separately.
