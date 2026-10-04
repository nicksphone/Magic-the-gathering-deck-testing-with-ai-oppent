# Competitive table v2

## Parent integration acceptance

The parent reviewed the presentation diff against its actual `d58dbec` base,
not by replacing current main with the older worktree. Its imported scope is
frontend presentation plus the new report/tests; no worker README, graph or
backend history was copied over newer main changes.

The v2 patch was merged into the final casting/trigger backend and frontend
source, retaining the new deliberate ordered-target renderer. Root unit/table
checks, ESLint and TypeScript/Vite build pass. The complete combined isolated
Chromium harness passes: v2 dense-board/cost checks, both-seat ordered targets,
all existing casting/combat/choice flows, recovery, process restart, sideboards,
natural AI BO3, human/AI BO3 and human/human BO3. The last flow makes more than
500 deliberate priority passes across both seats; it is not an optimal-deck test.

The parent independently verified all 40 original archived file hashes and
visually reviewed the artwork-led table. The combined empty-cache run exercises
honest offline fallback rather than borrowing worker JPEGs. New fixtures only
extend the disposable fixture API; production routes are unchanged.

Existing readiness checks now use stable mounted elements rather than hidden
saved-game text or CSS-capitalized headings. Recovery and preflight tests open
the workbench explicitly. Gameplay assertions are retained. Failed initial
fixture composition and the capitalization-selector run remain archived;
the corrected complete run is separately labeled. Browser CI now includes the
v2 checks and retains per-scenario timeout limits, with a 15-minute job budget
including dependency installation.

Parent combined evidence is in the verified casting-trigger archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/casting-trigger-repairs/20261004T222346Z/`.
The second redesign is deployed on the existing LAN frontend port 5173. Live
SQLite was not copied, migrated or written by these checks. Remaining manual
review: real long sessions, Firefox/screen-reader behavior, and the known
below-fold hand tradeoff on large boards.

## Inspection and implementation plan

Base: d58dbecf69765b2c22be81745b3c3ef1d7f5fc16. Scope: frontend presentation, new isolated tests, this report. No backend contract, dependency, shared graph or existing browser-test edits.

Before screenshots were captured from the actual disposable fixture API and Chromium, before coding. Baseline: management sidebar competes with play; player resources and hand fall below the fold even with two permanents; dense metadata reads as a debug record; lobby is an empty panel beside a narrow setup form; numerous equal-weight bordered boxes lack a spatial hierarchy.

Hierarchy: a compact masthead and workspace navigation; full-width two-sided felt table with engraved center line, distinct identity/zone bars, artwork-led permanents and a horizontally navigable hand tray; command area directly below the table, with stack alongside actions rather than management beside play. Lobby pairs editorial introduction with prominent matchup setup. Decks/import/history/simulator remain in a deliberately opened secondary workspace. Gold means priority/selection, not every border. Text labels remain authoritative, not inferred legality.

Connected chunks: (1) layout/lobby/workspace and command area, (2) table materials, seat identity, art and hand navigation, (3) isolated canonical stress fixtures and real browser checks, (4) gates, visual review, evidence archive and complete owned-process shutdown.

## Delivered presentation

- Full-width felt table; identity/life/zone clusters on the left, permanent rails in the center, land resources on the right. Mobile reflows these into a single column. Active turn and priority are labeled in text as well as color.
- No persistent management sidebar. Stack and command controls sit in a response workspace below the table, reachable through desktop sticky navigation and ordinary mobile anchors. Required choices get a prominent notice and their own command heading.
- Designed lobby pairs an editorial introduction with explicitly labeled seats, difficulty and match length. Start requirements are explained. Deck library/import, saved games and simulation/diagnostic tools are in the manually opened workbench; closing it restores navigation focus. Those components remain mounted, preserving their ongoing state.
- Real cached JPEG artwork, compact mana and effective-stat treatments, explicit tapped/target/attacker/blocker badges, original CSS materials rather than copied interface assets. Missing/failed images have an honest text fallback. No per-card lookup or alternate-image request loop.
- Named horizontal rails with previous/next buttons, native scrolling and individually retained card IDs. No virtualization, overlap hit-test ambiguity or shrinking dense boards into unreadable miniatures.
- Pinned inspection supports hand, permanents, land groups and public graveyard/exile cards. Available face metadata is inspectable without changing legal face selection. Escape restores the initiating focus. Transient previews do not intercept pointer actions; pinned previews have an explicit close control.

## Executed verification

Implementation commit: `6e7cdf23bd08aff65cd53d6cb76f739967e86e88`.

All commands ran in the isolated worktree. Runtime endpoints were exclusively owned ports **15174 / 10200 / 19223**, inspected before startup. Backend ran from a tracked-source copy under local scratch, with its own source-relative SQLite and image cache. The original main checkout and old v1 worktree were not modified.

| Command / check | Observed result |
| --- | --- |
| `npm test` | Passed API error/routing, match and simulation contract, mutation-gate and table-model suites |
| `npm run lint` | Passed |
| `npm run build` | Passed TypeScript and Vite production build; 46 modules |
| `git diff --check` | Passed |
| `node tests/browser-ui-v2.mjs` | Passed 13 recorded scenario groups in real Chromium |
| `node tests/browser-ui-v2-costs.mjs` | Passed six additional cost/ownership/pending-response groups |

Browser environment for those commands:

```sh
export MTG_BROWSER_ORIGIN=http://127.0.0.1:19223
export MTG_FRONTEND_ORIGIN=http://127.0.0.1:15174
export MTG_BACKEND_ORIGIN=http://127.0.0.1:10200
export MTG_UI_EVIDENCE=/path/to/local/evidence
```

Reproduction requires a **disposable copy** of tracked backend sources, plus `frontend/tests/ui_fixture_server.py` and `frontend/tests/ui_v2_fixture_server.py` copied into its `backend/tests/`. Run `python -m uvicorn tests.ui_v2_fixture_server:app --host 127.0.0.1 --port 10200` from that disposable backend, Vite with `VITE_API_BASE_URL=http://127.0.0.1:10200` and `--port 15174 --strictPort`, and a dedicated Chromium profile on 19223. Never run these fixtures from either live checkout. Optional fixture art uses six pre-cached `v2-<slug>.jpg` files; the archive contains those exact images and their source provenance. The test fixture does not fetch images.

