# MTG Deck Testing Lab Finish Plan

Updated: 2026-09-27 UTC. Audited implementation: `6b95fab0875f4cc35cb9648f8a598be5b13b2c80`, branch `main`.

Latest implementation reconciliation: validation `01a0235`, recovery `a17712f`, and the permanent-spell context milestone described below. The [two-stage Jev review](docs/audits/2026-09-27-jev-two-stage-review.md) evaluates the older `f760c98` snapshot, not this latest implementation. Its typed judgments evaluate supplied evidence and proposed remedies; they are not application fixes or current release certification. The separate bounded [validation review](docs/audits/2026-09-27-api-validation-jev.md) records one authorized current-source call; no further calls were needed for the spell-context repair.

## Review reconciliation and next execution order

- **Draw/cleanup: core paths repaired.** Turn draws use the shared replacement-aware handler. Cleanup now has persisted human discard choices, ownership-correct shared discard events, discard-before-expiration ordering, deferred APNAP triggers, state-based checks and repeated cleanup. The GUI exposes draw/sacrifice/cleanup choices. Multiple interacting replacements, discard-replacement families and full browser/process-restart acceptance remain open.
- **Knowledge/AI: partially addressed.** `babef27` implements canonical all-card/corpus ingestion and rulings verification. Typed production AI consumers, offline supported-corpus certification and decision-quality evidence remain open.
- **Documentation: maintained, not reopened.** The finish-plan rewrite was already completed. Keep new evidence and limitations linked without presenting documentation as gameplay acceptance.
- **Local-beta repairs underway:** tracked offline fallback, shared live face hydration, effective public views, acting-seat controls and strict request validation are implemented with regressions. Fifteen Chromium action paths pass, including both BO3 play/draw choices; full human-game acceptance remains separate. Conventional permanent spells no longer execute later abilities. Modal face costs/timing, land-face plays, Adventure exile permissions, supported ETB/self-cast target choices and divided-damage recipient legality have bounded coverage. Non-damage multi-target resolution, broader face semantics and full face-specific restart acceptance remain open. Interactive BO3 now has bounded seed/play-draw tests; sideboard strategy and complete-series browser acceptance remain open.
- **Recovery implemented with bounded acceptance:** saved-match restore, serialized/versioned/idempotent guarded mutations, refresh, lost-response reconciliation and test-backend process restart have regression/browser coverage. Match creation recovery and extended soak remain open. Same-origin production routing, access/origin controls, bounded jobs and multiworker coordination are still network release gates. Refresh advisories before choosing dependency upgrades.
- **Simulator strength remains unverified.** The latest two-game BO3 smoke shows repeatability only; it does not measure broad balance or seasoned-player quality.

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

- [ ] Route turn draws, spell draws and cycling through replacement-aware shared operations.
- [x] Route cleanup discards through event-aware, ownership-correct operations.
- [x] Let humans choose cleanup discards and resume pending choices after snapshots.
- [x] Discard before damage removal/end-of-turn expiration, perform simultaneous cleanup, then handle state-based actions, triggers, priority and repeated cleanup.
- [x] Test cleanup repetition where resulting triggers require another priority window.
- [ ] Expand interacting draw/discard replacement and APNAP/replacement-order fixtures; complete process-restart and browser interaction acceptance.

Evidence: `test_cleanup_choices.py` covers seat-2 ownership, rejected choices leaving snapshots unchanged, choice reload, damage/pump clearing without an intervening SBA, shared discard ownership and trigger-driven repeated cleanup. A React server-render probe confirms all three mechanic-choice controls render for seat 2 and block priority advancement; it is not browser E2E. The deterministic replay runner now initializes its database before querying decks and runs independently of prior API/tests.

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
- [ ] Make match creation idempotent, validate successful response contracts, test extended disconnect/reconnect and rapid multi-window transitions, and enforce deployment-specific authorization/topology under steps 9/14.

Evidence: 822 backend tests pass (161.21 seconds, 798 warnings), including concurrent identical retries, stale/conflicting writes, restored revision/receipts and injected snapshot/commit failures with unchanged full game/database snapshots. HTTP match mutation history and snapshots commit together; memory rolls back on exceptions. `GET /matches` discovers incomplete restored matches. The UI stores only its selected ID, resumes authoritative state, pauses automatic play on restore/error, and uses one non-queuing mutation gate plus versioned write keys generated with HTTP-LAN-compatible `getRandomValues`.

The production build and frontend unit scripts pass. Chromium passes the six human-action paths plus full-App refresh/double-click, discarded-success-response reconciliation and actual backend-process-restart checks. These use an isolated fixture/database with production routes, not a complete human game. Retry receipts retain the latest 100 keys; matching retries return current authoritative state. Legacy headerless callers remain supported without stale-version protection. Network/multiworker deployment and new-match creation retries remain open.

Cast admission also distinguishes permanent spells from their later target-bearing abilities, preserves Aura attachment requirements and covers artifact/enchantment/land/general-permanent target availability. Unqualified land targets include both players' lands; supported controller qualifiers remain explicit. The modal-parser fixture now has its intended Sorcery type rather than retaining a setup Island's Land type. These checks do not certify ETB/effect timing. The post-change seeded BO3 has zero timeout/drift ([replay](docs/plans/baselines/2026-09-27-recovery-replay.json)).

Acceptance: refresh, backend restart, disconnect, double-click and autoplay/manual overlap do not lose a match or apply an action twice.

### 8. Share BO3 transitions and seed provenance (P2)

- [x] Preserve root/per-game seeds for newly started interactive matches and restored controller snapshots; next game uses `root_seed + game_number`, matching the diagnostic runner's seed schedule. Keep seeds out of active public responses so library order stays hidden. Legacy saved matches without a root seed remain explicitly unseeded.
- [x] Let the previous game's human loser choose play or draw; AI losers choose play by default. Validate the chooser before transition and expose both human choices in the GUI.
- [ ] Validate sideboard transitions end to end; implement deliberate AI sideboarding or label its absence. Add full-browser BO3, drawn-game policy and explicit legacy-seed migration tests.

BO3 increment evidence: 875 backend tests pass in a fresh isolated source/database copy (102.62 seconds, 812 deprecation warnings), including helper and HTTP choice/restore tests. Frontend TypeScript/Vite build and unit checks pass; fifteen isolated Chromium paths pass, including both play/draw buttons against the API. A two-game seeded Mono Red Aggro/Dimir Control diagnostic replay has no timeout, anomaly label or determinism drift; it does not exercise an entire interactive series or sideboard strategy.

Acceptance: repeated seeded interactive series and restarts agree when actions agree; game-two starts follow the documented policy and sideboards remain legal.

### 9. Add contract and frontend release gates (P2)

- [ ] Generate/share OpenAPI types and validate response payloads at runtime where needed.
- [ ] Correct block assignments to list-valued mappings and remove broad simulator/action `any` types.
- [ ] Configure ESLint with React-hooks checks, component tests and browser smoke tests.
- [ ] Add clean-checkout CI for backend tests, frontend build/lint/tests and an HTTP/UI flow.

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

- [ ] Default production routing to same-origin `/api` or explicitly require and validate a backend URL.
- [ ] Align card-media routing and remove implicit HTTPS-to-HTTP mixed-content behavior.
- [ ] Test the actual built artifact under HTTPS proxying `/api` and `/card-images`, plus configured cross-origin operation.

Acceptance: health/import/start/action/media work under both documented deployment modes; Vite development proxy success alone is insufficient.

### 15. Bound jobs and concurrent mutations

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
