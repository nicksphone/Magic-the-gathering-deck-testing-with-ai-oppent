# UI Agent: Integrated Regression Follow-Up

Your redesign handoff is reviewed. The backend owner independently passed your
five suites (redesign, lab, human actions, recovery, simulator preflight) against
the repaired backend, plus frontend test/lint/build, in disposable source.
The original 41-script browser harness also passed with the old presentation.
The remaining integration check is the complete harness with your new UI.

Keep using your own clean `ui/arena-inspired` worktree. Do not edit main,
production backend code, shared docs/Graphify, or the release agent's work.
Record your actual starting commit. Read the applicable instructions and graph.

## Frozen Backend Input

The backend owner's completed frozen source bundle is:
`/tmp/mtg-rules-repair-caqUt4/final-backend.tar`

SHA-256:
`a8c3483c9d47cca4d75617e28fc2509afce28e9f66d976f5fcf8f15c067e97ae`

Verify that hash before using it; read this bundle only, never modify it or the
backend owner's scratch. It contains the five cross-family repairs, including
the corrected multiline counter follow-up. It is an uncommitted implementation
snapshot based on `26c9734`, not a claim that those repairs are already published.
The later two HTTP tests change test coverage only, not these production files.

If the bundle is unavailable, ask the backend owner for its archived equivalent;
do not silently replace it with your older backend or a live database.

## Execute

1. Make your own disposable local tracked-source copy of the frontend branch,
   overlay the verified backend bundle, and use isolated dependencies. Preserve
   source provenance separately if you initialize a temporary Git repository so
   `run-browser-ci.sh` can enumerate files. A temporary commit is not main HEAD.
2. Run frontend unit tests, lint and build, then the complete
   `frontend/tests/run-browser-ci.sh` on that combined source. Ensure the harness
   copies the supplied repaired backend, not your branch's older backend.
3. Inspect ownership and the harness lock before using fixed loopback ports
   10199/15173/19222. Wait if occupied; do not kill another agent's processes.
   Never test against backend 9999 or the live source-relative SQLite database.
4. If a test fails, distinguish real broken controls/payloads from stale selectors
   or timing. Fix only your frontend-owned paths. Do not remove assertions,
   fabricate fixture results, hide regressions with skips or change engine rules.
5. Recheck both seats, deliberate choices, exact land IDs, faces/costs, hidden
   information, reload/process restart, and natural BO3 flows. Preserve logs and
   screenshots where they change the diagnosis. No universal-Magic or expert-AI
   certification claim.

Write your final report in NEW `docs/ui-integration-validation.md`, including
backend bundle hash, frontend commit, exact commands/results, failed attempts,
source changes if any, and remaining manual ergonomics/accessibility concerns.
Do not modify root README/plan/changelog or the first handoff report.

Archive completed evidence on verified mounted/writable NFS under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ui-integration-agent/`
with a unique directory; verify copies before removing your successful scratch.
Keep active SQLite local, and leave other agents' artifacts alone.

Commit only your frontend fixes and new report on your branch. Do not merge or
push main. Provide commit IDs and verified evidence paths to the backend owner
for integration. Do not recreate the redesign or start another visual overhaul.
