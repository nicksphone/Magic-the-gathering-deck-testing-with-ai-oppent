# MTG Deck Testing Lab Finish Plan

Updated: 2026-09-27 UTC. Audited implementation: `6b95fab0875f4cc35cb9648f8a598be5b13b2c80`, branch `main`.

Latest implementation reconciliation: validation `01a0235`, recovery `a17712f`, and the permanent-spell context milestone described below. The [two-stage Jev review](docs/audits/2026-09-27-jev-two-stage-review.md) evaluates the older `f760c98` snapshot, not this latest implementation. Its typed judgments evaluate supplied evidence and proposed remedies; they are not application fixes or current release certification. The separate bounded [validation review](docs/audits/2026-09-27-api-validation-jev.md) records one authorized current-source call; no further calls were needed for the spell-context repair.

## Review reconciliation and next execution order

- **Draw/cleanup: core paths repaired.** Turn draws use the shared replacement-aware handler. Cleanup now has persisted human discard choices, ownership-correct shared discard events, discard-before-expiration ordering, deferred APNAP triggers, state-based checks and repeated cleanup. The GUI exposes draw/sacrifice/cleanup choices. Multiple interacting replacements, discard-replacement families and full browser/process-restart acceptance remain open.
- **Knowledge/AI: partially addressed.** `babef27` implements canonical all-card/corpus ingestion and rulings verification. Typed production AI consumers, offline supported-corpus certification and decision-quality evidence remain open.
- **Documentation: maintained, not reopened.** The finish-plan rewrite was already completed. Keep new evidence and limitations linked without presenting documentation as gameplay acceptance.
- **Local-beta repairs underway:** tracked offline fallback, shared live face hydration, effective public views, acting-seat controls and strict request validation are implemented with regressions. Fifteen Chromium action paths pass, including both BO3 play/draw choices; full human-game acceptance remains separate. Conventional permanent spells no longer execute later abilities. Modal face costs/timing, land-face plays, Adventure exile permissions, supported ETB/self-cast target choices and divided-damage recipient legality have bounded coverage. Non-damage multi-target resolution, broader face semantics and full face-specific restart acceptance remain open. Interactive BO3 now has bounded seed/play-draw tests; sideboard strategy and complete-series browser acceptance remain open.
- **Recovery implemented with bounded acceptance:** saved-match restore, serialized/versioned/idempotent guarded mutations, refresh, lost-response reconciliation and test-backend process restart have regression/browser coverage. Match creation now has durable same-key recovery, including lost-success-response retry and reload coverage. Extended soak remains open. A local self-signed HTTPS proxy smoke covers same-origin and configured cross-origin built artifacts in Chromium; a real LAN/trusted-certificate deployment remains untested. Access/origin controls, bounded jobs and multiworker coordination are still network release gates. Refresh advisories before choosing dependency upgrades.
- **Simulator strength remains unverified.** The latest two-game BO3 smoke shows repeatability only; it does not measure broad balance or seasoned-player quality.
- **Import analysis corrected:** curve buckets now come from cached mana costs (including front-face modal costs), with separate land/unknown counts; spell-color counts come from cached colors, and archetype analysis sees resolved metadata. These are not mana-source quality or AI-strength metrics. Full-deck strategy and mana-base validation remain open.
- **AI hand exposure closed for local play:** public match responses redact AI-controlled hands but preserve counts, and legal-move queries cannot expose AI card views. Human-vs-human remains a shared-device sandbox without per-seat authorization; separate-client hidden-information privacy is not implemented.
- **Land classification tightened:** game-state inference, rules legality, AI hand evaluation and deck-analysis land counts now use explicit front-face land types/type lines, with exact basic-name fallback for missing metadata. Mana production, Oracle text mentioning lands and land-name substrings cannot turn a nonland into a land. AI land priority selects only offered legal moves; missing nonbasic type metadata is a hydration/data issue, not permission to fabricate a play. Regression fixtures cover mana creatures, nonland card names containing a basic-land word, modal back-face lands, exact basics and malformed AI card IDs.
- **Deck-shape estimates aligned with layout:** cached modal/transform cards use front-face cost and creature type for archetype priors rather than treating every `//` name as split; back-face Land does not remove a cheap front spell. Canonical Valki, Delver and Bala Ged fixtures cover this boundary. Mana-base quality and strategic archetype inference remain open.
- **Replay attribution tightened:** a BO3 timeout is now classified from the timed-out game's log, not resolved games' errors. One fixed-seed Tempo/Dimir game reached turn 44 at the smoke test's 1,200-tick cap, but resolved on turn 65 at 1,836 ticks with a 3,000-tick cap. Its lone own-main pass with an actionable spell was not evidence of a stall. Repeated missed legal land drops across distinct turns remain a conservative `likely_stall` signal; statistical and full-game AI quality work stays open.

Verification for the land/diagnostics increment: 929 backend tests passed in an isolated source/database copy, including replacement of the obsolete fabricated-land and name-overrides-type expectations. The production-route browser harness passed all existing action, recovery and sideboard paths. A seeded Tempo/Dimir BO3 had zero replay drift; its 1,200-tick timeout was reported as `timeout_long_game` with one counted anomaly, while the timed-out first game resolved at 1,836 ticks under a 3,000-tick cap. This is not a broad matchup-strength or arbitrary-card rules certificate.
- **Live-game rules evidence:** a local-Oracle Ramp versus White Weenie scripted-human/AI API best-of-three completed through 200 HTTP calls (0-2, seed 19) with no rejected actions after the diagnostic translated display hints into typed requests. Its saved log has zero `not inferred` or missing-handler lines after the Recruitment Officer fix. This is not a browser game or balance estimate.

