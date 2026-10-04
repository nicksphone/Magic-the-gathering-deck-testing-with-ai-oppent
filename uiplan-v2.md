# UI Agent: Competitive Card Table, Second Visual Pass

## User feedback and goal

The user finds the integrated redesign better, but still too basic. Build a
visually finished, Arena-inspired competitive playtesting experience, not a
generic dashboard with card tiles. Preserve every existing working action and
backend contract. This is a presentation and interaction-polish task, not a
rules-engine rewrite.

## Workspace and coordination

- Read `graphify-out/GRAPH_REPORT.md` first and use its wiki if present.
- Use a separate worktree/branch based on current committed main, which already
  contains the first redesign. Do not continue from the old pre-integration
  backend base or change the live main checkout.
- Own frontend presentation files and a new `docs/ui-redesign-v2.md` report.
  Leave backend, root README/CHANGELOG/plan, shared Graphify output, databases,
  caches, deployment and dependencies untouched. Add no dependencies unless
  clearly necessary and justified in the handoff.
- The backend owner is handling rules repairs and the complete integrated
  browser harness. Do not overlap that assignment or edit existing browser
  tests to make a failing behavior pass. Add isolated visual/interaction tests
  under new filenames. Flag any necessary existing-test selector changes.
- No reset, force push, live service restart or deletion of another agent's
  work. Commit your owned work and report commit IDs; parent integrates it.

## Visual direction

1. Make the active game a near-full-width card table. Give the battlefield a
   deliberate textured environment, restrained depth, a center divider, and
   readable spatial separation between opponents. Avoid giant empty dashboard
   panels, repeated borders, and a permanently open management sidebar.
2. Give each player a compact, designed identity/life/zone cluster. Establish
   clear active-player, priority and response states without relying only on
   color. Keep hand, stack, lands and combat visually distinct and predictable.
3. Make real cached card artwork the visual focus when available. Keep readable,
   attractive text/offline fallbacks; never fake loaded images or invent card
   text, stats, names or actions. Use original ambient art/textures if useful,
   not copied Arena interface assets. Do not add per-card network fetch loops.
4. Design the hand as a purposeful card tray, with controlled overlap/scroll,
   smooth inspection, crisp selected/legal/disabled states and usable labels.
   Crowded cards must remain individually reachable with pointer and keyboard.
5. Make stack and combat feel like game elements rather than debug lists.
   Emphasize pending responses, selected attackers/blockers and actual targets;
   never suggest a move is legal unless the authoritative state allows it.
6. Give phase/priority actions a compact coherent command area. Hierarchy should
   make the next useful legal action obvious, without hiding less common ones.
7. Give the no-match screen a designed deck-selection/start experience. Match
   history, diagnostics, import, simulator and settings belong in accessible
   drawers/tabs or secondary surfaces, not in competition with the battlefield.
8. Choose intentional typography, spacing, iconography, lighting and accent
   materials. Use restrained meaningful motion, visible focus and reduced-motion
   support. Avoid generic neon/glass effects or decorative motion everywhere.

Aim for a cohesive premium game interface. A mere recolor, larger cards, extra
glows, or rounded boxes does not meet this brief. Explain the visual hierarchy
and demonstrate it with actual browser screenshots.

## Nonnegotiable behavior

- Preserve both human seats, hidden opposing hands and acting-seat ownership.
- Preserve all legal hand/exile/library plays, face selection, X, alternate and
  additional costs, mana choices, targets, modes, activation, equip/crew,
  mulligans, cleanup, replacement/trigger choices and BO3 transitions.
- Preserve exact-ID land selection. Do not group unlike mana abilities or put
  animated creature lands into a misleading ordinary-land bucket.
- Preserve effective stats/counters/damage, durable recovery, pending-request
  guards, visible actionable errors and current simulator diagnostics.
- Card inspection must work for hands, permanents and available face data,
  including keyboard entry/Escape/focus restoration, without obscuring actions.
- Real large battlefields must remain usable. Verify at least 20 lands,
  15 permanents and a 15-card hand with independently selectable IDs.
- Keep readable laptop/mobile layouts, 200% zoom and no unintended page-wide
  horizontal overflow. Do not solve desktop crowding by shrinking text beyond
  readability or hiding cards without a usable navigation control.

## Work and validation

1. Inspect the current rendered UI. Record what looks unfinished and sketch a
   unified table, lobby and secondary-panel hierarchy before coding.
2. Implement the complete visual pass in connected chunks, not unrelated tweaks.
3. Run frontend unit tests, lint and production build. Fix errors before handoff.
4. Use disposable local backend copies for browser checks; source-relative SQLite
   means tests in a live checkout can write live data. Never use production
   matches or databases for fixtures. Prefer existing canonical fixture routes.
5. Exercise both seats, legal casting/payment, exact land selection, crowded
   boards/hand inspection, pending choices, recovery and failure feedback.
6. Capture actual browser screenshots for lobby, a real active match, crowded
   board, response/choice state, card inspection, laptop and narrow viewport.
   Label injected fixture states honestly; no mock screenshots as runtime proof.
7. Record commands/results, accessibility and layout findings, remaining gaps,
   files changed and commits in `docs/ui-redesign-v2.md`. Do not claim universal
   rules correctness, complete browser coverage, or expert AI from UI checks.

## Storage and handoff

Keep active source, dependencies, scratch and SQLite local. Archive completed
screenshots/logs/evidence under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/ui-redesign-v2/`
only after verifying the NFS share is mounted and writable. Verify archived
copies before cleaning disposable local artifacts. Never open SQLite on NFS.
Preserve uncommitted user data; GitHub is only a restore path for committed code.

Do not deploy directly. Return the visual rationale, before/after screenshots,
owned commits and verification results for the parent to review and integrate.
