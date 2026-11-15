# Native backend execution boundary — November 9, 2026

Status: **full backend attempted, failed/incomplete; RC unfinished**.
Source56b20b081cedbf938e7f14830b463aaf6cdcd2ed retains backend tree
95df5186a5c229cfcde8b092afc9c1ec0e24a0ec. No application or original test changes
are made in this increment. The preceding [collection boundary](native-fixture-collection-boundary-20261109.md)
remains a separate collect-only success.

## Actual full attempt

The original `tests` declaration, order and assertions remain intact, with active
plain assertions, no plugin autoload/cache or deselection, and maxfail1. All36,739
nodes match the prior collection exactly;1,645 collection reports pass.

| Recorded outcome | Count |
| --- | ---: |
| Passing setup | 69 |
| Passing call | 68 |
| Failed call | 1 |
| Passing teardown | 69 |
| Native reference requests | 1,275 |
| Authorized SQL connect requests / handle audit events | 1 / 1 |

The failed call is
`tests/regression_agent_wave2/test_restart_and_additional.py::test_pending_modal_discard_choice_survives_sqlite_restart`.
Its exception class is PermissionError. The first unadmitted actor is installed
native `sqlalchemy/orm/loading.py`, `load_on_pk_identity`, definition line527.
The SQL constructor is rejected at actor authorization before a usable connection;
there is no second authorized handle event. The SQL-loading adapter remains
unqualified. No failure value, traceback, SQL statement, result, database body or
test-generated state is inspected by tooling. Later backend outcomes are unknown.

The worker reports17.302366438 seconds. Normal owned-process closure takes
20.010918359 seconds;20,200,036 output bytes stay opaque. The direct child is
reaped and its process group is absent, with no leftover group, supervisor error,
outer stop or cleanup termination. Bounds stay CPU120/125, inner180/outer210
seconds,4GiB,128MiB,retries0. This entry is not replayed to obtain later counts.

Local native code events record calls/normal returns only: choose_action8/8,
MatchFactory.from_decks176/176, checked_action277/258, and
deserialize_match_snapshot65/65. These are event counts, not unique decisions,
playing-strength results or exception-value observations. No return value is read.
Loader and monitoring ownership restore; global profiling remains unset and
unrelated observer callbacks number zero. Final receipts precede interpreter
shutdown; they do not certify every later atexit callback or individual SQL close.

## What changed in the evidence boundary

Positive preparation still copies/hashes only1,818 classified public inputs:
1,745 Python sources and73 public resources. The5,203-entry Git binding leaves
3,385 bodies excluded. Of these,960 native-only reference links bind original
ordinary-file and link metadata; their bytes are neither read, hashed nor copied
by tooling. Public bytes and reference metadata remain unchanged before/after.
This is not whole-tree byte verification or installed-dependency integrity proof.

Native setup/call/teardown roots bind actual collected test/fixture/unittest code
identities, original dispatchers, source read/call lines, active node/phase/thread
and a continuous caller chain. Generator fixture teardown keeps native semantics.
Private owned reads require that authority; an owned directory or JSON suffix
does not make generated state public. Native pytest/pluggy capture/bookkeeping
uses exact loader-returned code plus explicit tempfile/contextlib adapters and
the single orchestration callsite. Captured contents remain opaque.

SQLite requests require a native actor and exact memory or canonical owned path.
File URIs additionally need unambiguous literal `uri=True` at the closest public
connect/Connection source callsite. Dynamic flags, conflicting calls, protected
paths and escapes reject. Eleven exact native SQLAlchemy source files and
pre-phase generated wrappers are bound by code identity. Generated wrappers must
come from native langhelpers._exec_code_in_env:321 with its decorator producer;
no source-string, namespace, closure, frame locals/globals or actual argument/result
inspection is used. The observed loading adapter is outside that declared set.
Handle audit arguments are never loaded; counts do not establish constructor
return or per-handle close. Process closure proves worker termination only.

## Controls and retained failures

