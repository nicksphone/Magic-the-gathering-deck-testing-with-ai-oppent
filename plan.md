# MTG Deck Testing Lab Finish Plan

This plan reflects the current codebase, the verified runtime checks, and the remaining work needed to finish the project.

## Audit Status (2026-07-16)

The project is a substantial, test-backed simulator, but it is not yet rules-complete or consistently capable of piloting arbitrary decks at seasoned-player level. The current implementation is best described as a deterministic rules-aware testing platform with heuristic Oracle interpretation and matchup-aware AI.

Confirmed validation baseline:

- Backend: `438 passed`, 43 deprecation warnings.
- Frontend production build: passes.
- Tempo vs Blue Control two-game smoke run: completed with 0 timeouts; the sample result was Blue Control 2-0, which is not a balance conclusion because the sample is too small.
- The working tree contains ongoing implementation changes; do not discard unrelated local work while completing this plan.

Release blockers identified by the audit:

- Oracle interpretation still relies on text heuristics beneath the new structured ability boundary; broad conversion to structured card abilities remains unfinished.
- Master AI scores actions but does not yet consistently search multi-turn tactical lines.
- Active matches and simulator job metadata are now durable; interrupted simulator workers are marked failed rather than resumed automatically.
- Production API routing is now configurable, but automated production/LAN smoke coverage remains to be added.
- Full-game integration coverage is smaller than isolated rules-handler coverage.
- Card art and metadata remain dependent on cache completeness and upstream Scryfall availability.

## Verified Current State

