# Rules Regression Agent: Second Investigation

The first investigation is complete. The backend owner independently reproduced
its 14 failing and 16 passing cases against main at
`26c973449fa25591b6fc99d873512b13d8225e92` and owns the engine repairs.
Do not revisit or modify that handoff. This is a separate tests-only assignment.

## Isolation And Ownership

Read applicable AGENTS.md and the Graphify report before source exploration.
Use your existing `/home/nick/mtg-rules-regression` worktree and
`tests/rules-regression` branch. Check for uncommitted work first; preserve it.
Record your actual base and HEAD. Do not reset, rebase, merge main, or overwrite
the first investigation's files while the backend owner integrates them.
You may inspect committed main read-only to check whether a finding is already
fixed; report any difference between your branch and main explicitly.

Own only NEW files beneath:

- `backend/tests/regression_agent_wave2/`
- `backend/tests/fixtures/regression_agent_wave2/`
- `docs/testing/rules-regression-agent-wave2.md`

Do not edit production code, existing tests, first-wave files, shared docs,
Graphify outputs, dependency manifests, or another agent's worktree. Do not
merge into or push main. The frontend and release/storage agents have separate
assignments. Leave their files, services and processes alone.

## Objective

Find reproducible cross-card casting and decision-contract defects before the
backend owner takes on the next implementation batch. Test real checked actions
and generated legal moves; parser recognition alone is not correctness.

Prioritize these connected families, using at least two deck styles:

1. Variable costs: legal X values, zero versus positive X, generic versus actual
   colorless requirements, hybrid payment, and choosing affordable targets.
2. Alternative/additional costs: flashback, kicker, sacrifice/discard costs,
   restrictions on their combinations, and whether legal moves agree with
   announcement and actual payment. Include relevant supported mechanisms
   such as delve/convoke only after checking the existing implementation.
3. Modal and multi-face plays: selected face's types, costs and timing;
   front-face library characteristics versus cast-face characteristics;
   adventure or split-card permissions where actually supported.
4. Targets and choices: mixed target zones, all versus partly illegal targets,
   minimum/maximum selections, duplicate targets, and snapshot continuation.
5. AI legality and useful decision boundaries: an affordable legal alternative
   must not loop on an impossible cost/target. Use deterministic positions with
   real cards, multiple legal options, and private-information constraints.
   Distinguish a demonstrably illegal action or stall from a debatable strategy.

Exclude the current backend repair families: Remand-style counter/destination
clauses, Reanimate-style linked life loss, graveyard exile responses, Furnace
damage replacements, and undying death triggers. Do not duplicate first-wave
failures or manufacture new cards/deck balance expectations.

## Method And Acceptance

- Inspect existing tests first and concentrate on uncovered interaction seams.
- Use canonical real-card data, authoritative Oracle/rulings/rules and recorded
  URLs, identifiers, retrieval dates and relevant references. Do not invent text.
- Prefer a bounded batch of roughly 20-40 meaningful cases over hundreds of
  permutations of the same assertion. Cover both seats where it matters.
- Exercise legal-move generation, checked announcement, payment, resolution,
  resulting state, and durable restart when applicable. Use ordinary engine
  paths, not a mocked implementation of the expected result.
- Rejected actions must leave the complete authoritative state unchanged.
- Keep confirmed failing assertions intact: no weakened assertions, xfail or
  skip to hide failures. Fix fixture errors before labeling a defect.
- Reproduce twice with pinned seeds and run relevant existing tests alongside
  the new selection. Record exact commands, commits and counts, not inferred
  full-suite success. No large round-robin or tuning to force a win percentage.

Backend SQLite paths are source-relative. Run all tests in a disposable tracked
source copy with its own local database/cache, never in either live worktree.
Changing cwd or an unverified environment variable is not isolation. Use the
existing backend venv without changing shared dependencies. Avoid servers;
if essential, choose an unused private loopback port after inspecting ownership.

## Evidence Storage And Handoff

Keep active scratch and SQLite local. Verify the NFS share is mounted and
writable before archiving completed evidence under:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-agent-wave2/`
Use a unique run directory. Verify archive content and checksums before removing
your successful disposable scratch. Do not delete the first-wave scratch until
its evidence is safely archived and its handoff preservation is verified.

Commit only your new owned files on your branch. Report:

- Base/HEAD and commit IDs; changed files and verified archive path.
- Ranked confirmed defects with test IDs and exact expected/actual outcomes.
- Whether each failure also reproduces on current committed main, if checked.
- Relevant shared repair locations, labeled proposals rather than fixes.
- Passing controls, uncertain interpretations and unsupported families.
- Exact checks and repeatability results; anything needing human review.

The backend owner will review/integrate the batch, implement shared repairs,
run milestone gates, update shared documentation/Graphify and publish. This
assignment does not certify arbitrary-card support or expert AI.
