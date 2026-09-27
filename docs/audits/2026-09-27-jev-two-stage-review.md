# MTG — two-stage Jev audit and fix-direction review

## Outcome and attribution

**Both requested reviews were executed by a reusable TypeScript program against the live TypeSafe API.** Stage 1 evaluates candidate defects, scope/completeness and unknowns. Stage 2 consumes that freshly returned, validated Stage 1 result plus source-grounded worker-authored remedies, and evaluates directions, priorities and proposed acceptance coverage.

**The supplied snapshot is not ready for a reliable human-playtesting beta.** Repair live card hydration/views, acting-seat/action coverage, draw/cleanup semantics, malformed inputs and offline packaging; complete recovery, BO3 and regression gates. Broader simulator/AI quality remains unverified. Existing documentation reconciliation is completed, not an application fix.

Jev supplies **typed judgments and distributions**. The worker collected/reproduced evidence, proposed remedies/acceptance criteria, reconciled model uncertainty against source, and wrote this report. Jev did not autonomously inspect the repository, generate these prose fixes, implement patches, execute tests or certify release readiness. No application fix or deployment was performed.

## Actual TypeScript execution and provenance

Final evidence-bearing execution (working directory `/home/nick`):

```sh
node --experimental-strip-types /home/nick/Documents/mtg-jev-review/review.mts --run=review-02
```

The `.mts` artifact is executable TypeScript, not a Python/HTTP invocation mislabeled as TypeScript. Node executes its type-stripped code and both `fetch` calls; `tsc --noEmit` separately validates it. There is no response cache or fallback synthesis. Stage 2 is constructed only after Stage 1 receives HTTP 200 and passes runtime validation.

Live JavaScript SDK documentation was available and read: it recommends `@typesafe-ai/sdk` with Node 20+. We deliberately used the also-documented HTTP API **from TypeScript** so exact request/response text and headers could be archived with no SDK serialization ambiguity or application dependency changes. Only TypeScript and Node type declarations were installed in this deliverable; runtime uses Node built-ins. `package-lock.json` pins the tooling. Direct-fetch failures abort rather than automatically retry; rate limiting would require a deliberate fresh run with backoff.

| Stage | Resolved model | HTTP | Answers | Request ID | UTC start | Input/output tokens |
|---|---|---:|---:|---|---|---|
| 1 | `jev-1.13.0` | 200 | 26 | `req_01a0e41e07167832bdb7ad256c2b9d2d` | 2026-09-27T18:26:08.053Z | 18036 / 1235 |
| 2 | `jev-1.13.0` | 200 | 47 | `req_01a0e41e088d7e1bb4db7b88abfdf59b` | 2026-09-27T18:26:08.538Z | 27233 / 3026 |

Requested alias: `jev-latest`. Endpoint: `https://api.typesafe.ai/v1/systemone`. Actual final-run total: **73 judgments**, comprising 15 issue statuses + 3 global audit judgments + 8 unknown-surface judgments, followed by 45 per-case fix/priority/acceptance judgments + 2 global fix-review judgments.

**Execution issue, disclosed:** `review-01` also successfully made two fresh calls, but the first script captured only `x-request-id`/`request-id`; TypeSafe uses `x-typesafe-request-id`. We corrected header capture and reran the unchanged question design/evidence as `review-02`. Therefore this task made **four actual HTTP requests across two two-stage executions**, not just two requests total. Both runs remain archived. No rerun was made to seek preferred judgments. Earlier review-01 request IDs were not captured and are not invented. This report uses review-02 exclusively; differing response hashes are preserved.

Credential comes only from existing `TYPESAFE_API_KEY`, in the HTTPS Authorization header, never logged or saved. Exact JSON payloads contain curated relative-path source/log evidence, not database records, personal paths, full original reports or credentials. Persisted header allowlist excludes authorization/cookies.

## Scope and independent checks