- React + TypeScript frontend builds successfully.
- FastAPI backend tests pass.
- Local SQLite persistence is working.
- Rules engine covers turn structure, stack, combat, priority, mulligans, mana, state-based actions, triggers, replacement effects, prevention, continuous effects, and planeswalker loyalty resolution for the implemented scope.
- Explicit `{C}` mana symbols are tracked separately from generic mana in payment, AI scoring, and analytics.
- Generic "add one mana of any color" Oracle text now chooses a deterministic color from the controller's hand needs instead of picking an arbitrary color.
- Mana payment previews now consume pool mana during simulation so a single mana cannot satisfy multiple parts of the same cost.
- Common graveyard-to-battlefield reanimation text for creature cards is now supported in the oracle/effect pipeline.
- Reanimation-style Oracle inference now targets creatures from any graveyard when the text supports it.
- Battlefield-to-graveyard and battlefield-to-exile movement now respects card ownership for stolen permanents.
- Common continuous PT-setting phrasing such as "become 1/1" is now parsed alongside explicit base power/toughness text.
- Subject-specific base power/toughness setters now respect scoped Oracle text and deterministic battlefield order, and same-timestamp continuous/replacement sources now use battlefield position as the final tie-break.
- Engine-tagged control spell scoring now initializes board-role context correctly, and the Tempo-vs-Blue Control head-to-head smoke path completes cleanly again.
- Prowess-style noncreature-spell triggers now apply a temporary until-end-of-turn pump and clear at cleanup.
- Magecraft-style cast-or-copy triggers now fire for copied instants and sorceries as well as original casts.
- Additional-cost sacrifices now respect card ownership for stolen permanents.
- Direct sacrifice resolution now also respects card ownership for stolen permanents, matching the additional-cost path.
- Stack resolution now places instants and sorceries into their owner's graveyard, not the controller's graveyard.
- Common "one or more" dies/discard trigger variants now match the event layer alongside the singular forms.
- AI vs AI and head-to-head simulator paths run from the local repository layout.
- Diagnostic scripts now bootstrap their import path correctly when run from `backend/`.
- Diagnostic scripts refresh built-in and expansion deck corpora before simulation so they do not use stale local deck rows.
- The deterministic regression matrix now selects representative decks across archetypes before filling remaining slots.
- The overnight verbose round-robin diagnostics now use the same representative deck selection when capped.
- The representative deck selector now accepts both ORM rows and script-local dicts so diagnostics stay consistent across code paths.
- Restricted placeholder combat actions are filtered out of AI decision selection, which removes the repeated declare-attackers stall seen in simulator logs.
- Regression gate summaries now classify long active games separately from likely stalls and rules-issue timeouts, which reduces false-positive failure noise.
- Deck analysis now distinguishes actual split cards from other face-based imports, so combined mana costs are only used where they belong and primary-face costs are preserved for modal/adventure-style cards.
- Deck parser imports now accept common `Mainboard`, `Maindeck`, `Sideboard`, and `SB:` section headers for pasted decklists.
- Deck parser imports now also strip common set annotations like `[M11]` and `(XLN)` before lookup, which improves pasted decklist hydration.
- Deck parser imports now accept `4x Card Name` multiplier notation and ignore common comment lines, which broadens pasted-list support.
- Bounded regression gating completes successfully on a small deck sample.
- The current bounded regression matrix on six representative decks completed with 0 timeouts, 0 determinism failures, and 0 anomaly hits.
- Scryfall sync and token-art lookup now retry briefly on 429 responses instead of failing immediately.
- Card sync now falls back to cached metadata if a retryable Scryfall lookup still fails.
- Fallback card lookup now normalizes punctuation and spacing so common import-name variants can still resolve to cached metadata.
- Fallback card lookup now also resolves double-faced import names by trying the front-face name, which improves Delver-style hydration.
- Frontend production builds now resolve the backend from `VITE_API_BASE_URL` or the serving host on port `9999`, while development retains the Vite `/api` proxy.
- The frontend now displays backend connectivity status, polls `/health`, and provides a retry control when the API is unavailable.
- Active match snapshots now persist complete mutable rules state, card zones, stack objects, priority state, and RNG state in application-owned JSON.
- Active match snapshots are restored during backend startup, including controller configuration, decks, sideboards, AI archetypes, and match progress.
- Simulator job status, progress, errors, and results now persist in SQLite and are restored after startup; interrupted queued/running jobs are marked failed with an explicit restart reason.
- A structured `AbilitySpec`/`EffectSpec` boundary now carries source, cost, target hints, modes, choices, resolved effects, and unsupported-text fallback status into the rules engine.
- Triggered-ability fallback resolution now uses the same structured ability boundary as spell and loyalty resolution.
- Unknown nonempty action text is now marked as an explicit parser fallback instead of being indistinguishable from static keyword text.
- AI combat and threat evaluation now uses effective granted keywords, so static effects such as global deathtouch, trample, evasion, and menace grants affect attack/block planning.
- Current six-deck representative replay matrix completed 15 games with 0 determinism failures and no drift labels.
- Current Tokens vs Ramp three-game smoke completed with 0 timeouts; its 3-0 result is retained as diagnostic evidence only, not as a balance conclusion.
- Combat legality now recognizes nonbasic, snow, desert, wastes, and legendary landwalk in addition to the basic landwalk variants, with focused regression coverage.
- API smoke coverage now exercises `/health`, built-in deck loading, and local card-image serving; it also fixed the missing `BUILTIN_DECKS` import that caused built-in deck requests to fail at runtime.
- Analytics now counts unsupported Oracle fallbacks explicitly and attributes them to card names, with the same data rendered in the Testing Simulator UI.
- The current four-deck deterministic replay smoke completed 6 games with 0 determinism failures, 0 drift labels, and no anomaly hits; the prior six-deck 15-game baseline also remains clean.
- Controller-scoped creature, permanent, artifact, and enchantment ETB/death triggers are now matched before broad Oracle prefixes, preventing opponent-controlled entries or deaths from firing “under your control” abilities.
- An earlier Blue Control vs Ramp audit surfaced five Oracle fallbacks for Arboreal Grazer, Torrential Gearhulk, and Nissa; all three targets now have reusable handlers and subsequent Blue Control vs Ramp smoke runs showed no fallback, invalid-target, or cost-payment errors.
- Arboreal Grazer-style land-from-hand ETB effects now put a land onto the battlefield tapped without consuming the normal land play, and Torrential Gearhulk-style instant/sorcery recursion now casts a qualifying spell from the controller's graveyard through the normal stack.
- Nissa-style planeswalker handling now separates cast-time static text from loyalty lines, doubles land mana production through the mana engine, animates a target land with the +1 line, and deploys a green creature from hand with the -3 line.
- The post-change four-deck replay matrix completed 6 games with 0 determinism failures, 0 drift labels, and 0 anomaly hits. A separate control/ramp smoke reached a legal long-game timeout at the configured 1,200-tick cap; it was not classified as a repeated-action rules loop.
- Storm the Festival-style top-five permanent deployment and Shark Typhoon-style X/X flying Shark triggers now use generic top-library and spell-cast effect paths. The post-change three-deck replay matrix completed 3 games with 0 determinism failures, 0 drift labels, and 0 anomaly hits.
- Simple mana-cost activated abilities now have a legal-move and stack-resolution path; Recruitment Officer-style top-four creature searches are covered, while tap-plus-additional-cost, discard-cost, sacrifice-cost, and temporary-play permissions remain separate gaps.
- Temporary play permissions are now explicit per-card state with expiry, snapshot serialization, legal cast/land actions from exile, and a reusable top-card exile/play effect. Light Up the Stage-style cards no longer lose their temporary play window in the rules engine.
- Named-source attack triggers such as Goblin Guide now match the attacking permanent generically and queue a structured defending-top-card reveal effect; the event-to-stack path has focused regression coverage.
- Card cache rows now persist Scryfall rulings alongside faces and expose a completeness report for Oracle text, costs, type lines, legalities, rulings, face metadata, and real versus placeholder art through `/cards/completeness`.
- Fixed-cost and generic X-cost cycling are now first-class priority actions: the engine validates available mana, pays the cycling cost, moves the card to its owner's graveyard, places the draw ability on the stack, and the AI can use cycling as a lower-priority hand-filtering line.
- Common activated costs now support generic tap, mana, life, discard, and creature-sacrifice combinations. These costs are checked before payment, paid before the ability is put on the stack, and are available through both AI decisions and the human hand/battlefield action path.
- Cycling now emits a structured cycle event after activation, so generic “you cycle a card” and named-card cycling triggers can be matched and put above the cycling ability on the stack. Supported X values are carried into generic X-dependent trigger payloads.

