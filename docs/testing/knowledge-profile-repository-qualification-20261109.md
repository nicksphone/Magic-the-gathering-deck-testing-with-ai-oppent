# Knowledge Profile Repository Qualification: November 9, 2026

All four cases in the whole original
`backend/tests/test_knowledge_profile_repository.py` pass against real owned
in-memory SQL. Its three test functions and all26 assertion ASTs are unchanged.
This adds repository preservation and idempotence evidence; the application,
backend and AI policy have no source changes in this checkpoint.

The two-card case profiles Lightning Bolt and Grizzly Bears, opens a fresh
session, and repeats profiling with zero updates. Original assertions preserve
the exact `(id, updated_at, profiles_json)` tuple, canonical identity/source,
opaque future namespace and numeric/profile-derived fields. The two invalid-row
cases use an identity mismatch and an opaque tactical namespace; each reports
one error with zero profiles/updates, then verifies the original stored tuple
in a fresh session. Instrumentation never reads these SQL rows or tuples.

The155-card case verifies the committed RAW/provenance pin, exact155 canonical
IDs and shipped names, then writes and profiles all155 rows. The fresh-session
assertions preserve complete RAW data, source URI, future metadata, canonical
IDs and numeric profile fields. Pending ruling arrays and `rulings_verified=False`
remain pending. A second native profiling call reports155 profiled/zero updated.
This case does not independently compare every155 timestamp. The two-card
fixture's `rulings_verified=True` with empty arrays is a controlled test vector,
not official or live upstream ruling verification. No knowledge-quality or AI
strength score is inferred from these preservation tests.

The execution freezes base4332f668: all5,184 base Git blobs/modes plus the initial
plan, totaling5,185 public files. All2,699 backend files remain unchanged, with
backend tree8caa573558ae3aad708661b5485f69eb882f12db. The initial plan SHA256 is
64a426ad9985df6bbb7ef348ee1f9cd2587b4f96666712d857f6cc7942166dee.
Final nonexecuting prose/ledger binds separately from this execution snapshot.

Whole-module collect-only session67615 exits0 with exactly four literal nodes
and zero original test starts, SQL connections, AI choices or children. The old
catalog rejects the new module; the new catalog accepts four combinations and
rejects11 typed/opaque/missing/extra/unknown cases. The bounded resolver's four
function ASTs and indexed source-coordinate helper remain inherited.

Old SQL-context and ingestion-helper protocol controls refuse the new fixture
and direct profiler calls before implementation. The new exact context admits
only source fixture `database`, `sqlite:///:memory:`, StaticPool and native
constructor setup at line18. Native close must return under the same fixture's
teardown `engine.dispose` line22, with matching case, handle, engine, frame and
thread. Six SQL primitive audit/constructor functions retain their prior ASTs.
File SQL, URI/custom-factory and native-alias bypasses remain denied.

The profiler protocol binds the original `profile_corpus` function/import/code,
Repository receiver identity, active original test entry, exact callsite/order
and unchanged `corpus=None, archetype=None` defaults. It observes nominal dict
returns without reading contents. Literal `invalid` values are captured before
test bodies; controls replace later values with poison and never traverse them.
Repository rows, names, RAW payloads and test state stay opaque. Four detached
entry/fixture views and six direct-call views pass;36 invalid contexts and26
corrupt receipts fail. A separate single empty native memory connection/close
proves the context with zero queries and no database-body access. It is neither
an application case nor an extra successful repository test.

The single application invocation, session47467, exits0 with four passes and
all12 setup/call/teardown phases passing. Four native SQL constructor/handle/
return/teardown-close pairs and six direct native profiler returns verify.
There are zero AI choices, nested native calls, children, file-SQL/socket/
provider/owner operations, guard denials, constructor failures or authorizer
rejections. Original source and native functions remain unchanged/unwrapped.
JUnit time is22.055s, worker23.460330s and supervisor28.011226s. Terminal owned
output is1,446,323 bytes. CPU120/125hard, inner180/outer210 seconds, AS4GiB,
output128MiB, retries0/maxfail1 and plain active assertions remain fixed.
Native owned-worker reap and process-group absence verify without intervention.

All30 runtime inputs,20 collection inputs, source/RAW/initial-plan/control pins,
primitive progress/return receipts and actual supervisor scope/control hash
verify. Both fresh optimized negatives stop before application/cohort creation.
The pure verifier imports no application, runs no tests/SQL/network and reads no
private body or failure log. Its green XML contains metadata-only suite/case
tags after terminal success is confirmed. Guards are trusted instrumentation,
not OS isolation. No prior completed cohort, game or choice is replayed for
counts; this checkpoint has no failed control/application attempt.

Evidence is under
`/home/nick/mtg-rc-evidence-20261108/knowledge-profile-repository-qualification/`,
with sibling collection/intake/work ledgers. The single fresh Astra high
read-only final review finds0Critical/0Important/0Minor and independently checks
source/Git/backend, runner/control/receipt/cleanup-helper pins and actual
SQL/profiler/entry/closure associations. It executes no application, guard,
control or auditor and reads no private/failure body. Installed dependency
bytes/versions were not separately frozen before runtime; executable path,
observed native identities/configuration and source/harness bindings are the
recorded scope. Post-hoc hashes cannot establish historical library provenance.
Final author document/commit/exact-tree binding follows separately; those
receipts establish delivery without replaying the passed application cases.

The preceding4332 GitHub observation remains scoped to its88 returned branches,
17 open PR heads and four source-reconciled nonancestor heads. This checkpoint
does not perform new remote enumeration or mutation. Unknown/private forks are
not covered by zero fork/network metadata.

The original [RC audit](rc-readiness-20261108.md), root Gates1--3, complete
five-phase AI/data plan and
[roadmap issue2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
remain open. Fullbackend/hosted clean install, literal global Task1.3 scope,
complete Oracle/data/rulings, expert thirteen-style AI, native Forge/TCP,
browser/TLS/devices and exact Caddy/Vite inputs remain unproved. The matrix's
four partials/15 flags across13 decisions and prior receiver/Phyrexian/label
limitations remain. A four-case repository pass closes none of those gates.
