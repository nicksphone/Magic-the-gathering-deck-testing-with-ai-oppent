# Rules Regression Agent Handoff

Help the MTG Deck Testing Lab backend agent by independently identifying and
reproducing rules defects. The UI agent is redesigning the frontend concurrently.
Your deliverable is canonical fixtures, meaningful regression tests, and a clear
failure report, not engine fixes or UI changes.

## Workspace Isolation

Repository: `/home/nick/mtg-deck-testing-lab`.

Read applicable AGENTS.md instructions and `graphify-out/GRAPH_REPORT.md` before
source exploration. If the graph wiki index exists, use it for navigation. Verify
current source rather than treating inferred graph relationships as proof.

Create a separate branch and worktree from committed main:

```sh
git -C /home/nick/mtg-deck-testing-lab worktree add -b tests/rules-regression /home/nick/mtg-rules-regression main
```

If either already exists, inspect it rather than overwriting it. Record the base
revision. Do not modify the original checkout, copy its uncommitted changes,
reset files, merge into main, or push directly to main.

## Ownership

Add files only under these new paths in your worktree:

- `backend/tests/regression_agent/` for discovered regression tests.
- `backend/tests/fixtures/regression_agent/` for canonical data/provenance.
- `docs/testing/rules-regression-agent.md` for the handoff report.

Do not modify engine/effect/AI/API code, existing tests or fixtures, frontend,
dependency manifests, root README, CHANGELOG, plan.md, or shared Graphify outputs.
Report required changes instead. Coordinate any unavoidable overlap before edits.

Never touch the live database or cache. Backend SQLite paths are source-relative:
changing cwd alone does not isolate writes. Run tests in a disposable tracked-source
copy with its own local database/cache. Do not run SQLite on NFS. Do not restart or
stop another agent's services. Avoid servers unless required; if required, inspect
port ownership and choose a dedicated unused loopback port, not 9999, 5173, 10199,
15173, 19222, 10200, or 15174.

## Investigation Priorities

Inspect existing coverage first; avoid duplicating already meaningful tests.
Investigate connected interaction families across at least two deck styles:

1. Replacement/prevention interactions, competing replacements, event ordering,
   and explicit cannot overrides.
2. Continuous buffs and abilities: counters, anthems, temporary effects, source
   departure, suppression, layer ordering, and effective combat stats.
3. Graveyard interactions and zone changes: death/discard triggers, recursion,
   incarnation tracking, legal cast permissions, and snapshot restoration.
4. Counterspell/response timing: real priority, legal targets, stack copies,
   uncounterable spells, costs, and resolution continuations.

Do not assume a matchup must be 50/50 or manipulate deck composition to force
expected win rates. Do not invent cards, Oracle clauses, or unsupported behavior.

## Evidence and Tests

Use real cards and official current Oracle text/rulings from Scryfall or an
equivalent canonical source. For rules interpretations use authoritative Magic
rules sources. Preserve URLs, identifiers, retrieval dates and the relevant rule
or ruling reference in fixture/report provenance. Do not claim full card support
from one recognized clause or parser classification.

Construct focused deterministic positions through existing test helpers or actual
checked actions. Clearly distinguish interaction fixtures from legal tournament
decks. Exercise both seats where controller/owner order matters. Cover legal
announcements, paid costs, resulting zones/stats/life, triggers, priority, and
snapshot recovery as appropriate. Rejected actions should leave state unchanged.

For each suspected defect:

1. Explain the expected outcome and its authoritative basis.
2. Add the smallest test that reproduces actual behavior through a real engine
   path, not a mocked desired outcome.
3. Run it in isolated source and retain exact command, revision, result and log.
4. Distinguish confirmed engine failures from fixture mistakes, unsupported
   mechanics, integration gaps, and unverified interpretations.
5. Keep confirmed failures intact. Do not weaken assertions, add xfail/skip merely
   to hide failures, or implement a source fix. The backend agent owns repairs.

Run the new test selection together to detect fixture interference. Run relevant
existing tests where feasible and accurately report the scope; do not call an
unrun full suite passing. No changes to shared dependencies or credential use.

## Artifact Storage

Keep active code, dependencies, running test scratch and SQLite local. Archive
completed evidence under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-agent/`
with a unique run directory. Verify NFS is mounted and writable; do not silently
fall back to SSD storage. Verify archived copies before removing your completed
scratch. Preserve uncommitted work explicitly; GitHub cannot restore user data.

## Handoff

Commit only your owned new fixtures/tests/report on `tests/rules-regression`.
Do not merge into main. Provide the backend agent:

- Base revision, branch, commit IDs, and files changed.
- Ranked confirmed failures with test node IDs, expected/actual outcomes, and
  canonical source references.
- Exact checks performed, passing/failing counts, and archived evidence paths.
- Any uncertain findings or manual verification requirements.
- Suggested shared root-cause repair locations, clearly labeled proposals.

The backend agent will review and integrate the tests, repair shared engine paths,
run the milestone gates, update shared docs/Graphify, and publish. Your role is to
produce independently verifiable evidence, not certify arbitrary Magic rules or
seasoned-player AI.
