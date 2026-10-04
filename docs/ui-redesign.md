# UI redesign handoff

Branch: `ui/arena-inspired`. Base: `a69233fa5e037ae90320a972da6f5d601ac2bfcd`.

## Main integration

The parent integrated the exact frontend/documentation diff through `8135b45`
after reviewing the handoff. Its frontend unit checks, lint and build passed
again in main, and the existing LAN Vite server serves the new `table.css`.
Before integration, the parent ran UI redesign, lab, human-actions, recovery and
simulation-preflight browser suites against the repaired frozen backend; all
passed. Evidence is under the rules repair archive's verified gate bundle.
The full integrated browser harness is still separately assigned in
`ui-integration-plan.md`. This is not a claim of a completed long-session soak,
every possible action, or a finished UI release.

## Inspection checklist

- [x] Battlefield-first layout and compact action rail; existing Controls callbacks and mutation gate retained.
- [x] Saved games, deck tools, diagnostics, playback settings and logs use deliberate disclosures and bounded history previews.
- [x] Opponent above acting human; separate permanents/resources/hand, hidden information and permitted non-hand actions preserved.
- [x] Keyboard inspection, viewport-safe portal previews, explicit combat/status badges and individually addressable grouped lands.
- [x] Chromium verification of both seats, crowded boards, long hands, choices/stack, request failures, recovery, narrow widths, zoom and reduced motion.
- [x] Final test/lint/build and scoped diff checks passed; evidence copied and SHA-256 verified on mounted, writable NFS.

## Implementation and changed paths

- `frontend/src/App.tsx`: battlefield-first navigation, compact action rail, visible pending-choice notice, global request errors, lab/saved-match disclosures. Existing mutation/restoration fieldsets and mutation gate remain.
- `frontend/src/styles/{app,table}.css`: original dark textured table styling, high-contrast tokens, responsive grid, scrollable permanent/hand rows, readable non-color state labels, visible focus, reduced-motion rules. Legacy feature styles remain in a lower CSS layer.
- `frontend/src/components/Battlefield.tsx`: player/opponent orientation, phase track, life/resources/zones, card-face inspection and portal zoom, persistent keyboard inspection with Escape/focus return, status badges, grouped land member selection by exact ID. Creature lands stay among permanents. Non-hand casts and existing targets/costs/modes remain.
- `frontend/src/components/table-model.ts`: independently tested conservative land equivalence, authoritative mana metadata (no name-derived colors), identity retention, state labels and phase mapping.
- `frontend/src/components/Controls.tsx`: collapsible setup/playback/priority-stop settings, labeled fields, pass-priority disabled without the authoritative human action.
- `frontend/src/components/PermanentActions.tsx`: labels missing activation selections without changing payloads.
- `frontend/src/components/StackLog.tsx`: persistent counted top-first stack, collapsible five-event log with incremental expansion/collapse.
- `frontend/src/components/DeckPanel.tsx`: labeled deck fields and visible async request failures.
- `frontend/package.json`: table-model assertions included in `npm test`; no dependencies added.
- `frontend/tests/{browser-driver,browser-human-actions,browser-recovery,browser-simulation-preflight}.mjs`, `human-actions.tsx`, `simulation-preflight.tsx`: isolated origin overrides, inspection-safe selectors, actual production styles, recovery screenshots and simulator display coverage.
- `frontend/tests/{table-model,browser-ui-redesign,browser-ui-lab}.mjs`, `ui_fixture_server.py`: focused model, layout/keyboard/land/deck regression tests and isolated real-rules fixture setup.

No backend, API contract, gameplay rule, live database, root documentation or shared Graphify artifact changes. Existing source-relative data was isolated by copying tracked backend source into disposable local scratch before starting the fixture API. Fixtures use existing canonical cards, not invented cards; screenshots with absent media explicitly show text fallbacks rather than pretend card artwork.

## Actual validation

Final `npm test`, `npm run lint`, `npm run build`, and `git diff --check` all exited 0. Build: Vite 5.4.21, 44 modules; bundle 258.36 kB JS / 77.16 kB gzip, 22.03 kB CSS / 5.95 kB gzip.

Real headless Chromium runs (all exited 0):

- `node tests/browser-ui-redesign.mjs`: both human seats, canonical crowded boards, hidden opponent hand, 15-card scroll, pointer-driven exact-ID land tapping/persisted response, keyboard outline/Enter/Escape/focus return/Tab, reduced motion, laptop 1024px/mobile 390px/200% CSS zoom without page overflow, AI priority privacy/action gating, real scry choice and permitted library cast/stack, log expansion/collapse.
- `node tests/browser-ui-lab.mjs`: actual canonical `60 Swamp` import, persisted deck usable by both selectors, intercepted network failure visibly reported, base text/muted/gold token contrast against the lightest flat card surface (11.11:1 / 6.80:1 / 7.25:1).
- `node tests/browser-human-actions.mjs`: existing extensive real UI/API action suite, including seat two, targets, mana/alternative payments, X, modes/card faces, equip/crew/cycling-related controls, non-hand plays, mulligans, replacement/trigger choices, multi-block/trample/banding, priority/stack and next-game decisions. See full log for exact assertions, not a claim of all possible Magic rules coverage.
- `node tests/browser-recovery.mjs`: saved/diagnostic preview expansion, full App reload, overlapping land intents applied once, accepted-but-lost response reconciliation without write replay.
- `node tests/browser-recovery.mjs --verify-restart`: persisted session recovered after restarting only the disposable fixture API (performed before final presentation-only edits).
- `node tests/browser-simulation-preflight.mjs`: unsupported-mechanic review, refresh/poll/cancel, duplicate-start recovery, wrong-job rejection, styled completion/error display. Completion/error display is an explicitly injected component fixture, NOT an actual completed simulation result.