## Remaining Gaps

### Rules coverage
- Long-tail Oracle coverage is still incomplete for unusual older cards and fringe wordings.
- Some replacement and prevention interactions still rely on heuristic inference instead of a fully generic rules model, even though replacement source selection now follows timestamp-like battlefield ordering.
- Prevention and replacement now cover broader controller/target wording plus artifact-or-enchantment die replacement, but the overall rules model still has heuristic seams for fringe Oracle text.
- Layer ordering and timestamp resolution still need more fidelity in obscure overlapping effects, but scoped base-PT setters now follow the same deterministic battlefield ordering as other continuous sources.
- Trigger parsing still depends on text inference in a few cases, especially unusual Oracle variants outside the current corpus, but common one-or-more dies/discard forms, cycling triggers, and controller-scoped ETB/death clauses are now covered.
- Named-source trigger wording is covered for attack triggers, but other named-source, intervening-if, and conditional trigger variants still need broader corpus coverage.
- The current representative corpus still has concrete fallback cards in normal games; alternate cycling variants, unusual modal and multi-part permanent effects remain outside the generic resolver even where common Storm/Shark and temporary-exile patterns are covered.
- Additional-cost handling now covers common creature, artifact, enchantment, permanent, and artifact-or-creature sacrifices; uncommon patterns such as counter removal, energy/resource payments, and returning permanents still need explicit cost modeling.
- Some unusual graveyard-target and battlefield-recursion variants still need broader corpus coverage.
- Graveyard recursion now supports artifact and enchantment permanents in addition to creature recursion.
- Graveyard recursion now also resolves generic permanent-card recursion from a graveyard, which broadens coverage to lands and other permanent types.
- Oracle target inspection now surfaces artifact and enchantment permanents for Disenchant-style removal, reducing generic fallback selection.
- Oracle target inspection now also surfaces generic nonland permanents, broadening common Vindicate-style and tap/removal effects.
- Oracle inference now also supports countering activated and triggered abilities, not just spells.
- Interactive X-spells now fall back to the smallest positive legal X when a target is present, preventing zero-value retry loops.
- Common fallback card data now covers additional archetype-defining cards so blank cached rows do not leave imported decks with no-op oracle text.
- Type-based library search now supports artifact, enchantment, permanent, and other common tutor targets instead of only name-based fallback searches.
- Type-based library search now also supports battlefield tutors, so search effects can move cards straight onto the battlefield instead of only into hand.
- Battlefield-tutor search now respects count and mana-value limits, including Collected Company-style wording.
- Death-trigger handling now also recognizes generic permanent-dies wording, not just creature-dies wording, which helps artifact and enchantment synergies fire from the same event path.
- Legacy combat evasion keywords like `shadow`, `fear`, and `intimidate` now participate in blocking legality for older-card coverage.
- More exotic control-changing death/exile cases still need wider corpus coverage, especially when cards are stolen and then moved between zones, but stack resolution now correctly uses card ownership for spell graveyard placement.
- Mana-value heuristics for obscure split/alternative-cost imports are now narrowed to niche corpus verification, since split cards and other face-based imports no longer collapse to a one-size-fits-all cost string.

