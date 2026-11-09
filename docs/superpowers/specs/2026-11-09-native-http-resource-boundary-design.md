# Native HTTP event-loop resource boundary design

Continue the full MTG RC objective at e4bb1095514a0538e5c20e59adf7693226e6997e, backend95df5186a5c229cfcde8b092afc9c1ec0e24a0ec. The previous whole entry collected36739nodes and passed170calls before HTTP fixture setup hit the blanket socket guard. Actual socket arguments/handles/failed outputs remain uninspected. Public TestClient/AnyIO/asyncio source suggests native worker-loop self-pipe construction; prove this on an inert app before admitting it.

The implementer chooses a source/CodeType-backed launch lease and exact native self-pipe chain. A local PY_START callback on Thread.start must authenticate the exact AnyIO generator/contextlib/TestClient path through an original active test/fixture root and phase thread. Only its exact native portal worker root/bootstrap chain may redeem the one pending launch lease on its worker thread; expire pending authority at phase exit and worker authority on native root return. No Thread object/target/closure/locals/actual argument or return-body inspection. The ordinary immutable-source/trusted-instrumentation premise remains explicit; no hostile race/rebinding/sandbox claim.

Socket authority is limited to that worker startup, exact socket.socketpair/_make_self_pipe/loop-construction native code and literal source callsites. Only after actor admission may the native constructor audit expose integer family/type/protocol resource selectors, never its socket object argument. Admit at most one native AF_UNIX/SOCK_STREAM/proto0 socketpair module-entry request and two public wrapper constructor audit events per worker loop. Inert RED proves the raw C socketpair returns two endpoints without native constructor audit; its module entry therefore needs a pre-creation wrapper. Pre-guard captured C aliases remain outside the ordinary trusted-instrumentation premise; no general socket audit/sandbox certificate. Native bare-new delegation may preserve original construction only through the same native chain; foreign/bare/observer constructors still deny before argument inspection. No bind/connect/DNS/listen/remote or provider/child allowance.

Alternatives: globally permit UNIX sockets (too broad), inspect worker targets/frames/handles (prohibited), or use this narrow lease/chain contract (chosen under standing authorization). Preserve every original test/argv/assertion/order and actual app lifespan; do not substitute a synthetic app for original acceptance. The inert app proves the boundary only. One new full original entry must retain the first new failure/partial.

All original3RC gates/five-phase AI-data/thirteen-style requirements stay required. Runtime body admission remains1745Python+73resources with960metadata-only native references. No actual state/snapshot/hand/move/action/decision/trace/card-result/owner/model/SQL/output/failed-stream body inspection/hash/copy. Parent-I-S-B/plainassertions/noautoload/nocache, CPU120/125,inner180/outer210sec,4GiB,128MiB,retries0,maxfail1; original child ordinary startup distinct, CPU30/35/inner30/same ownedPG. Do not rerun original work for review/delivery, increase limits, filter/skip/partition/pad tests, revive broad archived tooling, waive historical breaches or bypass rejected remote writes.


## Verified prerequisite and conditional execution

The first native wake-up send on a separately owned inert AF_UNIX socketpair fails
with PermissionError without guard/monitor/app imports; both subject endpoints
are closed. Plain Starlette, literal-ASGI TestClient and plain AnyIO portal
baselines all stall under inner25/outer40 limits and close their owned groups.
The guarded prototype admits one pair/two wrapper constructors but likewise
cannot complete startup; its monitor/worker cleanup is unknown after inner exit.
This identifies an external native-IPC prerequisite. It is not a passing HTTP
control. Bind and retain the failed evidence; the original whole entry is deferred
until this prerequisite works. Full original acceptance remains required unchanged.
No native IPC failure is rerun for delivery, and no syscall/transport/ticker
workaround or larger timeout substitutes for native execution.