Twelve checks pass through exclusive opaque child stdout/stderr. They cover public
callsite/URI extraction, native phase and owned-file gates, full guarded lifecycle,
direct SQLite, SQLAlchemy and ORM controls, teardown faults, template/framework metadata negatives,
current intake and pure terminal verification. The inert constructors operate only
on their own memory/owned fixtures; original application tests are not replayed
for delivery. The full worker also rejects20 pre-import SQL/socket/child/provider/
protected-body/observer-owned routes before usable objects or absent body reads.

Collection-only authority first rejects native lifecycle reads. The new gate
passes six actual inert setup/call/yield-teardown/unittest phases while denying
six observer opens. The actual previous broad owned-directory guard admits six
observer attempts before absent-file IO; the new full guard denies all six while
retaining all six native owned reads. Clone/foreign/line/dispatch/thread/closed
routes reject. No target body exists in those controls.

All-SQL denial, missing static adapters and disabled native template binding each
produce retained RED controls. Their respective GREEN controls authorize five
direct memory/owned/URI requests, one SQLAlchemy request and one ORM request,
with matching handle audit events and observer/path negatives. Metadata controls
trap forbidden frame payload access and reject foreign/cloned/late producers.
These controls do not admit SQLAlchemy loading generically.

Fresh review finds one Important issue: the first implementation permits generated
SQL binding whenever the phase is absent, reopening admission between phases.
The retained epoch does not establish whether that window was exercised. The
correction permanently latches the first actual phase entry; both direct binding
and its audit hook reject all later template admission. An inert real enter/leave
regression fails first, then passes with the latch. The historical epoch, source
and pins stay unchanged; the corrected gate is qualified by controls only, with
no original application replay or retroactive execution qualification.

The reviewer also declines teardown-exception qualification from successful
lifecycle controls. Added native generator-fixture and unittest teardown faults
verify six cleared phase exits, six denied post-phase observer opens, six denied
active-phase observer opens, six authorized absent native reads and restored
loader ownership. A control with cleanup disabled fails first. Native pytest's
unittest reporting supplies a failed call outcome; only the fixture RuntimeError
class reaches this observer, so no second observed exception class is claimed.
The initial new control's expectation of two classes is corrected from native
plugin source, retaining its failed opaque audit. Final review has0Critical,
1Important fixed,0Minor; there is no second review.

Initial guarded capture allocation rejects before an exact framework contract is
added. A misspelled tempfile helper produces retained AttributeError metadata,
then is corrected from stdlib source. The first final verifier incorrectly looks
for epoch-owned manifests in its work directory; its FileNotFoundError and opaque
audit remain retained, and ownership-correct verification passes. A direct
primitive receipt aggregator also raises KeyError and exposes its own traceback
to tooling. This is a failed-auditor diagnostic handling violation, despite no
application/private/failed-stream body read. Subsequent checks use opaque streams;
there is no claim of pristine historical output handling. Earlier actual snapshot
pinning breaches remain nonconforming history.

## Remaining acceptance and handoff

GitHub repository and canonical [roadmap issue2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
are freshly read; the issue remains open. Earlier88-branch reconciliation and
unsupported fork-list limitations are retained, with no new completeness claim
for private/inaccessible work and no remote mutation.

The next increment needs a data-free SQL-loading adapter contract and native
negative controls before another original execution. This checkpoint closes none
of the original three RC gates, five-phase AI/data roadmap or thirteen expert
styles. Full backend/native/browser acceptance, full canonical data, actual expert
benchmarks, original matrix partials/flags, cold TCP/Forge, LAN/TLS/devices, exact
Vite/Caddy prerequisites, clean install/build/deploy and current hosted CI remain
open. No count padding, changed matrix caps, hidden skips, assertion weakening,
archived broad pinners or tooling access to protected bodies is authorized.

External evidence: `/home/nick/mtg-rc-evidence-20261108/native-backend-execution-work`;
terminal epoch: sibling `native-backend-execution-v1`. Review and exact-tree local
public patch exports are bound separately. Controlled-source enforcement does not
claim hostile native-code, descriptor-bypass or race containment.