Next: broaden target legality beyond divided damage and bounded ETB/self-cast triggers, then sideboard/BO3 and frontend gates, maintaining draw/replacement and full-game acceptance coverage alongside changes. Keep network release gates mandatory before wider exposure; continue supported-corpus AI work after local correctness. All acceptance checkboxes below remain evidence-based.

Latest divided-damage checks: 871 backend tests pass in a fresh isolated source/database copy (103.37 seconds, 798 deprecation warnings); frontend production build and unit checks pass. A seeded Mono Red Aggro/Dimir Control BO3 completes two games in 36 turns with no timeout, anomaly label or determinism drift. The previous cast-trigger milestone passed thirteen human-action browser scenarios; this backend-only increment did not rerun those paths. These are bounded regression checks, not balance or expert-AI certification. Earlier full-App recovery checks cover refresh, lost response and test-backend process restart, not a complete game or production deployment.

## Release scope and status

First finish a reliable local desktop application for an explicitly supported card corpus. Arbitrary-card rules completeness and seasoned-player AI across every deck require additional acceptance criteria and remain longer-term goals.

The frontend compiles and the backend has substantial regression coverage. Human playtesting is not release-ready: general trigger target/mode windows, non-damage multi-target resolution, conditional land entry and full-game/BO3 acceptance remain unfinished. Bounded ETB/self-cast target windows, divided-damage legality and interactive BO3 seed/play-draw policy are implemented. Acting-seat controls, checked requests, canonical modal spell/land choices, Adventure exile permissions, responseable crew activation and saved-match recovery are implemented. Live hydration shares the face-aware helper, public views carry effective stats/faces, and hover shows base stats, damage, keywords and counters. Turn draws and cleanup discards share event-aware paths; cleanup choices are exposed in the GUI.

This plan supersedes the July status paragraphs and patch history previously stored here. Historical changes remain in `CHANGELOG.md`. The September audit is stored in [docs/audits/2026-09-27-app-audit.md](docs/audits/2026-09-27-app-audit.md). Its detailed evidence and reproduction artifacts are local at `/home/nick/.hermes/cache/scratch/mtg-audit-6b95fab/`; those artifacts are not portable repository fixtures.

## Evidence baseline

These are results reported by the supplied September audit, not checks rerun by the documentation update:

- Frontend `npm run build`: passed, including the configured TypeScript gate. TypeScript strict mode is already enabled.
- Tracked-source disposable checkout: backend suite had **718 passed, 2 failed**, 154 warnings. Both failures required an ignored generic token SVG. Copying the developer asset into scratch made the two focused tests pass; the full suite was not rerun after that copy.
- The pinned Python venv passed `pip check`. The obsolete TestClient incompatibility/stall did not reproduce. API tests must no longer be excluded on that historical basis.
- Frontend lint and test commands are absent. No tracked frontend CI workflow was found.
- Registry audit reported 7 vulnerable frontend packages: 4 high, 2 moderate, 1 low. Review current advisories before choosing upgrades; these counts do not establish shipped-bundle exploitability.
- One seeded Mono Red Aggro vs Dimir Control BO3 completed two logical games, 2-0, 30 total turns, without timeout or deterministic drift. This does not establish balance or optimal decisions.
- Runtime probes reproduced lost faces, base/effective stat disagreement, draw/cleanup event inconsistencies, malformed-request 500s, and the game-two starting-player issue. Render probes reproduced missing human-seat/action controls; browser E2E was not performed.
- No fresh dependency install, live LAN/HTTPS deployment, large matchup matrix, concurrency stress test, full Scryfall sync, or long-session browser test was performed.

Past zero-parser-fallback counts describe parser classification only. They are not current cache facts or proof that every effect clause is implemented correctly. Knowledge storage exists, but AI consumption and the broader knowledge plan remain unfinished.

## Working rules

- Keep rules, effects, legality, timing and AI in application code. SQL stores data only.
- Use canonical card data with provenance. Do not invent cards, text or stats to improve a matchup.
- Fix reusable mechanics and integration boundaries rather than one named-card exception.
- Read Graphify before source navigation; refresh it after code changes. Check graph freshness against the implementation revision.
- Preserve unrelated local files, databases and cache. Run database-writing release tests in a disposable tracked-source checkout, not merely a different working directory.
- Each completed task needs focused regression evidence, relevant integration coverage, documentation updates and a recorded revision. Leave checkboxes open until acceptance is demonstrated.
- Win rates are observations, not fixed targets. Never force all matchups into 65-70% bounds; report sample size, seats, seeds and confidence intervals.
- The token-compression experiment is not a dependency or a planned feature.

## Gate 1: Reliable local human-playtesting beta

Complete these steps in order. Steps 1-5 close the highest-impact reproduced failures before deeper AI work.

### 1. Make clean checkout assets reproducible (P1)

- [x] Ship or deterministically generate the generic token fallback outside the disposable image cache.
- [x] Serve offline card/token placeholders through the intended media contract.
- [x] Test release-candidate source with empty database/cache and declared dependencies; do not copy ignored developer assets.

