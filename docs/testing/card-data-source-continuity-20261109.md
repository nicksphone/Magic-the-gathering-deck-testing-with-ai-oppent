# Card-data source continuity

The earlier 833-case execution remains qualified on `4775d475`'s source,
whose backend/audit bytes matched the recorded `91fd0a04` candidate. This audit
compares that source with `6c23dbda`; it runs no application, tests, SQL or AI.
It does **not** transfer the 833 passes to the current backend.

## What remains equal

All seventeen whole test modules in the
[833-case declaration](current-card-data-acceptance-20261108.md) retain their
exact Git blobs and modes. These named source paths also have no changes:
`backend/card_data`, `backend/knowledge`, `backend/persistence`, `backend/decks`,
and the corpus-sync, knowledge-gap and Oracle-corpus reporting scripts.
Current guarded domain34 and JSON254 executions overlap that old declaration;
they are never added to it as unique cases.

The audit parses public committed Python source without importing it. Its
conservative local-module graph reaches 239 source files on each revision,
including candidate package initializers and existing test setup. All four
changed production paths are syntactically reachable from every declared test
root. There are 8,404 current import records, of which 5,115 occur inside scoped
constructs such as functions, conditionals and exception handlers. These are
import candidates, **not function-execution coverage**.

From-import names can be symbols or re-exports; unresolved external imports,
star imports and runtime import hooks remain ambiguous. One recognized dynamic
import in the closure uses literal `card_data.seed_cards`; its argument is
resolved conservatively while runtime behavior remains unproved. Arbitrary
reflection and pytest/plugin startup are not completely modelled. Cycles do not
make the traversal recursive without bound. Inert parser controls verify relative
imports, package initializers, module/symbol ambiguity, delayed/conditional imports,
cycles and literal/nonliteral dynamic calls.

## Four changed production postimages

Each current file's exact SHA-256 matches its retained qualification source
manifest. This binds the changed **file**, not the entire later composition or
all runtime dependencies. Prior component results remain separate:

| Current production path | Recorded qualification and limit |
| --- | --- |
| `game_state/copying.py` | Reducer initialization preserves caller overrides. Five fresh-interpreter controls and a separate 235-case pure cohort passed. Later production changes are outside that combined execution. [Evidence](copy-import-order-20261108.md). |
| `rules_engine/state_based_actions.py` | Immutable attachment preflight closes its query scope before mutation. The nine-module cohort passed 317 ordinary cases; the earlier eight child-policy failures remain retained. Captured choices/reconstruction are separate from natural games and latency acceptance. [Evidence](attachment-check-preflight-20261108.md). |
| `rules_engine/costs.py` | Sacrifice eligibility shares a query scope; the original eligibility-body AST equals the delegated body's AST. Fifteen whole modules passed 456 ordinary cases. SQL-target checks are not a general filesystem or ATTACH fence; full-backend entry remained unsuccessful. [Evidence](sacrifice-query-scope-20261108.md). |
| `ai/agent.py` | Native projection can retain a winning death-trigger block before material pricing. Both Master modes/seats failed before correction, and all six Strong/Master/MasterPlus winning controls then passed. The 17-module execution still had 120 artifact-environment failures; its separately corrected whole module passed 120. There is no single green whole17 result. [Evidence](master-winning-death-block-20261108.md). |

This source audit neither re-executes those qualifications nor opens their game,
snapshot, database, owner-lock, model, failure-XML or log bodies. It correlates
public reports, source-hash manifests and primitive verification metadata only.
The old 833 run's 553 SQLite connections, 236 distinct owned file targets,
test-loop adjustment and reused dependencies retain their original limits.
No installed-library continuity, clean installation, complete IO fence or
current whole-suite/hosted pass follows from this audit.

## Next acceptance work

The older priority text calling Ghostly Flicker's two-target body unsupported
is superseded by the existing generic implementation and its recorded
[363-case composition](ghostly-flicker-batch-current.md). That is earlier scoped
evidence, not a new current execution. No duplicate implementation or test replay
was launched. General animation, arbitrary blink bodies and full rules remain open.

The next source intake addresses the still-unproved thirteen-style AI requirement:
map canonical fixture/deck admission and actual decision evidence to every required
style before selecting a concrete gameplay defect or qualification. Current source
contains eleven builtin deck templates and fourteen non-unknown selection labels;
these are different inventories. Deck names and labels do not prove strategic
coverage. In particular, `Combo-lite`, `Counter-heavy` and `Removal-heavy` must
not silently redefine the prose's combo and interaction-heavy requirements.
No learned matchup artifact is committed at `ai/data/matchup_profiles.json`.
The loader's explicit lineage and legacy fallback remain unchanged; absence of a
committed artifact does not inspect or characterize any operator's runtime file.
The original matrix, partials, flags, caps and roster remain untouched, and no
new game or data derivation starts here.

A read-only GitHub observation at **2026-11-09 11:24:47 UTC** again returns zero
forks/network members, 88 branch heads and 17 open PRs. Eighty-four branch heads
and all returned PR heads are ancestors of `6c23dbda`; the same four nonancestor
heads were already source-reconciled. This is the returned public inventory,
not unknown/private-fork enumeration or current hosted release qualification.

Public-source manifests, graphs, source deltas, input pins, pure verification,
review and export bindings are retained under
`/home/nick/mtg-rc-evidence-20261108/card-data-continuity-audit/`.
All three release gates, the full five-phase AI/data plan, literal Task1.3,
thirteen-style expert strength, native/browser/TLS/device checks and exact
Caddy/Vite build inputs remain open.
