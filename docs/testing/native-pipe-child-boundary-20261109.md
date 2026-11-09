# Native pipe and CLI child boundary — November 9, 2026

Status: **full backend failed/incomplete; RC unfinished**.
Source294e4565349f612b47bf4c7a0018ec62c0c33fa6 retains backend tree
95df5186a5c229cfcde8b092afc9c1ec0e24a0ec. No application or original test source,
assertion, ordering, selection, matrix or gameplay-limit change is made. The
[previous pipe rejection](native-sql-loading-boundary-20261109.md) stays retained.
The actual epoch uses the first child mutation guard. Final review finds a gap;
its correction is qualified by inert controls only, as detailed below. The epoch
and its source/pins stay unchanged and do not qualify the corrected mutation gate.

## Actual original full entry

The unfiltered `tests` declaration collects exactly all 36,739 original ordered
nodes: 1,645 passing collection reports and zero deselections.

| Recorded outcome | Count |
| --- | ---: |
| Passing setup | 109 |
| Passing call | 108 |
| Failed call | 1 |
| Passing teardown | 109 |
| Parent SQL requests / handle audit events | 138 / 138 |
| Parent SQL path/URI denials | 1 |
| Original restore CLI children / clean receipts | 4 / 4 |
| Child SQL requests / handle audit events | 4 / 4 |
| Native capture descriptors | 8 |
| Native reference requests | 1,338 |

Both original CLI cases in `tests/release_agent/test_restore.py` pass, including
all three invocations in `test_cli_error_and_restore_only` and the corrupt-backup
invocation. Each child independently has a clean receipt, including expected
nonzero native outcomes. Parent source, native SQL/fingerprint work and every
original assertion stay intact. The three declared prune children in
`test_paths_and_cli_are_explicit_and_dry_by_default` are not reached in this full
entry; their separate inert qualification is described below. Overlapping older
component counts are not added as new coverage.

The failed call is
`tests/release_agent/test_safety.py::test_partial_delete_error_rolls_back_every_row`,
with PermissionError. The first denial is `sqlite3.connect` at the path/URI check;
actor admission has no rejection. Public source shows a fault-factory lambda
forwarding `*a, **k` to a saved constructor while its caller supplies literal
`uri=True`. The current closest-callsite rule does not qualify that forwarding
form. This is a source-based inference for the next controlled reproduction;
actual kwargs, factory closures, SQL statements, failure values and tracebacks
are not inspected. The rollback assertion is unqualified here, and later backend
outcomes remain unknown. URI authority is not expanded after this first failure.

Worker time is30.042933228 seconds; normal owned-process closure takes
33.059621300 seconds. The27,761,840 output bytes remain opaque. The direct child
is reaped, its process group is absent and there is no leftover group, outer stop,
supervisor exception, cleanup termination or retry. Parent limits remain
CPU120/125,inner180/outer210 seconds,4GiB,128MiB,maxfail1. Assertions are active
and plain, with no site/user site, bytecode, plugin autoload or pytest cache.

Native local code events record calls/normal returns: choose_action8/8,
MatchFactory.from_decks189/189, checked_action287/264 and
deserialize_match_snapshot69/69. Return bodies remain unread. These are neither
unique decisions nor playing-strength results. Loader/monitor ownership restores,
global profiling stays unset, unrelated observer callbacks are zero, and the
permanent first-phase template latch remains enforced.

## Native-only pipes, fixtures and command resources

The parent binds actual native Popen/run code identities and their precise source
callsites, the original collected test/root dispatcher, current node/phase/thread
and a continuous caller chain. Only native readonly stdout/stderr wrapping at
Popen.__init__:1016/1021 is admitted. Descriptor checks use fstat, readlink inode
and access-mode metadata; pipe payloads are never read by instrumentation.
Foreign/clone/line/thread/phase callbacks cannot borrow this authority.

Native pytest tmp_path mkdir metadata is authenticated through its actual fixture
and framework code chain. Successful setup binds a single canonical mode0700
directory identity to its node, without reading fixture locals or return values.
Launch checks revalidate that identity and require the exact source call/order,
fixed selectors and owned target basenames for the seven declared commands.
Unknown commands, resources, environments and extra invocations fail closed.
Only declared process selectors and path-resource positions are classified after
actor admission; arbitrary application arguments and environment dictionaries
are not consumed.

Original argv, cwd and env=None behavior remain unchanged. The parent supplies
checked bootstrap environment entries for the original child interpreter.
Native outputs remain for the original native tests to parse; observers and
auditors do not inspect their captured stdout/stderr or database results.

## Parent and child startup are distinct