Evidence: 758 backend tests pass after installing `requirements.txt` into a new venv and copying source without databases/image cache (159.21 seconds, 173 deprecation warnings). Generic-art HTTP and empty-cache/offline resolver tests pass using the tracked asset. Frontend production build passes. The final Git-archive/CI gate remains to be established under step 9; this test did not borrow ignored image files or the developer database.

Acceptance: full backend suite passes in a clean checkout; generic token media returns 200 without a pre-existing cache.

### 2. Unify live and diagnostic hydration (P1)

- [x] Use one hydration contract for live start, sideboarding, analytics and replay; transfer cached face data.
- [x] Expose necessary face metadata in public card views and preserve it through snapshots/restart.
- [x] Add HTTP regressions using a real modal/transform card and names/quantities-only decks.

Evidence: `test_release_card_contracts.py` checks HTTP names/quantities start, transformed views, snapshot resume and live/diagnostic parity. The HTTP fixture mocks persistence; it does not prove process-restart or browser face-choice workflows. Those remain Gate 1 acceptance requirements.

Cache-name increment: repository bulk lookups now prefer exact Oracle names and only scan face aliases when needed; art-series `Card` records do not supply playable-face aliases. A canonical `Mountain // Mountain` art-series regression checks that a requested basic Mountain hydrates and enters the game as a Land, independent of cache insertion order. Import and match-start admission now reject known art-series, token and emblem objects while retaining valid transform cards. Broader legalities and format-specific deck validation remain Gate 2 work.

Admission validation: 880 backend tests pass in a fresh isolated source/database copy (114.96 seconds, 826 deprecation warnings); frontend TypeScript/Vite build and unit checks pass. The backend-only increment did not rerun the browser harness.

Validation: 878 backend tests pass in a fresh isolated source/database copy (103.65 seconds, 814 deprecation warnings), and frontend TypeScript/Vite build and unit checks pass. The browser harness was not rerun for this backend-only cache change.

Acceptance: both faces survive HTTP start and restart; legal face selection and transformation work through UI controls with correct types and stats.

### 3. Expose truthful effective card views (P1)

- [x] Serialize printed/base and effective power/toughness separately, with counters, damage and effective keywords.
- [x] Display effective battlefield/hover stats consistently with combat resolution.
- [x] Cover counters, anthems, temporary pumps, characteristic-defined stats and cleanup expiration.

Evidence: view regressions cover counters, anthems, temporary-bonus/damage clearing, characteristic-defined and unknown stats, including snapshot reload. The frontend compiles with shared card types and the updated hover renderer. Browser visual verification and full cleanup timing remain open; helper expiration coverage is not a cleanup-order certificate.

Acceptance: UI and engine agree before and after reload for each fixture.

### 4. Share draw/discard event paths and choices (P1)

- [x] Route turn draws, spell draws and cycling through replacement-aware shared operations.
- [x] Route cleanup discards through event-aware, ownership-correct operations.
- [x] Let humans choose cleanup discards and resume pending choices after snapshots.
- [x] Discard before damage removal/end-of-turn expiration, perform simultaneous cleanup, then handle state-based actions, triggers, priority and repeated cleanup.
- [x] Test cleanup repetition where resulting triggers require another priority window.
- [ ] Expand interacting draw/discard replacement and APNAP/replacement-order fixtures; complete process-restart and browser interaction acceptance.

Evidence: `test_cleanup_choices.py` covers seat-2 ownership, rejected choices leaving snapshots unchanged, choice reload, damage/pump clearing without an intervening SBA, shared discard ownership and trigger-driven repeated cleanup. A React server-render probe confirms all three mechanic-choice controls render for seat 2 and block priority advancement; it is not browser E2E. The deterministic replay runner now initializes its database before querying decks and runs independently of prior API/tests.

Draw-path evidence: turn draws call `draw_cards`; spell draws and cycling reach the same handler. Canonical Thought Reflection fixtures cover one/two unconditional draw-doubling sources, per-original-draw choices, draw-step/HTTP choices, nested dredge pauses, snapshot resume and later effect clauses. Canonical Teferi's Ageless Insight/Alhammarret's Archive wording now excludes only the first actual draw in the affected player's own draw step; the successful-draw count survives snapshots, and Archive's life-gain clause applies independently of its draw clause. Existing cycling replacement tests also pass. Other conditional replacement families, alternative win/empty-library replacements, APNAP combinations and a complete browser/restart flow remain open under the second unchecked item.

Latest draw-replacement validation: 914 backend tests pass in an isolated source/database copy; a seeded two-game replay reports no timeout or determinism drift. Frontend build and unit checks pass. The loopback-only browser harness passes 19 paths, including a human choosing Thought Reflection over Stinkweed Imp and then choosing both nested draws. This is not a complete-game/browser-restart certificate.

Conditional draw/life replacement validation: 918 backend tests pass in an isolated source/database copy; frontend build and unit checks pass; all 19 loopback-only browser action paths pass. A seeded two-game BO3 resolves in 36 turns without timeout or determinism drift. This is focused rules and repeatability evidence, not broad conditional-replacement, full-game or balance certification.

Validation: full existing suite 762 passed after the final engine change; the five cleanup fixtures also pass, including the subsequently added cascading-SBA case. Frontend build passes. Clean standalone seeded BO3 (Aetherdrift Aggro/Karlov Manor Control) completes without timeout or drift. No arbitrary-card or balance certification is inferred.