Observed browser behavior:

- An actual app-started White Weenie/Burn human-vs-human match completed both keep-hand decisions and was read back from the API. This screenshot is distinct from constructed stress positions.
- Both human seats: **20 distinct land IDs**, **15 distinct permanent IDs**, **15 distinct hand IDs** verified programmatically. Every hand card was keyboard-opened and Escape-closed with restored focus; every permanent focused; every land selected by its ID. A specific untapped land was pointer-submitted, and only that ID became tapped in persisted state.
- Opposing hands remained hidden. When AI held priority, the human viewpoint stayed at seat one and AI plays were not exposed as human actions.
- Real canonical library cast, stack response and pending scry decision exercised. Scry disabled pass until the explicit choice was submitted.
- Both seats paid deliberate discard and sacrifice costs for Bone Shards; incomplete payments disabled cast; exact costs/targets and mana deductions were verified from the real API after resolution.
- Double land intent applied once. Full-page reload restored its persisted revision. A held real HTTP response disabled gameplay fieldsets. A dropped accepted response displayed an error and reconciled to revision one without replay.
- Cached JPEG images decoded successfully in the actual browser. Six images were fetched once into the disposable cache from Scryfall; source URLs/IDs and archived bytes are recorded. Offline fixture images are honestly unavailable, not fabricated art.
- Named rail navigation and pointer inspection, available face inspection, reduced motion, 1024×768 laptop, 390×844 narrow viewport and 200% CSS zoom checked. No page-wide horizontal overflow at those sizes. Cards scroll inside their named rails instead.

## Evidence and visual review

Verified archive:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/ui-redesign-v2/6e7cdf23/`

NFS final filesystem type was `nfs` (automount also reports `autofs`); write/read/delete probe succeeded. **40 files**, including **23 PNG screenshots**, were copied and SHA-256 verified before the stopped disposable runtime was deleted. `manifest.json` records paths, sizes and hashes.

Key review pairs and states:

- `before-table.png`, `before-lobby.png`: initial rendered inspection captured before coding. The initial lobby includes a stale-match recovery error from empty fixture storage; do not interpret that as v2 output.
- `baseline-commit-lobby.png`, `baseline-commit-table-art.png`: clean screenshots rendered from an isolated exact base-commit frontend snapshot after implementation, against the same canonical artwork fixture. These provide the comparable baseline without reverting or touching the working tree.
- `after-lobby.png`, `after-workbench.png`: lobby and secondary surfaces.
- `after-real-started-match.png`: actual app-created match, not an injected board.
- `after-table-art.png`, `after-table-offline.png`: constructed canonical table with real cached art and explicit offline fallback.
- `after-crowded-seat-1.png`, `after-crowded-seat-2.png`, `after-hand-tray.png`: constructed stress positions.
- `after-stack-response.png`, `after-pending-choice.png`: real engine stack/choice interactions after fixture setup.
- `after-inspection.png`, `after-face-inspection.png`: pinned inspection.
- `after-laptop.png`, `after-mobile.png`, their `-commands` variants and `after-200-percent.png`: responsive evidence.
- `after-reconciled-failure.png`: genuine intercepted-response failure feedback.
- `browser-final.log`, `v2-checks.json`, `frontend-gates.log`, `art-provenance.json`: execution evidence.

Actual screenshots were visually reviewed during iteration. Refinements included explicit setting labels, visible disabled-start explanation, compact mana/stats, larger mobile rail targets, a response-specific command heading, and de-emphasized technical stack effect keys. This is a spatial and interaction redesign, not simply a palette change.

## Preservation review and integration notes

The final diff leaves legal-move derivation, viewer-seat ownership, land grouping, casting/payment/face/target/mode payloads, activation/equip/crew controls, pending choices, cleanup, mulligans, BO3 callbacks, mutation gate, recovery implementation and simulator logic untouched. `PermanentActions` remains mounted with its original props. All original control handlers remain. Effective stats, damage, counters and unsupported-effect warnings remain visible. No API/type contract, backend, dependency, database, cache, deployment or existing browser-test source was changed. Shared Graphify output was deliberately not updated, per explicit ownership restriction.

Existing-test selector dependencies for the backend owner:

1. The workbench is now initially hidden. Tests waiting for `document.body.innerText.includes('Saved matches')` must first open `nav a[href="#lab-tools"]`, or wait for the actual app state they need rather than unrelated management text. Tests opening inner `.saved-games`/`.tool-disclosure` must also open the outer workbench.
2. Heading `Match Controls` is now `Command the turn` (or `Choose your matchup` without a match). Existing stable IDs `#table`, `#match-controls`, `#lab-tools`, `.hand-card`, `.cast-card-box`, `.land-members`, `.card`, `data-card-id` and `data-hand-card-id` remain.
3. Deck selects now have visible label wrappers. Select by their unchanged aria labels, not by direct-child assumptions.
4. Stack controller text is now `Controller Pn`; raw `effect_key` remains under `Effect details`. Gameplay action button labels are unchanged.
5. Some existing browser tests hardcode backend port 10199 despite the environment override. An attempted additional existing cost suite stopped immediately at `ECONNREFUSED` on that port; it was not modified or counted as passing. The new isolated v2 cost suite uses the explicit owned endpoint and passed. No protected service was started, stopped or restarted.

