# Native HTTP wake-up prerequisite — November 9, 2026

Status: **native HTTP/backend acceptance blocked; RC unfinished**. Application
and original test source remain unchanged at backend tree
95df5186a5c229cfcde8b092afc9c1ec0e24a0ec, base
e4bb1095514a0538e5c20e59adf7693226e6997e. This checkpoint diagnoses the
[previous HTTP socket-guard setup failure](native-fault-uri-boundary-20261109.md).
It does not execute a new original backend entry. The latest original entry
remains36,739 ordered collected nodes,170 passing calls, one HTTP setup error,
171 passing teardowns and seven clean original restore/prune children.

## Independent native prerequisite

A separately owned inert subject creates an AF_UNIX/SOCK_STREAM/protocol0 pair
and attempts to send its own one-byte literal. The send raises PermissionError
without any guard, monitor, application import or received-payload inspection.
The subject makes two close calls on its own endpoints. It exits1; normal owned
closure takes1.000908483 seconds, reaps the direct child and confirms group absence.
No syscall error value, socket field, descriptor, received buffer or actual
application/request/response body is inspected by tooling.

Plain Starlette TestClient, an explicit literal-ASGI TestClient and a plain AnyIO
portal also fail to complete under inner25/outer40-second control limits. The
portal enters, then stalls on its first own-literal cross-thread call. All three
have normal exit1 owned-group closure at approximately26seconds. These are
separate inert controls, without the proposed guard or monitor; none counts as a
passing HTTP assertion or additional original coverage.

Installed package directory metadata identifies Starlette1.3.1, AnyIO4.16.0,
HTTPX0.27.2 and FastAPI0.142.2. No dependency is upgraded or replaced on the basis
of this diagnosis. The observed native send denial remains a prerequisite,
independent of any further library or application defect.

