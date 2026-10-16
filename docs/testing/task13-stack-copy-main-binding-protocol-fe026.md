# Stack-copy fidelity module-cache protocol correction

Base `fe026defe256f8262652cb4a4b9f36e7a9fc05e2` plus the frozen ten-path
printed-fixture candidate. The previous b72037 and 8d44 cold ledgers and the
completed fe02672 negative preflight remain immutable, not relabelled.

Four fidelity test bodies previously asserted process-global absence of
`main`. That is not a per-body purity contract: an earlier original HTTP test
or ordinary whole-suite collection can legitimately leave the real module
loaded. Reordering the modules is not a solution and was not done.

Each of those four bodies now snapshots both presence and object identity
at entry and requires the same binding at its existing end. The first-consumer
observer additionally checks at the boundary. Initial absence still requires
absence; a preloaded module or sentinel must remain the identical object.
The checker never imports, restores, removes, or substitutes `main`. It is
an entry/boundary/end binding check, not an arbitrary module-attribute audit
or a claim to detect transient changes completely undone between observations.

All printed-fact assertions, real consumers/delegation, twelve full RAW
admissions, physical identities and original28/145 action/StackItem/assertion
contracts are unchanged. An exact AST inverse removes only the two local
protocol-check functions, four entry snapshots, four replaced purity checks
and one added boundary check; it restores the entire prior fidelity AST.

The NEW labeled protocol module has24 cases: eight legitimate preloaded
bindings (ModuleType and sentinel across all four bodies), four cold-absence
controls, and twelve unexpected import/replacement/removal rejection controls.
Its instrumentation forwards the real underlying bodies and values, then
changes only the owned module-cache protocol input. The actual Python import
control uses a scoped stdlib loader creating an in-memory `main` protocol
module; it does NOT execute application main.py, mock HTTP, start a server,
or fabricate card/Oracle facts. Every test restores its protocol input.

Actual new pure TDD: 12 failed/56 passed RED in4.31s, then68 passed GREEN
in4.28s, no errors/skips/xfails/filters. All44 old identities remain; NEW24
identities and bytes are unchanged between RED and GREEN. The RED failures
are the eight rejected legitimate preloads and four missed removals, not
printed-fact failures. Full fidelity+protocol modules were run under the
unchanged native7 audit algorithms, with only declared module cardinality1->2.
Direct fresh Python-B, outer bytecode protection1, all SQL/socket/child/provider
denied, full source/runtime BE equality and FD/thread/child/database closure.

At preparation, the new mixed contract expects original28 + observed44+24 =96 unique nodes,
with the ORIGINAL module still first, including its real HTTP node. That
future order is not a qualification result. A fresh source-only root and
finite source/node/root bindings require parent review and new grants.
No new preflight, SQL, TestClient, actual app import, or mixed96 run occurred.
No production/shared-helper/schema/API/W changes or Phase1/release claim.

## Subsequent Executed Acceptance

The exact three-whole-module declaration subsequently passes all 96 ordinary
cases in 9.60 seconds, with 67 warnings and no errors, skips or unexpected
denials. The original module is first, including five genuine HTTP requests
returning 200 and one completed application lifespan. All source and all 3,674
runtime files/four links/429 directories remain unchanged. Actual database,
backup and owner-lock closure is independently verified before slot release.

A larger source-only `5763e072` declaration then executes all 1,399 expected
identities. These same 96 cases pass, but the whole run does not qualify:
15 unchanged startup-media negative fixtures cannot create their intentional
temporary symlinks under the private harness. They fail before the product's
symlink rejection checks. The exact result is 1,384 passes and 15 failures;
no tests are omitted or relabeled, and a separate harness correction is needed.

Executed evidence is archived under
`diagnostics/ci/task13-stack-fe026-MIXED96-QUALIFIED-20261016-z9vrgcpv/`;
the larger failed ledger is preserved separately under
`diagnostics/ci/task13-parent74-stack1399-5763-HOLD-20261016-gzht9tkp/`.
Neither result closes remaining canonical fixtures, Phase 1, hosted-current
acceptance or the full release.