The parent uses isolated no-site Python3.12.3-I-S-B. Original CLI commands have no
isolation/no-site flags; their receipts explicitly record `isolated=False` and
`no_site=False`, with user site and bytecode disabled. An owned sitecustomize
installs the child gate before target CLI imports. Python normally loads site
configuration before sitecustomize; this is not a general pre-site hook.
[Python's startup documentation](https://docs.python.org/3.12/library/site.html)
describes that order.

This exact public venv configuration is pinned, has
include-system-site-packages=false and has no .pth entries. Parent prelaunch and
child startup verify that inventory, prefix/environment/argv identity and direct
bootstrap pins. Unknown startup entries reject. This narrowly checked startup
does not establish installed dependency integrity or transfer parent isolation
to children. Child CPU30/35,inner30 seconds and4GiB stay within the parent
envelope, and children remain in the owned parent process group.

Child native authority binds SourceLoader-returned CLI/source code and native
runpy module dispatch. SQL is limited to the declared canonical targets and
source URI evidence; private owned reads and writes require native authority.
Sockets, providers, nested children, protected and foreign inputs remain denied.
Each child separately passes14 pre-import denial controls before native work;
those expected controls are retained separately from actual execution denials.

Receipts contain only producer-primitive startup/code/path/SQL-event/denial/closure
metadata. Exact issued declaration/receipt paths have explicit producer schemas;
an owned directory or JSON suffix does not make arbitrary data public. Declarations
and receipts require exclusive mode0600, ordinary single-link owned files.
Missing, duplicate, extra, dirty and incorrectly permissioned receipts reject
independently of the native program's expected exit. SQL handle audit arguments,
statements, rows, constructor return bodies and individual closes stay uninspected.
Process closure proves termination, not per-handle close or post-result atexit.

## Controls and retained development failures

Twenty-three final preflight commands plus the pure terminal audit pass. They include all
earlier phase/unittest/yield-teardown/fault/SQL/URI/template/framework checks,
native pipe integration,23 command/fixture/startup negatives,10 pipe metadata
negatives, child module/resource metadata, receipt faults and child-owned IO.
The Task1-only source bindings remain historical. The final23-command source-bound
suite qualifies the corrected shared helpers; the pure terminal audit separately
verifies the unchanged historical full entry, without transferring its qualification.

Seven actual original restore/prune argv forms and unchanged original CLI
call/assertion function bodies also pass on an explicitly owned inert three-column
literal schema. Only the native subject functions consume those literal fixtures
and outputs; instrumentation sees nine passing phases, seven clean receipts and
five SQL request/handle events. This qualifies the contract, not complete original
prune tests, canonical gameplay data or additional unique application coverage.

Missing authority first denies native pipe wrapping. Native binding then admits
two capture descriptors while a missing bootstrap still rejects launch. An active
observer pipe open remains denied. A broad OSError catch initially records that
PermissionError twice; a RED control and narrowed try/else fix preserve one record
per event. Ambiguous setup initially retains an old fixture binding; its RED/GREEN
control now clears stale ownership before revalidation.

A control-only actor fixture omitted a role field and retains its KeyError class
and opaque audit. Another control assumed a nonexistent scripts/__init__.py;
positive classification rejects it before open, and namespace-package metadata
corrects the fixture without widening admission. Initial child declarations inherit
mode0664 and fail startup before being trusted; explicit exclusive0600 creation
fixes the producer. An inherited `targets` name collision misclassifies SQL paths
as fixture references; metadata RED/GREEN separates those registries. Parent
receipt reads initially reject after native phases; exact issued schema paths
correct that admission. An observer write-only trap creates an empty absent owned
target under the old rule; native-only child IO now denies it before creation,
while all seven native CLI forms still pass. No DB body, including the empty
control artifact, is read/hashed/copied by tooling.

Receipt controls reject28 field/type variants and five invalid receipt sets. An
injected bootstrap fault launches three controlled processes, exits before target
imports and produces three nonclean receipts that all reject. Every development
failure and opaque output remains retained. No original application replay is
spent on delivery or count padding.

Fresh review reports0Critical,1Important and0Minor. Child open/SQL checks use
declared resources and native actors, but the first mutation branches use only
the broad owned directory. The actual epoch does not establish whether a foreign
mutation occurred. The corrected child guard permits only native removal of
declared targets/sidecars through exact source and Path.unlink dispatch, with
absolute canonical paths and no dir_fd override. Child mkdir/rmdir/rename/link/
symlink/chmod/chown/utime/truncate forms have no declared route and reject.

An empty-fixture foreign removal succeeds under the old guard (RED). The corrected
control denies ten foreign mutations and seven metadata variants, with two native
removal/sidecar positives. All seven real inert CLI invocations still pass with
clean receipts, including their native failure cleanup. The full24-check boundary
verification passes. No original full entry is replayed and no second review is
performed; historical mutation enforcement remains unqualified.

## Input scope and original acceptance

The5,209-entry Git binding admits1,818 public bodies:1,745 Python sources and73
resources. Its3,391 excluded bodies stay metadata-bound;960 native-only reference
links retain ordinary-file/link metadata without tooling reads/hashes/copies.
Public bytes and reference metadata verify unchanged. The separately named public
CI sources and exact public interpreter bootstrap configuration are not runtime
catalog or arbitrary-body permissions. The old frame-local/blanket-pinning child
guard is not reused. Earlier snapshot-hashing, direct auditor diagnostics and
historical template-window uncertainty remain nonconforming or unknown history.

Fresh GitHub repository metadata still reports zero forks/network members and
the November7 last push; canonical roadmap issue2 remains open. Earlier branch
reconciliation stays retained, without a private/inaccessible-work completeness
claim or remote mutation.

Next work needs an exact native URI-forwarding/fault-factory proof before another
original full entry. All three RC gates, five-phase AI/data and thirteen expert
styles remain required. Full backend/native/Forge/cold TCP/browser/LAN/TLS/devices,
complete canonical data and actual expert benchmarks, matrix partials/flags,
exact Vite/Caddy inputs, clean install/build/deploy and current hosted CI remain
open. No hidden skip, assertion weakening, matrix replay, reset cap, broad pinner,
hostile-code/race/descriptor-bypass certificate or private-body inspection follows.

Evidence: `/home/nick/mtg-rc-evidence-20261108/native-pipe-child-work`; terminal
epoch: sibling `native-pipe-child-v1`. One fresh review and exact public local
patch exports are bound separately.