### AI quality
- The AI is much stronger, but it still needs deeper tactical play in complex board states.
- Combat blocking now preserves mana creatures when better blocks exist, and still blocks with them when they are the only profitable defense.
- Master difficulty now invokes the deeper strategic planner earlier in complex midgame boards for control, counter-heavy, midrange, ramp, and tempo shells.
- Board-role planning now distinguishes stabilize, convert, race, control, defend, and normal states so multi-phase board evaluation is less generic.
- Engine-heavy artifacts and enchantments now carry explicit tactical weight so trigger engines are not scored like blank permanents.
- Matchup-aware scoring now gives ramp decks stronger early acceleration and control decks stronger stabilization lines when the board demands it.
- Control cast valuation now recognizes generic graveyard-casting recursion and rewards it only when a qualifying instant or sorcery is actually available in the graveyard, improving threat sequencing without card-name exceptions.
- Opening-hand evaluation now uses a broader hand-profile model, so ramp/control can keep real two-land action hands while aggro still rejects slow openers that lack pressure.
- Attack selection now uses the same hand-profile and board-role context, which reduces hopeless chip attacks from conservative decks while preserving pressure lines for racing archetypes.
- X-spells, modal cards, split cards, and dynamic-value cards still need broader matchup-aware scoring in rare edge cases, although X-value selection, modal face scoring, split/multi-mode selection, and board-role-aware mode scoring now consider board pressure, matchup pressure, and diminishing returns.
- The AI still needs more long-run tuning for control, tempo, ramp, token, and combo-lite matchups.
- Combo-lite matchups now have explicit proactive bias against control and counter-heavy shells, but the rest of the long-run tuning work remains.
- More board-state training data is still needed before the strongest archetypes can be treated as stable baselines.
- A Blue Control vs Ramp smoke after the recursion valuation change completed without fallback, invalid-target, or mana-payment errors; matchup results remain diagnostic until larger samples are run.