## Limits and remaining review

- Parent visual acceptance and the backend owner's full integrated rules/BO3 browser harness remain separate gates. These UI checks do not establish universal rules correctness or expert AI quality.
- Desktop and mobile use deliberate page scrolling for long hands, large public zones and complex action forms. The entire hand plus both battlefields is not guaranteed above the fold. Compact mana uses the engine's literal symbol notation, not licensed icon assets.
- 200% verification used Chromium CSS zoom/reflow, not a screen-reader audit or every OS/browser zoom implementation. All screenshot results are Chromium-specific.
- Fixture JPEG art is optional and not added to production assets. Production continues using its existing cache URLs. Dependency files are unchanged; the coordinator's baseline seven npm vulnerabilities were not remediated in this presentation-only task.

## Independent coordinator verification

The coordinator independently inspected the frontend diff and reran `npm test`, `npm run lint`, `npm run build`, `git diff --check d58dbec..HEAD`, `node tests/browser-ui-v2.mjs` and `node tests/browser-ui-v2-costs.mjs`; all exited 0. Browser execution used a fresh disposable backend source copy, its own local database/cache, the archived canonical JPEG artwork, and dedicated Chromium on the three owned loopback ports. Both seats retained all 20 land IDs, 15 permanent IDs and 15 hand IDs; exact-ID tapping, discard/sacrifice payments, pending guards, recovery and response failure checks passed. All 40 entries in the worker archive were independently checked against their recorded sizes and SHA-256 hashes.

Independent visual review found a coherent full-width table and clean lobby with no unintended overlap. Known presentation tradeoffs remain: the hand can fall below the desktop fold, small secondary labels are dense, and empty deck selectors currently read “Deck A/B” rather than explicitly “Select a deck.” The disabled-start explanation correctly requests two selections. These observations do not constitute universal accessibility or gameplay certification. The existing integrated browser harness still requires the backend owner's selector reconciliation described above.

Fresh coordinator screenshots/checks and shutdown proof are archived under the same archive's `coordinator-evidence/`. The coordinator stopped all its runtime process trees, independently verified no v2-owned processes remained and ports 15174/10200/19223 had no listeners, then hash-verified the NFS evidence copy before deleting its disposable backend/database/cache/browser scratch. Active source/dependencies were preserved.

## Owned files

Modified: `frontend/src/App.tsx`, `frontend/src/components/Battlefield.tsx`, `frontend/src/components/Controls.tsx`, `frontend/src/components/StackLog.tsx`, `frontend/src/styles/app.css`.

Added: `frontend/src/components/CardArt.tsx`, `frontend/src/components/CardRail.tsx`, `frontend/src/styles/competitive.css`, `frontend/tests/browser-ui-v2.mjs`, `frontend/tests/browser-ui-v2-costs.mjs`, `frontend/tests/ui_v2_fixture_server.py`, and this report.

## Runtime shutdown and cleanup

All owned runtime groups were stopped, including Vite, esbuild, fixture API, Chromium children, detached Chromium crash handlers and this worktree's auto-started TypeScript language-server children. No npm/sh/node preview child was left running.

`shutdown-proof.json` records **no remaining runtime processes** with the v2 worktree/disposable runtime cwd and all three ports closed: **15174, 10200, 19223**. Evidence was archived and verified before removing the disposable source copy, synthetic SQLite, image cache, browser profile and baseline snapshot. Active worktree source and installed dependencies remain for parent review. No merge, push or deploy was performed.