Primary input is `/tmp/mtg-validation-f760c98/repo/`, treated read-only. All **296 tracked files** were freshly byte-compared against Git object `f760c98dc78016c00e3f64b88f99d013a624a261` before inheriting earlier evidence. Read the supplied and canonical graph reports first; supplied graph base `6b95fab0` is stale, and no supplied wiki index exists. The graph was navigation, not proof. No app edits means no graph update was appropriate.

Canonical checkout is now `babef27b5d2e4ccef38400ba90cb0c06bb8824c0`, newer than the supplied snapshot, with a pre-existing untracked coder-plan file. This review does not override or certify that evolving checkout. Knowledge work there cannot close or invalidate findings about the supplied snapshot; it needs a separate current-revision review.

28 reused verbatim source excerpts were programmatically revalidated against supplied bytes, further source excerpts were attached, and no prior Jev response was included in Stage 1. Prior sanitized candidate/remedy material was reused only within that validated scope. Source-relative database configuration makes changing cwd insufficient: probes and focused tests used a **new tracked-only copy** under `/home/nick/.hermes/cache/scratch/mtg-jev-two-stage/`, sharing only the existing Python interpreter/dependencies. Fresh install reproducibility was not tested.

| Newly executed check | Actual result | Durable evidence |
|---|---|---|
| API helper versus diagnostic hydration | 0 faces versus 2 | `contract-probes-new.log:1` |
| Effective versus public serialized stats | engine 3/3 versus API 2/2 | `contract-probes-new.log:2` |
| Cleanup versus ordinary discard | hand ends at 7 both; trigger count 0 versus 1 | `contract-probes-new.log:3` |
| Draw-step versus effect replacement | +1 card/+0 life versus +0 cards/+1 life | `runtime-probes-new.log:1` |
| Malformed inputs | empty/negative deck 200; missing quantity/card ID/invalid player 500 | `runtime-probes-new.log:3-7` |
| BO3 transition | games 1 and 2 both start P1 | `runtime-probes-new.log:9` |
| Two clean-copy fallback tests | 2 failed: generic route 404 and different fallback filename | `asset-tests-new.log:1-38` |
| TypeScript typecheck and offline validator tests | pass; missing keys/range errors rejected, stage dependency checked | `typecheck.log`, `self-test.log` |

Probe exit 0 means a diagnostic completed, **not** that app behavior passed. Backend GET 200 after a bad action does not prove every state field was untouched. BO3 `seed:null` probe fields do not prove absence of persisted RNG state; the missing explicit factory seed is source evidence. Generated per-card art exists, so packaging findings do not mean all art fallback fails.

Preserved **prior** evidence, not newly executed here: full suite 718 passed/2 failed; configured frontend build passed; npm advisory snapshot 7 affected packages (4 high/2 moderate/1 low); one two-game BO3 replay, no determinism failure. This is neither a fresh security scan nor a broad AI/balance measurement. No complete browser game, deployed HTTPS check, concurrency exploit/stress test, fresh install, Python advisory scan or broad semantic certification was performed.

## Stage 1 — Jev audit judgments

Jev status counts: **{'open': 13, 'unverified': 2}**. Independent dispositions: **{'open': 13, 'unverified': 1, 'fixed': 1}**. Categories are review cases, not exploit counts.

| Case | Jev status (confidence) | Independent disposition |
|---|---|---|
| hydration | open (0.88) | open |
| human_actions | open (0.98) | open |
| draw_cleanup | open (0.94) | open |
| effective_stats | open (1.00) | open |
| fallback_assets | open (0.99) | open |
| input_validation | open (0.98) | open |
| recovery | open (0.95) | open |
| routing | open (0.64) | open |
| bo3 | open (0.79) | open |
| frontend_contracts | open (0.92) | open |
| operational_controls | open (0.95) | open |
| dependencies | open (0.55) | open |
| knowledge_ai | open (0.93) | open |
| simulator_strength | unverified (0.90) | unverified |
| documentation | unverified (0.54) | fixed |

