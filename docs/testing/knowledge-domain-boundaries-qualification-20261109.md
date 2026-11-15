# Knowledge Domain Boundaries Qualification: November 9, 2026

The whole original `backend/tests/test_knowledge_domain_boundaries.py` passes
all34 cases with its four test functions and nine assertion ASTs unchanged.
Twenty-four invalid-domain cases cover insert/update rejection for unsupported
provenance, absent/empty sources, out-of-range scores, NaN, signed infinities,
and invalid threat values. Original assertions observe no INSERT/UPDATE/DELETE,
unchanged row dumps and no new/dirty ORM objects. This is reject-before-write
evidence; it does not assert that no read query occurred.

Eight valid-domain cases preserve row identity, admitted numeric/source values
and opaque JSON. One schema-only case checks provenance enum and numeric bounds
without SQL. One legacy case writes an explicitly invalid old-style ORM row and
proves it remains readable without rewrite. These manual/legacy schema controls,
including rows labeled `scryfall`, are not canonical Oracle knowledge fixtures.
No production, backend or original test source changes in this checkpoint.

Base331d4c16 freezes5,186 Git blobs/modes plus the initial plan:5,187 public
files, including all2,699 unchanged backend files/tree8caa5735. The initial plan
SHA256 is8964cd1bddedfc497b8e0602084cfe28bf18258e39fe7896e280c018892392ff.
Final nonexecuting prose and ledger bind separately from the execution snapshot.
Whole collect-only session19325 exits0 with exactly34 nodes and zero original
test starts, SQL connections, AI choices or children. All22 collection inputs
and15 collection receipt pins verify; closure is normal.

The old catalog, float/static signed-number and math-name rules reject the new
source. The new bounded interpreter admits exact finite float constants, signed
int/float syntax and the original unaliased `from math import inf,nan`. It rejects
unknown names, attributes, calls, shadowed/rebound imports, non-finite numeric
constant syntax and unsupported types. It does not eval or execute application
source. Exact IEEE754 bits retain type, signed zero, infinity sign and NaN
payload. JSON receipts encode floats as tagged primitive dictionaries and
contain no raw non-finite JSON number. All34 source combinations and35 negative
literal controls verify; the bounded source-coordinate helper is unchanged.

A separate inert RED exposes an entry-guard alias: encode-only comparison could
accept an already encoded float marker as an actual float argument. The entry
guard now validates the raw before-body parameters against the exact static
source types before encoding. Marker dictionaries, integer substitutes and
foreign NaN payloads cannot masquerade as source floats. All other entry helper
function ASTs remain unchanged. Late parameters become poison in controls;
lookup, SQL and return checks use captured metadata without revisiting them.
This is an external instrumentation correction, not a product behavior change.

Only the original `repo` fixture can open native `:memory:` SQL during setup
at source line17. Its original `sqlite://` URL has no database component and
uses SingletonThreadPool. Native teardown close at line20 must match the same
fixture frame, case, engine, thread and registered handle. The schema-only case
cannot register SQL or borrow another case's handle. Old source/pool context
controls refuse these new contexts;49 new context negatives and20 corrupt
receipt negatives fail while34 inert entries/33 fixture lifecycle views pass.
Six primitive SQL constructor/audit function ASTs and existing I/O protection
remain inherited. A separate empty native memory constructor/close canary runs
zero queries and reads no database body; it is not an application test case.
Original test-owned SQL observers remain untouched; guards never inspect their
statements, callbacks' collections, row dumps or actual database contents.

Before collection and runtime,523 selected installed public files totaling
33,577,106 bytes are pinned and later rechecked: SQLAlchemy2.0.57,
SQLModel0.0.22, Pydantic2.9.2/core2.23.4, pytest9.0.3 and selected pluggy,
greenlet/typing distribution code and METADATA, plus the Python3.12.3 executable,
SQLite wrappers/native extension/libsqlite3. `math` is built into this Python
executable. These selected pre/post pins are not a complete transitive
dependency, standard-library or OS reproducibility certificate. They do not
retroactively fill the previous checkpoint's absent library epoch pins.

The initial library freezer incorrectly required a separate math extension and
stops before its manifest or application launch. The dependent first pin attempt
then reports the absent manifest. Actual import-spec metadata identifies math as
built-in; the corrected freezer pins it through Python. Both failed setup paths
and the first optimized-bootstrap receipt remain preserved. The changed worker
gets a fresh optimized negative before collection. A later verifier-builder
substring assertion rejects legitimate `2699` and four-function checks; its
source/error metadata remain preserved, and a narrowed generator plus the pure
verifier succeeds without application replay. Failure log/XML bodies stay
unread/unhashed. None of these is an extra passed case or an application failure.

The single application invocation, session4196, exits0 with34 passes and all102
setup/call/teardown phases passing. All33 native SQL constructor/handle/return/
teardown-close pairs verify, and the pure schema case uses zero SQL. There are
zero AI/native profiler/ingest calls, file-SQL/socket/provider/owner operations,
children, guard denials, constructor failures or authorizer rejections.
JUnit time is10.039s, worker11.482597s and supervisor14.005685s. Terminal owned
output is1,738,097 bytes. CPU120/125hard, inner180/outer210s, AS4GiB/output128MiB,
retries0/maxfail1, plain assertions and original module/parameters remain fixed.
The worker is reaped and its owned process group disappears without intervention.

All31 runtime inputs, source/Git/initial-plan/selected-library/control pins and
primitive entry/phase/SQL receipts verify. The pure verifier runs no application,
test, SQL or network and reads no private body. Green XML is inspected only after
terminal success and contains metadata-only suite/case tags. Fresh optimized
negatives stop before application/cohort creation. Guards remain trusted Python
instrumentation, not OS containment. Evidence is under
`/home/nick/mtg-rc-evidence-20261108/knowledge-domain-boundaries-qualification/`,
with sibling collection/intake/work ledgers. The single fresh Astra high
read-only review finds0Critical/0Important/0Minor. It independently checks3,097
public Python/Markdown snapshot hashes/Git bindings, original source, all31/22
runner and26/15 receipt pins, selected523 installed files and typed-entry/SQL/
closure/recorded-ancestry associations. It executes no application, test, guard,
control or auditor and leaves protected/SQL/failure/non-code fixture bodies
unread. Final author document/commit/exact-tree export checks follow separately;
their receipts establish delivery without replaying the passed application.

The original [RC audit](rc-readiness-20261108.md), root Gates1--3, complete
five-phase AI/data plan and
[roadmap issue2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
remain authoritative and unfinished. Full backend/hosted clean installation,
global Task1.3 interpretation, complete Oracle/rulings/corpus, expert thirteen-
style AI, native Forge/TCP, browser/TLS/devices and exact Caddy/Vite inputs remain
unproved. Original matrix partials/flags/decisions and earlier receiver/Phyrexian/
label limitations remain. A fresh GitHub GET at09:35:19UTC returns88 branch heads:84 local ancestors
and the same four previously source-reconciled nonancestor SHAs; all17 open PR
heads remain ancestors. No additional runtime work is identified in that
returned inventory. Zero fork/network metadata is not unknown/private-fork
enumeration, and no remote mutation or release acceptance follows. These34 storage
controls close no release or playing-strength gate.