Acceptance: equivalent draw/discard sources invoke the same applicable replacements/triggers; cleanup choices and restart resume are correct.

### 5. Render legal actions for the acting seat (P1)

- [x] Replace battlefield player-1 assumptions with explicit acting-seat ownership and human controller checks.
- [x] Drive controls from legal moves, including generic activation, crew, loyalty, cycling, equipment and permitted exile/top-library play.
- [ ] Provide target, mode, face, X-value, mulligan and cleanup choices needed by supported actions.
- [ ] Verify permanent cast effects cannot execute later activated/triggered text prematurely; select targeted ETB/cast-trigger choices in their actual ability window, not as spell targets.
- [x] Separate conventional permanent spell compilation from activated/triggered text, preserving Aura attachment and supported entry choices.
- [x] Add snapshot-safe human target selection for supported single-target ETB triggers after APNAP ordering, with resolution-time legality checks and no-target fallback; add separate resolution-time accept/decline for supported optional triggers. Other trigger families and multi-target work remain open.
- [x] Extend the same choice window to supported self-cast single-target triggers: target the ability after casting, resolve it before the spell and retain it if that spell is countered. Cast-only triggers no longer fire for a copy; modal/multi-target and other cast-trigger clauses remain open.
- [x] Recheck each recipient of supported divided-damage spells at resolution, preserve announced allocations for legal recipients, fail when all are illegal, and include distribution recipients in protection checks. Canonical Pyrotechnics tests cover zone changes, protection, hexproof, player targets and snapshot restore; other multi-target effect families remain open.
- [x] Pay crew tap costs at activation and resolve Vehicle animation through a counterable stack ability; preserve costs if crew creatures leave and track the same battlefield object across control changes. Vehicle-specific crew triggers/copy layers remain open.
- [x] Preserve canonical layout, selected modal spell characteristics and printed-identity restoration through stack resolution and snapshot codecs; verify differing costs/types and planeswalker stats.
- [x] Normalize both battlefield transform paths through the shared face adapter; canonical Kumano/Delver tests cover numeric stats, keywords and AI threat assessment. A real-card Mono Red Aggro/Burn interactive autoplay BO3 now completes after this crash fix; one 2-0 series is not matchup evidence.

Transform increment evidence: 877 backend tests pass in a fresh isolated source/database copy (103.11 seconds, 812 deprecation warnings); frontend TypeScript/Vite build and unit checks pass. The canonical-card interactive BO3 completed two games without a stall. Its first attempt used an erroneous ad-hoc face-first diagnostic loader and is excluded from gameplay conclusions; the corrected loader prefers exact Oracle names before face aliases. Neither run certifies AI quality.
- [x] Implement bounded modal land-face plays and Adventure resolve/exile/normal-face permissions with persistent snapshots, single-target failure checks, actor ownership separation, AI payload and human browser coverage.
- [ ] Complete conditional land entry, multi-target Adventure failures, split-card mechanics and broader face-specific process-restart/browser acceptance; backfill old cache layout from verified canonical data.

Land/Adventure evidence: [boundary fixtures and open cases](docs/testing/land-adventure-boundary.md) use canonical Bala Ged Recovery, Riverglide Pathway, Bonecrusher Giant and Brazen Borrower faces. The UI scenarios play a tapped land face and follow Stomp into exile and Bonecrusher Giant onto the battlefield. No entire-card Oracle or broad matchup-strength claim follows from these boundary checks.

Modal spell evidence: [boundary tests](docs/testing/modal-spell-faces.md) use actual Wandering Archaic / Explore the Vastlands, Valki / Tibalt and Delver Oracle metadata. Human browser scenarios cover the affordable back-face default and a deliberate switch with distinct cost. AI payload materialization and cast bias respect the offered spell face. Known transform-only backs are not direct cast choices. These do not certify full Oracle semantics or every face/permission family.

Spell-context evidence: canonical Oracle fixtures reproduce premature effects before the repair and pass afterward. Modern entry wording routes through supported ETB matching; ETB draw/destruction remains on a separate stack object. Supported single-target ETB and self-cast triggers now expose a human target choice after ordering and optional human accept/decline at resolution, with snapshot and browser coverage. Ulamog's cast trigger resolves before its creature spell and survives that spell being countered. Unattended choices remain deterministic; other trigger/ability semantics remain open. See [bounded contract](docs/testing/targeted-trigger-choices.md).
- [x] Show an explicit warning for any legal action kind without an implemented control.

Evidence: [browser harness and reproduction](docs/testing/human-actions-browser.md) exercises the actual Battlefield component and production API action handlers in an isolated database: seat-2 land, targeted permanent activation, crew selection and response window, exile spell and top-library creature. This is not a full App onboarding/game/recovery E2E. Generic abilities expose advanced JSON for less common choice contracts; polished multi-choice/mulligan/face coverage remains open. Shared extraction now retains adjacent mana symbols, targets validate before costs and unsupported variable activated costs are excluded. [Crew timing tests](docs/testing/crew-stack-timing.md) cover the core stack boundary, not every Vehicle-specific trigger or layer interaction.

Validation: 768 backend regressions pass in a tracked-source copy with initially empty database/cache and existing pinned dependencies; the TypeScript/Vite build also checks the browser harness. Five Chromium action scenarios pass. No fresh dependency install, full browser game or network deployment is claimed.