Global audit judgments:
- `audit_scope`: **bounded_substantive (1.00)**.
- `release_readiness`: **blocked (0.96)**.
- `audit_completeness`: **not_established (1.00)**.

Unknown surfaces are not silently converted to defects:

| Surface | Jev evidence judgment (confidence) |
|---|---|
| complete MTG semantics | narrow_only (0.48) |
| broad AI strength or balance | narrow_only (0.69) |
| production HTTPS deployment | unknown (0.95) |
| network exposure/exploitability | unknown (0.87) |
| concurrency/load behavior | unknown (0.87) |
| clean dependency install | unknown (0.57) |
| complete browser UI | narrow_only (0.47) |
| Python advisories | unknown (0.88) |

**Independent reconciliation:** documentation is **fixed in scope**, despite Jev's `unverified` selection. `CHANGELOG.md:5-9`, `plan.md:15-20,190-198`, and the documentation-only commit establish the historical status rewrite; they explicitly do not claim implementation completion. We preserve Jev's raw answer and do not reopen completed documentation. Stage 2 itself selects maintenance-only and no new repair acceptance for this case.

Routing's source default remains open, but an explicit deployment override could avoid it; no live HTTPS failure is established. Dependency advisories are supplied historical audit data, not seven proven shipped exploits. Missing operational controls are visible in source; exposure and exploitability remain unknown. Knowledge-consumer incompleteness applies to the supplied snapshot only. Low-confidence judgments require this kind of source reconciliation, not deletion or repeated inference until agreement.

## Stage 2 — fix directions, priority and acceptance

Direction counts: **{'appropriate': 15}**. Acceptance counts: **{'sufficient_bounded': 14, 'not_applicable': 1}**. Priority counts: **{'local_blocker': 8, 'beta_followup': 1, 'network_release_gate': 2, 'investigate_first': 1, 'simulator_roadmap': 2, 'maintain_only': 1}**.

| Case | Direction (confidence) | Priority (confidence) | Proposed acceptance coverage (confidence) |
|---|---|---|---|
| hydration | appropriate (0.94) | local_blocker (0.72) | sufficient_bounded (0.97) |
| human_actions | appropriate (0.98) | local_blocker (0.59) | sufficient_bounded (0.94) |
| draw_cleanup | appropriate (0.98) | local_blocker (0.80) | sufficient_bounded (0.97) |
| effective_stats | appropriate (0.99) | local_blocker (0.42) | sufficient_bounded (0.99) |
| fallback_assets | appropriate (0.91) | local_blocker (0.77) | sufficient_bounded (0.94) |
| input_validation | appropriate (0.97) | local_blocker (0.62) | sufficient_bounded (0.94) |
| recovery | appropriate (0.96) | beta_followup (0.55) | sufficient_bounded (0.95) |
| routing | appropriate (0.88) | network_release_gate (0.84) | sufficient_bounded (0.89) |
| bo3 | appropriate (0.94) | local_blocker (0.38) | sufficient_bounded (0.96) |
| frontend_contracts | appropriate (0.92) | local_blocker (0.42) | sufficient_bounded (0.89) |
| operational_controls | appropriate (0.96) | network_release_gate (0.64) | sufficient_bounded (0.87) |
| dependencies | appropriate (0.96) | investigate_first (0.36) | sufficient_bounded (0.89) |
| knowledge_ai | appropriate (0.98) | simulator_roadmap (0.97) | sufficient_bounded (0.92) |
| simulator_strength | appropriate (0.99) | simulator_roadmap (0.87) | sufficient_bounded (0.96) |
| documentation | appropriate (0.86) | maintain_only (0.56) | not_applicable (0.51) |

Roadmap ordering: **appropriate (0.94)**. Claim that defects are fixed now: **no (1.00)**.

Choice confidence describes probability-distribution concentration, **not** repository coverage, factual correctness, patch success or deployment permission. The complete probabilities remain in exact responses. `sufficient_bounded` means the proposed tests would cover the described issue **if implemented and passing**; no such future success is asserted.