Reproduction environment used:

```sh
export MTG_FRONTEND_ORIGIN=http://127.0.0.1:15174
export MTG_BACKEND_ORIGIN=http://127.0.0.1:10200
export MTG_BROWSER_ORIGIN=http://127.0.0.1:19223
export MTG_UI_EVIDENCE=/home/nick/.hermes/cache/scratch/mtg-ui-arena-verification/evidence
# In frontend, with the isolated services already running:
npm test && npm run lint && npm run build
node tests/browser-ui-redesign.mjs
node tests/browser-ui-lab.mjs
node tests/browser-human-actions.mjs
node tests/browser-recovery.mjs
node tests/browser-simulation-preflight.mjs
```

Fixture API uses `PYTHONPATH=<disposable-copy>/backend:<worktree>/frontend/tests` and `python -m uvicorn ui_fixture_server:app --host 127.0.0.1 --port 10200`. The extension rejects ordinary checkout backend imports. Start Vite with `VITE_API_BASE_URL=http://127.0.0.1:10200 npm run dev -- --host 127.0.0.1 --port 15174 --strictPort`. Inspect port ownership first. Never point these fixtures at live backend source/data.

## Evidence

Archive: `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/ui-arena-inspired-20261004/`.

NFS mount verified (`192.168.8.132:/export/RCHFiles`), write/read/delete probe passed; all copied files SHA-256 verified against local originals. `manifest.json` records sizes/hashes. Logs: `gates.log`, `ui-browser.log`, `ui-lab.log`, `human-actions.log`, `recovery.log`, `restart.log`, `simulation.log`.

Screenshots in `evidence/`: `crowded-seat-1-desktop.png`, `crowded-seat-2-desktop.png`, `crowded-laptop.png`, `crowded-mobile.png`, `crowded-200-percent.png`, `long-hand.png`, `keyboard-inspection.png`, `active-choice-desktop.png`, `active-choice-mobile.png`, `active-choice-mobile-controls.png`, `active-stack-desktop.png`, `active-stack-mobile.png`, `deck-import-error.png`, `reconciled-api-error.png`. Representative screenshots were visually reviewed; spacing, card density and mobile choice discoverability were revised accordingly.

## Limitations and backend dependencies

- No requested backend contract changes. The UI depends on existing legal moves, pending choices, effective card fields, authoritative mana metadata and mutation reconciliation. Missing mana metadata is not guessed. No rules support is claimed beyond the existing backend; the human-action suite explicitly notes partially unsupported Saga chapter effects.
- Zoom tested through Chromium CSS zoom at 200%, not operating-system magnification or every browser's native zoom implementation. No Safari/Firefox or screen-reader certification. Contrast assertions cover base flat-surface tokens, not every image/pixel combination.
- Large boards and long hands intentionally scroll horizontally; small screens place the action rail below the table with an explicit pending-choice navigation link. Card art availability depends on the existing media API/cache.
- Selection/target labels reflect the current available legal-move metadata and local cast target selections; no new backend combat animation or targeting API was fabricated.
- `npm ci` baseline reported seven dependency vulnerabilities (one low, two moderate, four high). No blind audit fix or unrelated dependency upgrade performed.
- Disposable verification services/scratch may remain available for integrator inspection; do not remove active runtime files. Archived evidence is independent of those services.

## Independent coordinator verification

The coordinator reran `npm test`, `npm run lint`, `npm run build`, and `git diff --check a69233f..HEAD`; all exited 0. Using the disposable backend source and loopback fixture API, the coordinator also reran all five browser suites listed above (redesign, lab, human actions, recovery, simulation preflight); all exited 0. Restart recovery was not independently rerun. Desktop and mobile-choice screenshots were independently visually reviewed: no overlapping/clipped choice text; large boards intentionally require horizontal and vertical scrolling, and mobile checkbox targets remain small.

The original archive's 21 manifest entries were independently verified against their SHA-256 and size records. Fresh coordinator screenshots and checks are in the archive's `coordinator-evidence/`, copied only after NFS mount/write/read verification and hash-checked before deleting their disposable local originals. This does not claim integration with the concurrently changing backend on main.

## Integration

At review, `git diff --name-only a69233f..main -- frontend` was empty: no committed newer frontend changes were observed. This does not inspect or incorporate the original checkout's active uncommitted backend work. Cherry-pick the implementation commit onto the backend integrator's chosen base, reconcile any subsequently committed frontend changes, rerun gates and real browser suites against an isolated copy of integrated backend source, and then update shared Graphify/documentation. Do not merge/push main from this worktree. Graph/wiki index was absent; shared Graphify updates remain the backend integrator's responsibility.

Implementation commit: `282ae435524a7685386d8e71e4bb1c5ddd939765` (`feat(ui): build battlefield-first playtest table with verified interactions`). This follow-up handoff commit records that completed identifier; its own ID is discoverable with `git log -- docs/ui-redesign.md`.