The [seeded Aggro/Dimir BO3 smoke replay](docs/plans/baselines/2026-09-27-human-actions-replay.json) completes two games without timeout or deterministic drift. This is repeatability evidence, not a matchup-balance or expert-AI measurement.

Acceptance: complete human-vs-human and human-vs-AI flows through UI; seat 2 can act, crew a Vehicle, activate an ordinary ability and play a permitted exile card. No silent legal-action omissions.

### 6. Validate API requests before mutation (P2)

- [x] Define bounded typed deck entries and discriminated action/choice contracts.
- [x] Reject malformed quantities, missing fields, invalid player/card IDs and unsupported actions with structured 4xx responses.
- [x] Define explicit sandbox deck-size policy separately from malformed-input validation.
- [x] Verify rejected external actions leave authoritative game state and persisted snapshots unchanged through copy-on-write execution.
- [x] Commit accepted match mutations, history and snapshots together and roll back memory on persistence failure; retain durable revision/idempotency metadata for the versioned UI write path.

Evidence: 806 backend tests pass in an isolated source/database copy (120.05 seconds, 548 deprecation warnings). Malformed HTTP payloads, invalid actor/source/face/cost/target choices, failed loyalty payments, duplicate concurrent land requests, combat restrictions, and deliberate London mulligan bottoms have regression coverage. Normal mainboards require 60-250 cards; explicit sandbox permits 1-250, never empty. The 250 cap is an application resource limit, not a Magic maximum. Live and batch admission resolve name/quantity entries through cached/canonical metadata. See [input contracts](docs/api/input-contracts.md).

Frontend production build, seven error-message assertions and six Chromium component/HTTP paths pass. A seeded Mono Red Aggro/Dimir Control BO3 finishes two games without timeout or drift ([replay](docs/plans/baselines/2026-09-27-api-validation-replay.json)). Human seat 2 can explicitly select ordered London bottoms; mulligans may continue to a zero-card opening hand. This does not establish full-game browser acceptance, arbitrary-card target semantics, fresh dependency installation or expert AI.

One fresh, authorized Jev request judged the scoped rejection, storage/topology/target limits and next-work direction against current working-source excerpts. [Review provenance and limits](docs/audits/2026-09-27-api-validation-jev.md). No database contents were supplied; the credential was used only in the authorization header, not evidence or archives.

Acceptance: missing/negative/oversized inputs and stale IDs cannot cause internal 500s or invalid games. Fuzz meaningful action families.

### 7. Restore matches and coordinate UI mutations (P2)

- [x] Add saved active-match discovery/resume and persisted frontend selection.
- [x] Add visible errors, bounded request timeouts and revision-checked state/legal-move reads.
- [x] Serialize manual/autoplay/response-window mutations and guard duplicate clicks.
- [x] Reconcile authoritative state before retrying when a write result is lost; persist revision and bounded idempotency receipts.
- [x] Make match creation idempotent with a durable receipt and same-key frontend retry/reload recovery.
- [ ] Validate remaining successful response contracts, test extended disconnect/reconnect and rapid multi-window transitions, and enforce deployment-specific authorization/topology under steps 9/14.

Evidence: 822 backend tests pass (161.21 seconds, 798 warnings), including concurrent identical retries, stale/conflicting writes, restored revision/receipts and injected snapshot/commit failures with unchanged full game/database snapshots. HTTP match mutation history and snapshots commit together; memory rolls back on exceptions. `GET /matches` discovers incomplete restored matches. The UI stores only its selected ID, resumes authoritative state, pauses automatic play on restore/error, and uses one non-queuing mutation gate plus versioned write keys generated with HTTP-LAN-compatible `getRandomValues`.

The production build and frontend unit scripts pass. Chromium passes the human-action paths plus full-App refresh/double-click, discarded-success-response reconciliation and actual backend-process-restart checks. These use an isolated fixture/database with production routes, not a complete human game. Mutation retry receipts retain the latest 100 keys; matching retries return current authoritative state. Legacy headerless callers remain supported without stale-version protection. Network/multiworker deployment remains open.

Creation-retry increment: `POST /matches/start` now persists a bounded start key and request fingerprint atomically with the new match snapshot. Concurrent same-key requests return one match; changed payloads conflict, and retry after losing the in-memory controller restores only that match. The frontend retains the pending key/payload until a match and its legal moves load, retries ambiguous responses, and recovers after reload. HTTP and Chromium regressions cover both lost-response paths. This is local single-process durability, not multiworker coordination or long-session certification.

Repeated Start clicks after an ambiguous failure reuse the pending request rather than creating a new key; the browser harness verifies this path. Simultaneous fresh starts from separate windows are still outside this local single-process acceptance.

Verification: 922 backend tests passed in an isolated source/database copy; the final recovery-file rerun passed 14 tests after adding a database rollback assertion. Frontend build, lint and unit checks passed. The loopback browser harness passed its 19 action paths, three existing recovery paths and two new ambiguous-start paths. One seeded BO3 replay completed two games with zero determinism failures. These checks do not certify full-game UI play, balance or multiworker safety.

Cast admission also distinguishes permanent spells from their later target-bearing abilities, preserves Aura attachment requirements and covers artifact/enchantment/land/general-permanent target availability. Unqualified land targets include both players' lands; supported controller qualifiers remain explicit. The modal-parser fixture now has its intended Sorcery type rather than retaining a setup Island's Land type. These checks do not certify ETB/effect timing. The post-change seeded BO3 has zero timeout/drift ([replay](docs/plans/baselines/2026-09-27-recovery-replay.json)).