The model's local-blocker versus beta-followup priorities for effective stats, BO3 and contracts have relatively weak concentration; dependencies select investigate-first. Worker scheduling keeps all local acceptance requirements before beta release, implements their regression tests alongside each fix rather than postponing all tests, and refreshes dependency advisories/reachability before selecting upgrade versions. Before any broader network exposure, authorization/resource/routing gates apply regardless of their place in local-only work. There is no calibrated automatic decision threshold or automated write action.

## What to fix and how — worker-authored, Jev-evaluated bounded proposals

Each section cites supplied source/evidence actually provided to Jev. These are **directions, not implemented patches**. Acceptance remains outstanding. Wording below is worker-authored; Jev selected typed evaluations, not these paragraphs.

### 1. Fallback Assets — open

**Issue:** Clean tracked checkout fails required generic fallback-art tests.

**Grounding:** `backend/card_data/token_images.py:18-35`; `pytest.log:12-37,62; asset-tests-rerun.log:1-38`; `asset-tests-new.log`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Choose and document the canonical offline-art contract. Prefer track a fallback SVG outside ignored cache and serve/copy it deterministically, or explicitly adopt generated per-card fallbacks and align route/tests. Verify fresh install with empty cache and no network, then entire suite; do not borrow developer-only cache.

**Acceptance:** Declared clean dependency install, empty DB/cache and no network serve documented fallback; two failing tests and full suite pass without developer files.

### 2. Hydration — open

**Issue:** Live API match hydration drops cached card faces and public views omit them.

**Grounding:** `backend/main.py:1175-1206`; `backend/card_data/hydration.py:30-44`; `backend/game_state/serializers.py:264-274`; `contract-probes-new.log:1-1`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Unify pure cached-card hydration for API, sideboard, simulation and replay while retaining API sync policy separately. Parse and validate face arrays and expose face/active-face fields in views. Test HTTP names-and-quantities start, face selection, transform and snapshot resume.

**Acceptance:** HTTP names/quantity start with cached two-face fixture retains faces; legal UI face choice/transform and snapshot restart preserve active face, types and stats; live/diagnostic parity.

### 3. Human Actions — open

**Issue:** Human seat 2 and generic ability, crew, and non-hand legal plays lack complete UI controls.

**Grounding:** `frontend/src/components/Battlefield.tsx:93-106`; `frontend/src/components/Battlefield.tsx:121-129`; `frontend/src/components/Battlefield.tsx:405-424`; `source review`; `backend/rules_engine/move_generator.py:201-261`; `backend/rules_engine/move_generator.py:315-380`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Derive acting seat from authoritative legal-move response and pending choice owner; render typed legal actions independently of hand zone, including activate_ability, crew and exile/library play. Enforce seat/controller on server. Add component and browser tests for both seats and each legal action; warn rather than silently omit unsupported moves.

**Acceptance:** Both human seats complete a game using actual controls; ability, crew, exile/library moves and pending choices submit correct actor and legal payload; stale/wrong-seat actions rejected; hidden information remains intentional.

### 4. Draw Cleanup — open

**Issue:** Normal draw step bypasses draw replacement; cleanup bypasses discard events and human selection.

**Grounding:** `backend/rules_engine/engine.py:87-110`; `backend/rules_engine/engine.py:233-245`; `backend/effects/handlers.py:209-241`; `runtime-probes-new.log:1-1`; `contract-probes-new.log:3-3`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Factor shared replacement/event-aware draw and discard operations. Preserve raw zone helper for low-level use; represent pending cleanup choice and continuation in durable state. Reorder cleanup correctly (discard before simultaneous damage removal/end-of-turn expiry), run state-based actions/triggers, grant priority and repeat cleanup when required; do not merely replace pop with the existing auto-selecting discard helper. Test step/spell/cycling parity, ownership, multiple replacements, discard choice and restart.

**Acceptance:** Golden state/log/stack tests for step/spell/cycling draw replacements, multiple replacements and resume; human cleanup selection, ownership, trigger ordering, damage/effect expiration, priority and repeat cleanup.

