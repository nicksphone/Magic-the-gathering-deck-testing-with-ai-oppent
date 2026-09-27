# MTG Deck Testing Lab Finish Plan

Updated: 2026-09-27 UTC. Audited implementation: `6b95fab0875f4cc35cb9648f8a598be5b13b2c80`, branch `main`.

Latest implementation reconciliation: `b4eba86`. The [two-stage Jev review](docs/audits/2026-09-27-jev-two-stage-review.md) evaluates the older `f760c98` snapshot, not this latest implementation. Its typed judgments evaluate supplied evidence and proposed remedies; they are not application fixes or current release certification. No new paid API calls were made to reconcile it.

## Review reconciliation and next execution order

- **Draw/cleanup: partially addressed.** `b4eba86` routes turn draws through the shared replacement-aware handler and adds persisted Dredge choices/continuations. Cleanup still needs deliberate discard selection, ownership/events, discard-before-expiration ordering, simultaneous damage/effect cleanup, priority and repeated cleanup. Multiple interacting replacements remain open.
- **Knowledge/AI: partially addressed.** `babef27` implements canonical all-card/corpus ingestion and rulings verification. Typed production AI consumers, offline supported-corpus certification and decision-quality evidence remain open.
- **Documentation: maintained, not reopened.** The finish-plan rewrite was already completed. Keep new evidence and limitations linked without presenting documentation as gameplay acceptance.
- **Local-beta repairs underway:** tracked offline fallback, shared live face hydration and effective public views are implemented with regressions. Broader UI acceptance remains separate. Both human seats/all legal actions, strict request validation, BO3 transitions and frontend contract/test gates remain open.
- **Recovery and network gates remain open:** refresh/restart resume, serialized/idempotent mutations, same-origin production routing, access/origin controls and bounded jobs. Refresh advisories before choosing dependency upgrades; the historical scan is not a current exploitability assessment.
- **Simulator strength remains unverified.** The latest two-game BO3 smoke shows repeatability only; it does not measure broad balance or seasoned-player quality.

Execute steps 1-3 first (offline assets, unified hydration, truthful views), then steps 4-6 (cleanup, acting-seat controls, validated mutations), followed by recovery/BO3/frontend gates with regression tests alongside each change. Keep network release gates mandatory before wider exposure; continue supported-corpus AI work after local correctness. All acceptance checkboxes below remain evidence-based.

Latest checks at `b4eba86`: 753 backend tests pass in an isolated copy **with local image assets**, frontend build passes, seeded Aggro/Dimir BO3 has no timeout or determinism failure. Fresh dependencies, empty-cache tracked-only acceptance and browser/network flows were not validated by those checks.

## Release scope and status

First finish a reliable local desktop application for an explicitly supported card corpus. Arbitrary-card rules completeness and seasoned-player AI across every deck require additional acceptance criteria and remain longer-term goals.

The frontend compiles and the backend has substantial regression coverage. Human playtesting is not release-ready: the UI omits the second human seat and legal actions, and cleanup bypasses supported discard events/choices. Live hydration now shares the face-aware helper, public card views carry effective stats/faces, and hover shows base stats, damage, keywords and counters. Turn draws use the replacement-aware effect path. Browser integration and broader acceptance remain open.

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

Acceptance: both faces survive HTTP start and restart; legal face selection and transformation work through UI controls with correct types and stats.

### 3. Expose truthful effective card views (P1)

- [x] Serialize printed/base and effective power/toughness separately, with counters, damage and effective keywords.
- [x] Display effective battlefield/hover stats consistently with combat resolution.
- [x] Cover counters, anthems, temporary pumps, characteristic-defined stats and cleanup expiration.

Evidence: view regressions cover counters, anthems, temporary-bonus/damage clearing, characteristic-defined and unknown stats, including snapshot reload. The frontend compiles with shared card types and the updated hover renderer. Browser visual verification and full cleanup timing remain open; helper expiration coverage is not a cleanup-order certificate.

Acceptance: UI and engine agree before and after reload for each fixture.

### 4. Share draw/discard event paths and choices (P1)

- [ ] Route turn draws, spell draws and cycling through replacement-aware shared operations.
- [ ] Route cleanup discards through event-aware, ownership-correct operations.
- [ ] Let humans choose cleanup discards and resume pending replacements/choices after snapshots.
- [ ] Discard before damage removal/end-of-turn expiration, perform simultaneous cleanup, then handle state-based actions, triggers, priority and repeated cleanup.
- [ ] Test trigger ordering and cleanup repetition where resulting triggers require another priority window.

Acceptance: equivalent draw/discard sources invoke the same applicable replacements/triggers; cleanup choices and restart resume are correct.

### 5. Render legal actions for the acting seat (P1)

- [ ] Replace player-1 assumptions with explicit acting-seat ownership and human controller checks.
- [ ] Drive typed controls from legal moves, including generic activation, crew, loyalty, cycling, equipment and permitted exile/top-library play.
- [ ] Provide target, mode, face, X-value, mulligan and cleanup choices needed by supported actions.
- [ ] Show an explicit warning for any supported legal action without an implemented control.

Acceptance: complete human-vs-human and human-vs-AI flows through UI; seat 2 can act, crew a Vehicle, activate an ordinary ability and play a permitted exile card. No silent legal-action omissions.

### 6. Validate API requests before mutation (P2)

- [ ] Define bounded typed deck entries and discriminated action/choice contracts.
- [ ] Reject malformed quantities, missing fields, invalid player/card IDs and unsupported actions with structured 4xx responses.
- [ ] Define explicit sandbox deck-size policy separately from malformed-input validation.
- [ ] Verify failed actions leave authoritative state unchanged; avoid catching exceptions after partial mutation.

Acceptance: missing/negative/oversized inputs and stale IDs cannot cause internal 500s or invalid games. Fuzz meaningful action families.

### 7. Restore matches and coordinate UI mutations (P2)

- [ ] Add saved active-match discovery/resume and persisted frontend selection.
- [ ] Add visible errors, bounded request timeouts/cancellation and stale-result rejection.
- [ ] Serialize manual/autoplay mutations and guard duplicate clicks.
- [ ] Establish safe retry semantics when a request result is lost.

Acceptance: refresh, backend restart, disconnect, double-click and autoplay/manual overlap do not lose a match or apply an action twice.

### 8. Share BO3 transitions and seed provenance (P2)

- [ ] Preserve base/per-game seeds in live transitions and snapshots, matching deterministic runner semantics.
- [ ] Implement previous-loser play/draw choice under the chosen match policy; expose it to humans and AI.
- [ ] Validate sideboard transitions; implement deliberate AI sideboarding or label its absence.

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