Acceptance: refresh, backend restart, disconnect, double-click and autoplay/manual overlap do not lose a match or apply an action twice.

### 8. Share BO3 transitions and seed provenance (P2)

- [x] Preserve root/per-game seeds for newly started interactive matches and restored controller snapshots; next game uses `root_seed + game_number`, matching the diagnostic runner's seed schedule. Keep seeds out of active public responses so library order stays hidden. Legacy saved matches without a root seed remain explicitly unseeded.
- [x] Let the previous game's human loser choose play or draw; AI losers choose play by default. Validate the chooser before transition and expose both human choices in the GUI.
- [ ] Validate sideboard transitions end to end; implement deliberate AI sideboarding or label its absence. Add full-browser BO3, drawn-game policy and explicit legacy-seed migration tests.

Bounded sideboard transition: the API now shows current mainboard/sideboard quantities for human-controlled seats only between games, rejects completed-match and AI-seat manual swaps, and preserves an applied swap through restore into game two. The UI displays that inventory, limits manual selection to human seats and disables duplicate submission. An HTTP regression checks exact next-game card counts and rejected writes against memory/database snapshots; a loopback browser path submits a real basic-land swap, reloads and verifies game two. This is not a complete played BO3 or AI sideboarding strategy, so the combined checkbox remains open.

Verification: 923 backend tests passed in an isolated source/database copy. Frontend build, lint and unit checks passed. The loopback browser harness passed its existing action/recovery paths plus the new sideboard transition and seat-switch draft-clearing checks. Hosted CI run `36372772663` passed all three jobs.

BO3 increment evidence: 875 backend tests pass in a fresh isolated source/database copy (102.62 seconds, 812 deprecation warnings), including helper and HTTP choice/restore tests. Frontend TypeScript/Vite build and unit checks pass; fifteen isolated Chromium paths pass, including both play/draw buttons against the API. A two-game seeded Mono Red Aggro/Dimir Control diagnostic replay has no timeout, anomaly label or determinism drift; it does not exercise an entire interactive series or sideboard strategy.

Acceptance: repeated seeded interactive series and restarts agree when actions agree; game-two starts follow the documented policy and sideboards remain legal.

### 9. Add contract and frontend release gates (P2)

The frontend now checks live match responses for core fields, both player views, required card-view fields and list-valued block assignments. Unit regressions reject malformed payloads, and a backend-serialized match passed the validator. This is partial boundary coverage, not generated OpenAPI types or full response validation.
Legal-move responses now also validate the acting seat, nonnegative revision, move discriminator and optional card-view/choice-list shapes. Unit tests reject malformed examples, and the loopback browser harness accepts production API responses across its action/recovery paths. Other successful API responses still need boundary contracts.
Saved-match discovery now checks IDs, modes, turns, game numbers, revisions and two player names; malformed summaries fail before recovery selection. Unit cases and the production-route browser recovery fixture pass. Deck import and the rest of the API still need generated/shared contracts and selective runtime validation.
The Testing Simulator job-status boundary also validates progress and completed summary metrics, and its `any` result cast is removed. Diagnostic run payloads and other API responses still need generated/shared contracts and selective runtime validation.

A clean-checkout GitHub Actions baseline installs declared Python and locked npm dependencies, then runs the backend suite, frontend build, lint and frontend unit checks. Browser-flow gates were added later and are described below. The final frontend `any` casts for Vite environment access and start-mode selection were removed; `ImportMeta` now uses Vite's client declaration. A disposable frontend copy passed `npm ci`, build and unit checks locally; a separate fresh Python venv passed seven API smoke tests.

ESLint checks TypeScript and React hooks in `src`, with the shared autoplay, response-pass, deck-refresh and legal-move dependencies corrected rather than suppressed. A fresh `npm ci` copy passes lint, build and unit checks; the local browser harness passes 19 action paths plus App refresh, ambiguous-write recovery and backend-process restart. The updated hosted gates are verified below.

A separate browser CI job uses the existing production Controls/API and App recovery fixtures against a temporary backend copy, including an actual process restart. Hosted run `36370371065` passed 918 backend tests, frontend build/lint/unit checks, all 19 browser action paths and three recovery checks. Chrome is used on the hosted runner because its Chromium binary did not expose the CDP port. This is not a complete human game or BO3.

- [ ] Generate/share OpenAPI types and validate response payloads at runtime where needed.
- [x] Correct block assignments to list-valued mappings and remove broad simulator/action `any` types.
- [x] Configure ESLint with React-hooks checks and production-component browser smoke tests.
- [x] Add clean-checkout CI for backend tests, frontend build/lint/tests and an HTTP/UI flow.

Acceptance: malformed block/card-view payloads fail contract tests; regressions cover steps 1-8. Do not add a redundant task to enable existing TypeScript strict mode.

Gate 1 exit: empty cache/database setup can import a supported deck, play both advertised human modes, choose mulligans/targets/responses/cleanup, complete combat and a BO3, sideboard, reload/restart and resume. All configured gates pass without developer-only assets; bad inputs return 4xx.

## Gate 2: Trustworthy supported-corpus simulator