### 5. Effective Stats — open

**Issue:** Public battlefield stats are base rather than effective stats.

**Grounding:** `backend/game_state/serializers.py:247-261`; `contract-probes-new.log:2-2`; `backend/rules_engine/continuous.py:116-155`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Build a public card-view adapter using the same continuous-effect functions as combat. Expose printed/base and effective power/toughness, keywords, counters and damage distinctly; do not overwrite canonical base stats. Cover counters, anthems, temporary pumps, characteristic-defined stats, cleanup and reload in contract/UI tests.

**Acceptance:** HTTP and UI fixtures for counters, anthems, temporary pump, characteristic stats, expiration and reload match combat; base values remain unchanged.

### 6. Input Validation — open

**Issue:** Invalid decks/actions/player IDs are accepted or cause HTTP 500.

**Grounding:** `backend/main.py:96-120`; `runtime-probes-new.log:3-8`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Use bounded strict deck-entry models and discriminated action models; validate required IDs, legal actor, targets, costs and zone membership before writes. Separate optional sandbox deck-size rules from malformed data. Execute accepted mutations atomically under match version checks; return structured 4xx, not catch-all success. Fuzz inputs and compare full snapshots/database before and after rejected requests.

**Acceptance:** Malformed/oversized/negative/missing fields and wrong actor/zone/target/cost receive structured 4xx and identical complete in-memory/DB state; legal actions still work.

### 7. Recovery — open

**Issue:** Frontend cannot resume a saved match after refresh and lacks shared mutation/error handling.

**Grounding:** `frontend/src/App.tsx:14-27`; `frontend/src/App.tsx:113-118`; `frontend/src/App.tsx:195-208`; `frontend/src/api/client.ts:168-177`; `App.tsx full-file review; runtime-probes-rerun.log:8`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Persist/discover active match ID and GET authoritative state on resume. Route manual/autoplay requests through one mutation coordinator; use action idempotency keys plus server versions, abort stale reads and ignore old responses. Show actionable errors. After an ambiguous write timeout reconcile state before retry rather than blindly replaying. Test refresh, restart, double click and overlapping autoplay.

**Acceptance:** Refresh/restart discovers saved match; double-click/manual-autoplay overlap and multi-client stale write cannot duplicate effect; ambiguous write timeout reconciles before retry; visible actionable error and stale read tests.

### 8. Bo3 — open

**Issue:** Interactive next-game transition loses explicit seeded construction and starts games 1 and 2 with the same player.

**Grounding:** `backend/main.py:1221-1245`; `runtime-probes-new.log:9-9`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Define sandbox versus tournament start-player policy. Persist root seed, per-game seed schedule and play/draw choice; share transition service with diagnostics, applying legal sideboard and starting-player decisions before opening draw/mulligan. Test same actions across independent runs and restart between games. Store seed metadata explicitly; null probe fields alone do not prove RNG state is absent.

**Acceptance:** Seeded interactive BO3 repeats setup across independent runs/restart; root and per-game provenance persisted; sideboard inventory conserved; chosen sandbox or prior-loser play/draw policy tested.

### 9. Frontend Contracts — open

**Issue:** Build passes but frontend lacks test/lint scripts and runtime boundary validation; blocks type is wrong.

**Grounding:** `frontend/package.json:6-20`; `frontend/src/types/index.ts:60-64`; `frontend/src/api/client.ts:168-177`; `backend/game_state/serializers.py:292-295`; `build.log:3-13; source inspection`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Generate/share OpenAPI types plus runtime schema checks, model legal actions as discriminated unions, fix blocks to arrays of blocker IDs, and replace unsafe any at meaningful boundaries. Add ESLint/hooks, component tests, browser smoke and clean-checkout CI. Do not redundantly enable strict mode (already enabled).

**Acceptance:** Wrong blocks shape/missing face fields rejected by runtime boundary tests; both-seat actions, choices, errors and resume tested in components/browser; clean CI runs lint/build/frontend/backend suites.