The local Python3.12 source shows `_write_to_self` sending a zero byte and catching
OSError. The [CPython3.12.3 source](https://github.com/python/cpython/blob/v3.12.3/Lib/asyncio/selector_events.py#L141)
has the same native mechanism. Combined with the independent send denial and
plain portal stall, this is a source-supported explanation for the missing
cross-thread wake-up; it does not prove that every later HTTP behavior would
work. No timer, syscall, transport or larger-timeout substitute qualifies native
HTTP or release acceptance. Failed native IPC is not replayed for delivery.

## Guard gap and bounded prototype

The old fence rejects the public Python socket constructor, but the native
`_socket.socketpair` entry returns two endpoints without constructor audit events.
An inert foreign-entry test demonstrates that gap, closes its own endpoints and
fails RED. The current fence wraps that module entry before creation; the same
control now denies it with one guard record and no returned endpoint.

A bounded HTTP prototype authenticates the actual Thread.start -> AnyIO portal
producer -> contextlib -> TestClient.__enter__ -> original native test/fixture
root. It uses the original phase/thread and continuous source/callsite authority.
Only the exact native portal-worker/bootstrap chain can redeem its pending launch
lease. Source pins cover11 explicitly classified native Python files; bindings
use exact public function CodeTypes, including preloaded native functions. Original
project roots retain their SourceLoader-returned code bindings.

Socket admission additionally requires the exact asyncio self-pipe construction
chain and the authenticated worker startup. It permits one typed native UNIX pair
request, two native public bare-new delegations and two constructor audit events,
with exact ordering and source lines. Family/type/protocol selectors are classified
only after actor admission. The socket-object audit argument remains unread.
Foreign callbacks, clones, wrong lines/roots/phases/threads, extra requests and
selector variants reject. DNS, bind/connect/listen, remote sockets, providers and
nested processes gain no allowance.

The pre-review guarded inert prototype reaches one authenticated parent launch/worker entry,
one pair request and two wrapper constructor audit events. Its loop records ten
ticks, two portal-call function entries and three wake-up attempts, but does not
complete startup before the inner limit. Three supervised development controls
retain this failure; each exits1 and closes its owned group at approximately26
seconds. Native worker return and monitor cleanup are unproved after inner exit;
the last primitive retains one worker lease and an active monitor. Process-group
termination does not establish per-resource closes or successful Python cleanup.

These prototype runs were not captured in a prelaunch hash-pinned epoch. Their
authored source provenance, primitive metadata and closure receipts are retained;
current source pins do not retroactively certify their exact execution bytes.
The prototype is not wired into the original whole-backend worker/preparer and
is not qualified for original HTTP execution. A new native environment must first
pass the wake-up prerequisite, then support a properly pinned full inert HTTP
control and original unmodified backend acceptance.

The ordinary immutable-source/trusted-instrumentation premise remains explicit.
Pre-guard captured raw C aliases, hostile rebinding/source races, receipt forgery,
descriptor reuse and OS sandbox completeness are not certified. No live Thread
target, closure payload, frame locals/globals, actual function arguments/returns,
SQL handle/result or actual private body is inspected.

## Current checks and retained failures

Twenty-nine pre-review preflight commands pass; after the one review fix pass,
all31 current preflight commands pass. They include19 HTTP code/lease/
selector metadata negatives, one parent-worker/pair metadata positive, two wrapper
metadata positives and the actual foreign native-pair RED/GREEN. All inherited
phase/fixture/unittest/teardown/fault, owned-body/SQL/URI/template/loading/framework,
pipe/command, seven inert CLI, bootstrap/receipt and child-mutation controls pass.
Two additional pure lifecycle/supervisor scripts reproduce the reviewed defects
RED and pass GREEN; the pure source/prerequisite/closure auditor passes separately. These checks verify
bounded contracts and evidence; the native wake-up prerequisite and HTTP assertion
remain failed/unqualified.

The initial native constructor guard hides native audit events. Selected local
PY_START metadata on its own shim identifies the native source chain without
reading arguments. An actual audit later reports socket.__init__:233 rather than
the initially inferred232; the metadata control fails RED before that line is
corrected. Missing-policy and foreign-pair RED receipts remain retained.

The first foreign-pair control tries to publish its receipt path after fence
installation; that bookkeeping write fails. The corrected producer issues the
exact owned primitive path before installing the fence. Another initial HTTP
control runner lacks an owned deadline/group supervisor and stalls. Its tool
session ends130 after interruption; separate historical group absence is unknown.
An attempted capture-descriptor ownership lookup finds no match and signals no
process. Subsequent controls use their own explicit process groups, CPU20/25,
inner25/outer40seconds,4GiB and16MiB captured-stream cap. All seven supervised
control groups have terminal reap/absence receipts; outputs and timeout traces
remain opaque. No historical failure or cleanup uncertainty is erased.

The original backend limits remain CPU120/125,inner180/outer210seconds,4GiB,
128MiB,retries0,maxfail1, with parent-I-S-B/plain assertions/no autoload/no cache.
Original child argv and ordinary startup remain distinct from parent isolation.
No application test, assertion, order, fixture body, matrix or gameplay limit is
changed; no original full entry is spent on an independently failed prerequisite.

## Inputs, review and remaining scope

Current pure intake verifies1,745 classified Python sources plus73 public
resources. All960 original reference bodies remain excluded and metadata-only.
The5,215-entry base has3,397 excluded Git rows bound as metadata; no new source
projection/reference-link epoch is prepared. Native11-source pins are separately
classified public library source, not an expansion of the runtime body catalog.
Actual state/snapshot/hand/move/action/decision/trace/card-result, owner-lock,
model/feature, bundle/profile, SQL, native output and failed-stream bodies remain
outside tooling inspection. Earlier privacy, mutation, template, observer and
diagnostic violations remain retained; no global privacy certificate follows.

Fresh Astra-high review reports0Critical,3Important and0Minor, checking95 package
pins,52 public tool sources,11 native sources, the separate public cleanup helper,
29 bound preflight rows and seven producer closure receipts. All22 declined items
are explicitly ruled on in the retained ledger. Author1818/960 proofs remain
distinct from the reviewer's package audit; it performs no native/application rerun.

All three Important findings are fixed in one RED/GREEN pass. The control
supervisor supplies signal to its extracted helper and emits an explicit nonclean
receipt if cleanup raises. Fake process/OS controls cover running termination,
escalation, leftover groups and cleanup exceptions without real signals. A new
parent-start event revokes an older pending ticket even if rejected, preventing a
foreign launch from borrowing stale authority; later valid launches still work.
Monitor acquisition/registration is transactional, partial setup rolls back, and
terminal close revokes pending/worker records while preserving foreign ownership.
Four real monitoring-API fault injections and close/reopen controls pass without
actual threads, sockets, HTTP or application work. No second review is performed.

The original95-input review snapshot is retained exactly; three changed public
inputs are reconstructed and checked against their original hashes. This does
not supply the missing native prelaunch epoch. Current fixes have31-command and
pure-audit proof only; historical native controls, their cleanup uncertainty and
missing original integration remain unqualified. NativeHTTPPolicy and CodeEvents
both choose monitoring ID3; future original integration must resolve that ownership
conflict before native qualification. No source-only fix predicts HTTP success.

All three RC gates, five-phase AI/data work and thirteen expert styles remain
required. Complete backend, canonical whole-data/rules/arbitrary-deck acceptance,
seasoned-player benchmarks, natural-game matrix partials and flags, Forge/TCP,
Chrome/Brave/Firefox, LAN/TLS/devices, clean install, exact build/dependency floors,
deployment and current hosted acceptance remain unfinished. Independent RC work
can continue here; native HTTP/backend acceptance needs an environment where the
normal native IPC prerequisite works. No remote-write rejection is bypassed.

Evidence: `/home/nick/mtg-rc-evidence-20261108/native-http-resource-work/VERIFIED.json`.