September 27 engine increment: dedicated core handlers for Infect/Wither/Toxic, Ninjutsu, Annihilator, Escape, Prototype and optional Dredge; persisted mechanic choices and spell continuations; draw-step replacement routing; ability-versus-spell cast events. This does not complete corpus certification. Next: expose new actions/choices to humans, unify canonical live hydration, validate interacting replacements and first-strike windows, then implement Morph/Manifest, Suspend, Discover, Battle protectors/defense, Mutate, Craft and Banding in separately tested increments. Contracts and remaining limits: [docs/rules/expanded-keywords.md](docs/rules/expanded-keywords.md).

### 10. Verify corpus and finish knowledge consumers

- September 27 ingestion milestone: reusable all-Oracle bulk import, exact-name/search rulings verification and a knowledge gap report are implemented. The first local import contains 38,690 unique Oracle records and 6,433 faces; bulk records explicitly await rulings verification. Data remains local and is rebuildable from the official source. Tactical profiles, AI consumers, verified offline seeds and full rules coverage remain open.
- Corpus verification now covers 88 requested names with zero missing metadata or pending rulings (87 canonical records). The full bulk reimport leaves all 38,690 records unchanged. See `docs/plans/baselines/2026-09-27-card-knowledge.json` for the evidence summary.

- [ ] Freeze and publish the supported corpus and per-mechanic coverage limits.
- [ ] Sync canonical data/rulings with provenance; use verified offline seeds and report incomplete metadata honestly.
- [ ] Reconcile [the knowledge implementation plan](docs/plans/2026-09-09-ai-knowledge-base.md) with current code before carrying forward its historical cache counts.
- [ ] Implement tactical profiles, AI consumers and measured matchup priors; storage alone does not complete knowledge integration.
- [ ] Surface unsupported/ambiguous semantics before simulation instead of silently approximating them.

Acceptance: corpus completeness and AI profile consumption are reproducible, including offline mode. Do not require nonempty rulings when the authoritative card legitimately has no rulings.

### 11. Validate semantics across rule families

- Recruitment Officer's canonical mana-value-limited top-four reveal and Militia Bugler's power-limited variant share a resolution-time handler. A human may select a qualifying creature or reveal none after snapshot restore; HTTP legal-move/action coverage reaches the same choice. Live/replay AI now uses the pending choice with contextual ranking; direct effect calls retain deterministic fallback. Remaining cards go to the library bottom in RNG-backed random order where Oracle text says so. The earlier Recruitment Officer test used altered card text and has been corrected. Other top-library families remain to audit.
- Supported creature/permanent topdeck battlefield effects no longer peek at hidden candidate cards during cast/legal-move generation. Human and AI selection occurs after resolution inspects the then-current library; human choices permit zero through the printed up-to count, survive snapshots and complete the paused stack item. AI ranks free battlefield value rather than taking the first eligible card; one focused regression checks this, not broader strategic quality. Focused canonical Collected Company/Storm the Festival fixtures cover changed library order, choice bounds and random-order bottom placement using persisted RNG; a Thought-Knot Seer boundary verifies `{C}` in creature mana value. Supported "any order" clauses now pause for a second ordered human bottom choice, preserve zone consistency, and finish the stack item only after that choice; focused and browser tests cover Collected Company. Broader clauses remain open.
- Expressive Iteration-style hand/exile/bottom placement inspects cards only at resolution. Human ordered choice pauses and resumes the stack across snapshots; live/replay AI chooses a ranked hand card and exile card through the same legal move. The exile-play expiry uses the resolution turn. Focused tests cover hidden cast hints, duplicate rejection, changed library order, HTTP actions and a production Controls browser path.
- Supported library-search effects now expose candidate cards at resolution, not during cast. The human chooser survives snapshot/stack continuation, supports failing to find a restricted hidden-zone card, and is exercised through the Controls/API browser path. Live and batch AI controllers now use the same pending choice and rank needed mana colors and near-term card value; a snapshot regression checks the choice, but broad tutor decision quality remains open. Inferred one-card tutors no longer take every matching card. A corrected canonical Cultivate fixture verifies ordered split placement (first land tapped on battlefield, second into hand) rather than the earlier altered hand-only text. Other search wordings and full clause fidelity remain open.
- Tutor-choice validation: 902 backend tests passed in an isolated source/database copy before the legacy-snapshot migration edit; 24 focused recovery/search tests passed after it. Frontend build/unit checks passed. A seeded two-game replay completed without timeout or determinism drift. These checks establish regression stability, not optimal tutor strategy.
- Generalized library-choice validation: 905 backend tests passed in an isolated source/database copy, followed by 27 focused library-choice tests after adding the old-snapshot-key compatibility assertion. A seeded two-game replay completed without timeout or determinism drift. No complete browser game or broad AI decision-quality matrix was run for this change.
- AI mechanic-choice audit found that the generic sacrifice ordering could discard lands before tokens and that unattended cleanup discarded the first hand cards. Sacrifice now ranks token/board loss and protects mana sources; cleanup uses a persisted AI choice and a hand-retention heuristic. Focused regressions cover both. These are bounded tactical heuristics, not optimal play or broad discard-synergy coverage.
- Mechanic-choice validation: 907 backend tests passed in an isolated source/database copy; a seeded two-game replay resolved in 40 turns with no timeout or determinism drift. Frontend code was unchanged for this increment; no browser full-game run was performed.
- The September inventory in `docs/plans/baselines/2026-09-27-mechanics-inventory.json` identifies additional gap candidates: Morph (153 cards), Suspend (74), Infect (49), Ninjutsu (37), Mutate (34), Discover (33), Escape (33), Banding (26), Craft (24), Prototype (21), Dredge (14), Manifest (68) and Annihilator (15). Battle metadata covers 39 cards; protector/defense behavior still needs implementation. These are data inventory counts and code-audit candidates, not exhaustive coverage certification. Supplemental, digital and novelty cards are also present in bulk data and require explicit format/scope handling.