### 10. Routing — open

**Issue:** Production API default bypasses same-origin proxy and can use insecure HTTP from HTTPS page.

**Grounding:** `frontend/src/api/client.ts:1-8`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Default to same-origin /api or require an explicit validated deployment setting; centralize API and media URL policy. Test actual production build under HTTPS /api and /card-images, plus explicit cross-origin configuration. No live deployment failure is asserted.

**Acceptance:** Actual production HTTPS build health/import/start/action/art succeed via /api and /card-images without mixed content; explicit cross-origin setup tested separately.

### 11. Operational Controls — open

**Issue:** Before network exposure, authorization, bounded job admission and coordinated per-match writes need explicit controls.

**Grounding:** `backend/main.py:55-86`; `backend/main.py:734-750`; `backend/main.py:790-792`; `main.py route review`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Keep local single-user service private and document supported single-worker topology now. For network deployment add authentication/authorization, restricted origins and CSRF defenses as applicable, bounded queue/quotas/cancellation, and per-match atomic version/idempotency checks shared across workers or explicitly restrict one worker. Test unauthorized writes, job floods, restart and concurrent stale actions; no exploit or stress failure is claimed.

**Acceptance:** Private single-user/single-worker constraints documented and enforced; before network release unauthorized writes rejected, allowed origins tested, stale writes conflict, job floods bounded by declared CPU/memory budget; restart/backup restore verified.

### 12. Dependencies — open

**Issue:** Supplied npm audit contains unresolved dependency advisories.

**Grounding:** `npm-audit.json parsed metadata`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Upgrade deliberately in isolated branch, checking Node/plugin compatibility and exact advisory fix ranges; refresh lockfile and use npm ci, build, new UI tests and full/production-only audits. Avoid audit fix --force. Distinguish dev/build exposure from shipped runtime reachability; current exploitability is not established.

**Acceptance:** Deliberate compatible upgrade and clean npm ci; build/UI tests pass; fresh full and production-only advisory scans plus reachability assessment explain exceptions; separate Python security scan.

### 13. Knowledge Ai — open

**Issue:** Knowledge storage exists but planned corpus sync and real AI consumers remain incomplete.

**Grounding:** `tracked file enumeration and agent.py source review`; `backend/ai/agent.py:1-100`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** After human correctness, freeze supported corpus and offline canonical seed/provenance, validate faces/rulings/effect clauses and wire typed knowledge into actual agent decisions. Add data-gap reports and consumer tests, then compare decision quality with seed/seat-balanced samples. Do not infer AI competence from model/table existence or parser coverage.

**Acceptance:** Offline provenance-backed supported corpus reproduces; actual production AI consumer tests verify knowledge affects decisions; explicit unsupported semantics; seed/seat-balanced before-after quality results.

### 14. Simulator Strength — unverified

**Issue:** Whether this app is a trustworthy broad-corpus simulator with strong/balanced AI remains unverified.

**Grounding:** `replay-final.json:1-34`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Define supported corpus and golden semantic fixtures, compare API and simulator hydration/transition parity, then run predeclared seed- and seat-balanced archetype matrices, with timeout/illegal action metrics and confidence intervals. Use smoke replay as repeatability evidence only, not a quality or balance certificate.

**Acceptance:** Predeclared supported cards/golden fixtures plus seed/seat-balanced archetype matrix, sample size and timeout policy; illegal action/cost/target traces and uncertainty intervals; API-simulator/restart parity. Not universal Magic certification.

### 15. Documentation — fixed

**Issue:** Whether historical contradictory finish-plan notes remain unresolved at the supplied revision; assess documentation only, not implementation completion.

**Grounding:** `CHANGELOG.md:5-9`; `plan.md:15-20`; `plan.md:190-198`; `git diff 6b95fab..f760c98`. Exact excerpts and results are in `evidence.json` and both request bodies.