### Simulation and diagnostics
- The regression matrix and overnight round-robin now cover representative archetype spread, but they can still be expanded to larger samples and higher tick budgets.
- Long-form replay drilldown can still be improved for faster root-cause attribution, although structured AI TRACE drift now distinguishes stack-target, mode-choice, and face-choice mismatches and anomaly clustering now splits out pass loops, X-value errors, cost-payment failures, and unsupported Oracle fallbacks. The API anomaly scan now counts the same main-phase pass loops, repeated X-value errors, and card-level Oracle fallbacks.
- Replay comparison outputs now include a concise first-divergence excerpt so the exact divergent lines and nearby context are visible in batch and regression outputs.
- Overnight round-robin diagnostics now include the missing battlefield snapshot implementation and classify anomaly clusters from structured counters, so ordinary priority passes are not mislabeled as stalls; long games and pass-with-legal-action cases remain distinct.
- Training exports now include a lightweight board-role hint for each AI decision, and the priors builder can consume those exports in addition to raw replay traces.
- The simulator should continue to separate genuine stalls from long but valid games in its reporting, although timeout classification now distinguishes long-active games from likely stalls and rules issues.
- A six-deck verbose round robin completed with no hard rules errors or missed-land windows; its prior generic `pass_priority` cluster output was corrected to two pass-with-legal-action cases and one legal long-game case.
- The deterministic replay matrix now supports seeded best-of-1/3/5/7/9 matches, aggregates per-game wins and hashes, and validates the complete match sequence for determinism; a best-of-three two-deck smoke completed with zero replay failures.
- Remaining Scryfall/network edge cases are now mostly transient or offline-only rather than an unhandled hot path.
- Card metadata refreshes are now resilient even when the upstream API is temporarily unavailable after retries.
- Card-data completeness reports now identify uncached cards and fallback-backed Oracle data instead of silently treating partial metadata as complete.
- Saved-deck completeness is now available through `/decks/completeness` and `/decks/{deck_id}/card-completeness`, covering distinct mainboard and sideboard names for release diagnostics.
- Batch analytics now reports Wilson 95% confidence intervals and flags extreme, skewed, or insufficient-sample win rates; the Testing Simulator renders those balance alerts instead of presenting small samples as settled matchup truth.

### UI and docs
- The battlefield is usable, and density-aware sizing now engages earlier to keep moderate boards readable. Human players can now activate available fixed or X-cost cycling directly from the hand and choose a validated X value.
- Missing art now falls back to name-specific local placeholders, which improves token and uncached-card readability.
- Cached double-faced cards now also reuse face-level art when the root image is missing, which reduces blank Delver-style and transform-style displays.
- Token creation now emits enter-the-battlefield events, which closes a common trigger gap for token-centric decks.
- Token art fallback now prefers a generic token creature asset before the blank placeholder, which improves token readability even when upstream art is unavailable.
- Enter-the-battlefield trigger matching now covers token creation and permanent-ETB wording under your control, which broadens common trigger coverage.
- Enter-the-battlefield trigger matching now also covers artifact- and enchantment-specific ETB wording, which keeps noncreature engines on the same event path.
- Enter-the-battlefield trigger matching now also covers combined artifact-or-enchantment wording, which broadens noncreature engine coverage further.
- ETB matching now also recognizes the common another-permanent-under-your-control wording, which keeps token engines and permanent synergies on the same event path.
- Sacrifice triggers now emit from normal and additional-cost sacrifices, which broadens aristocrats-style payoff coverage.
- Sacrifice triggers now also cover artifact/enchantment wording and combined artifact-or-enchantment wording, which broadens noncreature sacrifice engines.
- Discard triggers now emit from normal discard effects and additional-cost discards, which broadens wheel and discard-payoff coverage.
- Combat-damage triggers now emit when attackers connect, which broadens combat-step payoff coverage.
- Attack triggers now emit when creatures are declared as attackers, which broadens attack-step payoff coverage.
- Block triggers now emit when creatures are assigned as blockers, which broadens block-step payoff coverage.
- Action-bearing triggers now reuse the oracle parser as a fallback, which broadens support for create, destroy, tap, discard, and similar trigger text.
- State-based actions now emit death/permanent-death events for lethal creatures and 0-loyalty planeswalkers, which keeps SBA-driven triggers in the same event path.
- Board evaluation now rewards trigger-engine permanents, improving AI recognition of sacrifice, ETB, discard, and combat payoff engines.
- Replay drift classification now recognizes attack, block, sacrifice, discard, ETB, death, and combat-damage log lines, which improves root-cause reports.
- Land plays now emit battlefield-entry events, which enables landfall-style triggers from actual land drops.
- Damage-prevention replacements now apply to creature-targeted damage as well as player-targeted damage, which broadens common fog/ward-style interactions.
- Damage-prevention replacements now also catch "you or a permanent you control" wording, which broadens a common class of prevention effects.
- Artifact- and enchantment-specific death triggers now share the same event path as creature and generic permanent death triggers.
- Combined artifact-or-enchantment death triggers now share the same event path as the rest of the permanent-dies family.
- README, changelog, plan, and graph exports should stay synchronized after future code changes.