- [ ] Add golden fixtures for full clauses, costs, modes, targets, attachments and zone permissions.
- [ ] Expand continuous layer/dependency, replacement/prevention ordering and can't-override fidelity.
- [ ] Cover simultaneous state-based actions, APNAP trigger choices and resumable nested effects.
- [ ] Test live HTTP and diagnostics against shared fixtures; parser classification alone cannot satisfy this task.

Acceptance: expected zones, choices, stats, timing, triggers and outcomes match fixtures and replay/restart state.

### 12. Measure and improve decisions across archetypes

- [ ] Establish per-archetype before/after decision metrics using full hand/board/legal-action traces.
- [ ] Evaluate land drops, mana sequencing, lethal opportunities, bad attacks/blocks, engine protection and interaction windows.
- [ ] Extend bounded multi-turn planning, hidden-information estimates and sideboard plans using demonstrated mistakes.
- [ ] Cover control, tempo, aggro, ramp, tokens, tribal, midrange, drain and combo-style decks rather than tuning one archetype alone.

Acceptance: each AI change has concrete decision evidence and regressions; no strength claim based only on completing games or winning a small sample.

### 13. Run seeded matrices and replay/restart gates

- [ ] Predefine sample sizes, seed schedule, seat balancing and long-game timeout policy.
- [ ] Run representative then full supported-corpus BO3 matrices, retaining detailed anomalous-game traces.
- [ ] Report confidence intervals, rules/cost/target errors, illegal attempts and explained timeouts.
- [ ] Validate deterministic replay and snapshot restart equivalence, with first-divergence drilldown.

Gate 2 exit: no unexplained supported-corpus rules/cost/target stalls; reproducible replay/restart; measured decision improvements and transparent uncertainty. Small deterministic smoke results remain smoke evidence.

## Gate 3: Packaged release and operational hardening

### 14. Test production API and media routing

- [x] Default production routing to same-origin `/api`; keep an explicit backend-origin override.
- [x] Align card-media routing and remove implicit HTTPS-to-HTTP mixed-content behavior from the default.
- [x] Test the built artifact under a local HTTPS proxy for `/api` and `/card-images`, then rebuild for a separately configured HTTPS backend origin.

Evidence: `frontend/tests/production_proxy_smoke.py --browser --cross-origin` passed in a disposable backend checkout with empty initial SQLite/cache and a temporary self-signed certificate. Both modes passed Chromium `Backend online`/deck loading and HTTPS health, import, match start/action and media requests. Frontend build/unit checks pass. The script restores the default build. This does not prove a real trusted-certificate LAN deployment, multiuser security or long-session behavior.

Acceptance: health/import/start/action/media work under both documented deployment modes; Vite development proxy success alone is insufficient.

### 15. Bound jobs and concurrent mutations

Single-process batch admission now shares one slot across synchronous and background-job routes. A second request gets structured 429, and failure paths release the slot. This does not provide a queue, cancellation, retention, multiworker coordination or network authorization; the larger job-control checkbox remains open.
The in-memory simulator history is now capped at 20 terminal jobs while old result lookups fall back to SQLite. Startup loads only recent rows plus unfinished jobs, which are marked failed after restart. Durable database retention, cancellation and quotas remain open.

- [ ] Define single-process local topology and network exposure policy explicitly.
- [ ] Add bounded job queues/quotas, cancellation, retention and documented crash/restart behavior.
- [ ] Add per-match locking/versioning and stale-write checks; test simultaneous actions.
- [ ] Add authentication/authorization and restricted origins before supporting network access beyond a trusted single-user setup.
- [ ] Upgrade vulnerable dependencies deliberately against current advisories; retest without blind forced upgrades.

Acceptance: mutations cannot corrupt concurrent state; job floods remain within measured limits; network authorization/origin policy matches the documented deployment. Keep development servers private during this work.

### 16. Verify installation and long-session operation

- [ ] Test clean-machine dependency install, offline fallback and backup/restore.
- [ ] Test backend restart recovery and supported worker topology.
- [ ] Run browser soak tests, accessibility/error-boundary checks and replay inspection flows.
- [ ] Reconcile README features/limitations, changelog and Graphify with final verified behavior.

Gate 3 exit: reproducible install, HTTPS/API/media smoke, bounded jobs, restart/data recovery, long-session usability and dependency/security review all pass.

## Completion and reporting

Work remains open until its acceptance evidence is recorded. A milestone report must include changed files, checks and artifacts, remaining risks and manual-review needs. This documentation update does not close any implementation checkbox.

The scoped release is finished only after all three gates pass. Any remaining unsupported mechanics must be explicitly visible and documented. Full Magic rules completeness and arbitrary-deck expert AI are not implied by that scoped release.

## Known Limitations and Next Upgrades

Start with Gate 1 steps 1-5, then input/recovery/BO3/contracts. The current priority is reliable human play over deeper search or cosmetic polish. Broader rules fidelity, knowledge-driven AI, statistical validation and operational release checks follow in Gates 2 and 3.