**Direction:** Keep the reconciled gate plan and link new acceptance evidence as work lands; do not reopen the completed documentation rewrite or label planned app work fixed. Refresh stale graph only alongside future code edits, not during this read-only audit.

**Acceptance:** Existing reconciled plan remains linked to actual acceptance evidence, and does not claim implementation completed; no redundant rewrite required.

## Deliverables, reuse and preservation

All durable artifacts are under `/home/nick/Documents/mtg-jev-review/`:

- `review.mts`: real reusable two-stage TypeScript driver; `package.json`, `package-lock.json`, `tsconfig.json` provide isolated tooling.
- `runs/review-02/stage1-request.json`, `stage1-response.json`, `stage1-provenance.json`, `stage1-validation.json`: exact final first-stage exchange.
- Corresponding `stage2-*` files: exact dependent second-stage exchange; `summary.json` keeps complete case distributions. `runs/review-01/` preserves the earlier header-capture run.
- `evidence.json`, `evidence-validation.json`, `scope-validation.json`: sanitized candidate source/log evidence, bounded proposals, validated citations and byte-match manifest.
- `contract_probes.py`, `runtime_probes.py`, new logs and `local-execution.json`: actual probe scripts, commands/cwds/exit codes. Probe scripts import a sibling `repo/backend`; only run them with a fresh isolated source copy, never next to live source/database.
- `supplied-*` logs retain distinctly historical suite/build/advisory/replay evidence.
- `docs/` stores freshly fetched TypeSafe index, JavaScript SDK, HTTP API, state, Choice and citation-check cookbook; `sources.json` records URLs/timestamps/status/hashes.
- `independent-validation.json`, `source-before.json`, `preservation-after.json`, `artifact-manifest.json`: schema/hash/dependency/count/secret/preservation checks and artifact inventory.
- `prepare_evidence.py` and `finalize_review.py`: local evidence preparation and independent validation/report assembly; the prep script intentionally refuses an existing scratch copy rather than overwrite it. **Only `review.mts` makes the Jev calls.**

To reuse saved sanitized evidence for another actual two-stage evaluation:

```sh
npm --prefix /home/nick/Documents/mtg-jev-review ci
npm --prefix /home/nick/Documents/mtg-jev-review run typecheck
npm --prefix /home/nick/Documents/mtg-jev-review test
node --experimental-strip-types /home/nick/Documents/mtg-jev-review/review.mts
```

Use a Node runtime supporting built-in TypeScript stripping; verified here on `v22.23.2`. The key must already be in the environment; do not put it in CLI arguments or report files. The default timestamp creates a new output directory; an existing explicit `--run=` directory is rejected. `--self-test` uses an explicitly labeled synthetic validator fixture, makes **zero HTTP requests**, and never substitutes it for live results. For newer application revisions, regenerate/revalidate evidence first; rerunning old evidence does not inspect new source.

**Preservation:** independently rehashed all **575 supplied files** after tests/calls: no changed, added or removed files. Original/canonical application source, database and dependencies were not written by this task; canonical is explicitly not claimed unchanged relative to the older snapshot. Isolated scratch database/cache writes and deliverable tooling/files are the only task changes. No deployment.

### Final-run SHA-256 integrity

- `stage1-request.json`: `d9d552bb8d4dbfdefe90e675ca2a834f1106e3f4eb249b4d0dd77d3c2704ec3c`
- `stage1-response.json`: `381764f2c17db3dca75464376152127333b0b2804a48ca642a0fe3be02391afa`
- `stage2-request.json`: `0edec3fa66ff09372f0e02129e9604bd8785c6d6b9f18105ea69bd52027dd952`
- `stage2-response.json`: `5378b67944dff6477db41ace126c2ded11275c56e9b792264a9b27f517f00466`

Stage 2 contains the full parsed Stage 1 result unchanged plus its exact raw-response hash; independent validation checks both, exact answer sets, probabilities/ranges, model IDs, HTTP statuses and artifact hashes. Evidence and TypeScript compilation are verified; application acceptance work remains open.