## Step-by-Step Finish Plan

### 0. Fix runtime and deployment blockers
1. Make the frontend API base URL explicit for development, LAN testing, and production builds.
2. Add a health/connection indicator and actionable retry state to the frontend.
3. Document the supported deployment modes: Vite development proxy, static frontend plus backend, and reverse-proxy deployment.
4. Add an API smoke test that starts the backend, checks `/health`, loads built-in decks, and verifies card-image routing.

Exit criteria:
- A production build does not silently load with a nonfunctional API.
- LAN and local-host deployments have documented, tested configuration.

### 1. Make match and simulator state durable
1. Move active match records from process memory into a persistence-backed repository.
2. Persist simulator job status, progress, errors, and result metadata.
3. Make match and job identifiers safe across backend restarts and multiple workers.
4. Preserve deterministic seeds and replay references for resumed or inspected jobs.

Exit criteria:
- Restarting the backend does not silently destroy a saved match or completed simulator result.
- The simulator can be monitored after a page refresh.

### 2. Replace regex-only Oracle growth with structured abilities
1. Define a card-ability intermediate representation for costs, choices, targets, modes, effects, conditions, and duration.
2. Convert the highest-value mechanics in the current deck corpus first rather than attempting every historical card at once.
3. Use the structured representation for legal targets, cast choices, stack objects, triggers, and AI card valuation.
4. Keep text heuristics only as an explicitly logged fallback for unsupported cards.
5. Add corpus-driven tests for modal, split, transform, adventure, X-cost, alternate-cost, additional-cost, and copied-spell behavior.

Exit criteria:
- Mechanics present in the built-in deck corpus do not silently resolve through generic no-op or guessed behavior.
- Unsupported Oracle text is visible in diagnostics instead of appearing to resolve successfully.

### 3. Complete high-value rules fidelity
1. Tighten continuous-effect layers, timestamps, dependency ordering, and characteristic-defining effects.
2. Expand replacement/prevention ordering, can't-effect overrides, and multiple simultaneous replacements.
3. Complete attachment and aura legality, control changes, ownership movement, and zone-change triggers.
4. Add missing combat families such as banding, rampage, flanking, bushido, and landwalk where the corpus requires them.
5. Add coverage for vehicles, sagas, battles, classes, day/night, dungeons, initiative, and other modern card structures.
6. Validate simultaneous triggers, intervening-if conditions, optional choices, ordering choices, and “up to” choices.

Exit criteria:
- Common competitive mechanics are handled by explicit rules code.
- Every newly supported interaction has a focused regression test and at least one full-game integration test.

### 4. Raise AI from scoring to tactical planning
1. Add bounded multi-action search for spell sequencing, combat, stack responses, and mana preservation.
2. Search attack/block assignments using lethal, trade, crack-back, protection, and post-combat state evaluation.
3. Improve hidden-information reasoning using known cards, revealed cards, deck composition, and opponent ranges.
4. Add explicit plans for control, tempo, ramp, aggro, burn, tokens, aristocrats, reanimator, tribal, and combo-lite decks.
5. Teach Master AI when to hold interaction, represent a response, spend removal, protect an engine, or preserve a finisher.
6. Add automated sideboard plans and re-evaluate plans after games one and two.
7. Tune weights from replay/training data and matchup samples instead of adding card-name-specific exceptions.

Exit criteria:
- AI does not repeatedly miss obvious land drops, lethal attacks, profitable blocks, available interaction, or high-value curve plays.
- Complex positions are evaluated across at least the next meaningful decision sequence, not only the immediate action.

### 5. Build a serious regression and balance matrix
1. Run seeded best-of-three and best-of-nine samples across every built-in archetype pair; the replay runner now supports these match lengths.
2. Add long-run deterministic replay checks with first-divergence output and nearby state context.
3. Separate rules failures, AI stalls, legal long games, and expected deck-out losses.
4. Track play/draw advantage, mulligan rates, average turns, resource use, card-activation rates, and matchup confidence intervals.
5. Flag suspicious results such as 100% win rates, repeated no-action turns, unused mana with legal plays, and impossible zone states.
6. Require anomaly explanations before accepting a regression run as healthy.

Exit criteria:
- Every representative deck pair completes without unexplained stalls.
- Results are statistically meaningful enough to distinguish AI defects from matchup variance.

### 6. Finish card data and asset reliability
1. Add cache completeness reports for every imported deck, including Oracle, costs, type lines, faces, rulings, legalities, and images.
2. Retry and cache Scryfall data without blocking gameplay when the network is unavailable.
3. Resolve face-level art for double-faced, split, modal, and adventure cards.
4. Add token metadata and edition-specific token art where available, with clearly labeled fallbacks.
5. Surface unresolved or placeholder cards in deck analysis and simulator diagnostics.

Exit criteria:
- Users can identify every card in a loaded deck, even when upstream services are offline.
- Missing metadata is reported rather than silently producing weak AI behavior.

Current implementation note:
- `/cards/completeness` is available for distinct card names from an imported deck, and the deck import panel displays cache, fallback Oracle, placeholder-art, and ruling status after imports. Bulk completeness summaries remain in the release-hardening queue.
- Bulk saved-deck reports are now exposed by the backend; a dedicated multi-deck completeness dashboard remains optional release-polish work.

### 7. Complete the testing UI and release hardening
1. Keep battlefield, stack, mana, priority, combat, and hand panels readable on long matches and dense boards.
2. Add visible AI reasoning, action legality explanations, and response-window seat/controller context.
3. Add frontend replay browsing, anomaly drilldown, and simulator progress after refresh.
4. Add error boundaries, request timeouts, retry controls, and backend health reporting.
5. Verify hover inspection, keyboard accessibility, mobile fallback behavior, and LAN access.
6. Update README, changelog, plan, and generated analysis exports after every milestone.

Exit criteria:
- Long-session deck testing is understandable without reading raw backend logs.
- The documentation matches the actual shipped behavior.

### Current next implementation slice
1. Add replacement-aware cycling tests for draw/discard triggers and optional cycling triggers.
2. Expand X-cost cycling coverage to alternate costs, replacement-aware draws, and card-specific trigger payloads beyond the generic X/X token path.
3. Continue converting the highest-frequency fallback cards from simulator diagnostics into structured effects, starting with the current built-in deck corpus.

## Priority Order

Work in this order unless a production failure requires an earlier interruption:

1. Complete structured abilities for the current deck corpus, using the new fallback-card report to prioritize implementation.
2. Continuous/replacement/combat rules fidelity.
3. Tactical AI search and sideboarding.
4. Runtime/API deployment follow-up, including automated production/LAN smoke coverage.
5. Durable simulator job resume policy and multi-worker coordination.
6. Large deterministic matchup and balance matrix.
7. Card-data completeness and asset reporting.
8. Frontend replay and release polish.

## Verification Gates

A change is not done until all of the following are true:
- Backend tests pass.
- Frontend build passes.
- Representative simulator runs complete without unexplained stalls.
- AI vs AI can finish matches across representative decks.
- Human vs AI can progress through legal response windows.
- The README and plan match the codebase.

## Definition of Done

The project is finished when:
- The app loads and runs locally without broken pages.
- Deck import, card cache, rules engine, AI, and simulator work together in normal use.
- Common deck archetypes can be tested without manual intervention.
- Remaining rules and AI gaps are niche edge cases rather than day-to-day blockers.
- Documentation reflects the real shipped state.
