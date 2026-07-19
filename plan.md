# MTG Deck Testing Lab Finish Plan

This plan reflects the current codebase, the verified runtime checks, and the remaining work needed to finish the project.

## Audit Status (2026-07-19)

The project is a substantial, test-backed simulator, but it is not yet rules-complete or consistently capable of piloting arbitrary decks at seasoned-player level. The current implementation is best described as a deterministic rules-aware testing platform with heuristic Oracle interpretation and matchup-aware AI.

Confirmed validation baseline:

- Backend: `443 passed`, 43 deprecation warnings.
- Frontend production build: passes.
- Current focused diagnostics taxonomy tests: `8 passed`.
- Current decision-reason and trace-export tests: `15 passed`; AI traces now preserve stable reason labels and legal action-type summaries for downstream analytics and training.
- Current consolidated rules/AI validation: `344 passed`; frontend production build passes; the current three-game deterministic replay smoke has 0 determinism failures and 0 drift labels.
- Tempo vs Blue Control two-game smoke run: completed with 0 timeouts; the sample result was Blue Control 2-0, which is not a balance conclusion because the sample is too small.
- Latest implementation milestones are pushed to `main`; preserve any future unrelated local changes while completing this plan.

This is an engineering-completeness audit, not a claim that the simulator is rules-complete. The application is usable for deterministic deck testing and common archetypes, but it should not yet be described as a pro-level Magic rules implementation or as an AI trained to optimal play across arbitrary cards.

### Current release assessment

The repository is in a functional engine-hardening stage, not a feature-discovery stage. The core loop works, but "works" currently means that supported cards and common interactions can be simulated deterministically; it does not mean that every imported Oracle text is interpreted correctly or that Master AI always finds the seasoned-player line.

Verified strengths:

- Common turn, priority, stack, mana, combat, zone, trigger, replacement, prevention, attachment, Saga, Vehicle, day/night, cycling, tutor, X-value, and temporary-permission paths have application-code coverage.
- AI has archetype detection, mulligan and land-drop logic, interaction timing, bounded spell/stack/combat lookahead, legal tutor-choice materialization, and structured decision traces.
- The simulator has persistent job state, deterministic seeds, replay hashes, first-divergence reporting, anomaly classification, and confidence-interval reporting.
- The frontend has a working production build, configurable LAN API routing, health/retry state, response windows, card inspection, density-aware battlefield rendering, and simulator progress reporting.

Verified limitations:

- The ability model is a boundary around the existing resolver; it is not yet a complete structured representation for all costs, modes, conditions, continuous effects, replacement effects, and choices.
- The engine still has heuristic seams for unusual Oracle text, dependencies between continuous effects, timestamp/layer edge cases, multiple replacement choices, and modern permanent structures.
- Master AI is bounded and heuristic. It can still miss multi-turn resource plans, hidden-information inferences, sideboard plans, complex combat assignments, and matchup-specific “hold versus deploy” decisions.
- Small replay samples are useful for finding deterministic bugs but cannot establish balance. A result such as 100% win rate is an anomaly signal until a larger seeded matrix explains it.
- Missing or placeholder card data/art can still reduce both player readability and AI quality when a deck is imported offline.
- A reproducible `oracle_corpus_report.py` now ranks the shipped corpus by weighted copies and unresolved Oracle family. The current report covers 81 unique cards / 3,780 copies across 11 built-ins and 52 expansion entries; 3,441 weighted copies are structured effects, 155 are structured event/replacement paths, 184 are static/no-op classifications, and 0 remain parser-fallback or missing-Oracle. The report uses the same stable backend SQLite cache regardless of launch directory, so the previous false 450-copy missing-Oracle result is retired.

The abandoned token-compression experiment is not part of this project plan, runtime, or release criteria. Do not add it back as a gameplay, diagnostics, or documentation dependency.

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
- Explicit top-library choices now support hand/exile/ordered-bottom placement for Expressive Iteration-style effects. Human selections are validated for exact one-time placement, while AI callers retain a deterministic fallback; the focused gate passes 61 tests and the latest three-game replay smoke has 0 determinism failures and 0 drift labels.
- Common tempo bounce now has a reusable ownership-correct battlefield-to-owner-hand effect for nonland permanents and creatures, with target hints, leave events, stolen-permanent coverage, and no Oracle fallback.
- Master/Master Plus now run bounded small-board attack-subset search through legal blocker assignments and combat resolution, reducing hopeless chip attacks while retaining lethal and mandatory attack behavior.
- Master/Master Plus deep-copy search is now complexity-bounded by battlefield size and legal-action count; dense token boards use deterministic heuristic/combat evaluation instead of monopolizing simulator runs. Tokens vs Ramp completed three games at the 1,200-tick cap with 0 timeouts after this guard.
- AI diagnostic traces now preserve effective keyword snapshots, attacker assignments, blocker assignments, X values, and legal-action counts. Analytics now reports evasion-aware bad attacks, lethal attack opportunities/misses, profitable versus losing blocks, engine-protection passes, and resource-preservation passes.
- Master blocker search now rejects non-lethal pure chump assignments when no attacker is lost, while retaining lethal prevention and profitable trades. A post-change Tokens vs Ramp diagnostic completed without obvious bad attacks or losing-block classifications.
- Attack search is gated to late-game positions with at most three attackers and two blockers after matrix profiling showed larger clone-search bounds could monopolize long simulations.
- Current Tokens vs Ramp three-game smoke completed with 0 timeouts; its 3-0 result is retained as diagnostic evidence only, not as a balance conclusion.
- Combat legality now recognizes nonbasic, snow, desert, wastes, and legendary landwalk in addition to the basic landwalk variants, with focused regression coverage.
- API smoke coverage now exercises `/health`, built-in deck loading, and local card-image serving; it also fixed the missing `BUILTIN_DECKS` import that caused built-in deck requests to fail at runtime. SQLite persistence is anchored to `backend/mtg_lab.db` rather than the process cwd, preventing API and diagnostics from silently using different caches.
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
- Nontoken death replacement clauses now enforce the token/non-token distinction; multiple simultaneous replacement choices and deeper dependency ordering remain open.
- Prevention and replacement now cover broader controller/target wording, combat-only and named-source “can't be prevented” scopes, plus artifact-or-enchantment die replacement, but the overall rules model still has heuristic seams for fringe Oracle text.
- Layer ordering and timestamp resolution still need more fidelity in obscure overlapping effects, but scoped base-PT setters now follow the same deterministic battlefield ordering as other continuous sources.
- Trigger parsing still depends on text inference in a few cases, especially unusual Oracle variants outside the current corpus, but common one-or-more dies/discard forms, cycling triggers, and controller-scoped ETB/death clauses are now covered.
- Named-source trigger wording is covered for attack triggers, but other named-source, intervening-if, and conditional trigger variants still need broader corpus coverage.
- Common transform upkeep triggers now have an explicit path, and the core day/night state machine transforms matching daybound/nightbound permanents; other state-based transform systems remain unfinished.
- The current representative corpus still has concrete fallback cards in normal games; alternate cycling variants, unusual modal and multi-part permanent effects remain outside the generic resolver even where common Storm/Shark and temporary-exile patterns are covered.
- Additional-cost handling now covers common creature, artifact, enchantment, permanent, and artifact-or-creature sacrifices; uncommon patterns such as counter removal, energy/resource payments, and returning permanents still need explicit cost modeling.
- Some unusual graveyard-target and battlefield-recursion variants still need broader corpus coverage.
- Graveyard recursion now supports artifact and enchantment permanents in addition to creature recursion.
- Graveyard recursion now also resolves generic permanent-card recursion from a graveyard, which broadens coverage to lands and other permanent types.
- Oracle target inspection now surfaces artifact and enchantment permanents for Disenchant-style removal, reducing generic fallback selection.
- Oracle target inspection now also surfaces generic nonland permanents, broadening common Vindicate-style and tap/removal effects.
- Aura and Equipment detection is now case-insensitive, Aura restrictions cover common permanent/player target classes, and state-based actions recheck invalid attachments.
- Common temporary control-change effects now move permanents by controller, restore them at cleanup, and persist their duration metadata without changing ownership.
- Common battlefield exits now emit a shared leaves-battlefield event, and controller-scoped leave triggers resolve through the normal stack path.
- Mass battlefield exits now use a shared batched event path, so `one or more` leave/death triggers fire once per simultaneous batch while ordinary per-object triggers remain separate.
- Oracle inference now also supports countering activated and triggered abilities, not just spells.
- Interactive X-spells now fall back to the smallest positive legal X when a target is present, preventing zero-value retry loops.
- Common fallback card data now covers additional archetype-defining cards so blank cached rows do not leave imported decks with no-op oracle text.
- Type-based library search now supports artifact, enchantment, permanent, and other common tutor targets instead of only name-based fallback searches.
- Type-based library search now also supports battlefield tutors, so search effects can move cards straight onto the battlefield instead of only into hand.
- Library-search choices are now explicit and shared across human and AI actions: legal moves expose matching candidates, cast-choice validation rejects nonmatching IDs, and resolution revalidates selected cards against the live library.
- Battlefield-tutor search now respects count and mana-value limits, including Collected Company-style wording.
- Death-trigger handling now also recognizes generic permanent-dies wording, not just creature-dies wording, which helps artifact and enchantment synergies fire from the same event path.
- Legacy combat evasion keywords like `shadow`, `fear`, and `intimidate` now participate in blocking legality for older-card coverage.
- More exotic control-changing death/exile cases still need wider corpus coverage, especially when cards are stolen and then moved between zones, but stack resolution now correctly uses card ownership for spell graveyard placement.
- Mana-value heuristics for obscure split/alternative-cost imports are now narrowed to niche corpus verification, since split cards and other face-based imports no longer collapse to a one-size-fits-all cost string.
- The next rules work must be corpus-driven: collect fallback and invalid-resolution counts from representative decks, then convert the highest-impact families into reusable structured effects. Do not add isolated card-name branches merely to make one fixture pass.
- Conditional target metadata now filters and validates common type exclusions and mana-value ceilings, including nonartifact, nonland, noncreature, creature-or-planeswalker, static mana-value, controlled-basic-land, and controller-graveyard limits. Revolt-style state conditions and conditional payment branches remain separate work.
- Modal casting now selects modes before target materialization and rebuilds mode-specific target hints, so counter, removal, and other mutually exclusive modes do not share stale target classes. `Choose two` selections resolve through an ordered structured effect sequence.
- Replacement candidate handling now applies one mutually exclusive prevention/replacement effect per event, chooses the latest deterministic source when no explicit source ID is supplied, and carries source metadata through gain-life, draw, and damage replacement paths. A human-facing replacement-choice prompt and full re-evaluation loop remain open.
- Verbose card-play analytics now reports pass-with-unused-mana and main-phase land-not-first decisions separately, preserving hand, board, mana, legal-action, and reasoning context for later AI tuning.

### AI quality
- The AI is much stronger, but it still needs deeper tactical play in complex board states.
- Master lookahead now resolves unanswered activated/cycling stacks during simulation, but stops the approximation when the opponent has a legal non-pass response; this improves card-filtering and engine valuation without suppressing interaction.
- Master strategic planning now expands to a bounded two-ply search when the board is developed, so spell sequencing and response preservation are evaluated beyond the immediate action without imposing the cost on early turns.
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
- AI training artifacts currently provide timing/board-role priors and labeled traces, not a learned policy. They must be treated as evidence for weight tuning and regression analysis, not as proof of expert play.
- The next AI milestone must measure decision quality, not only match completion: missed land drops, unused legal mana, premature attacks, lethal misses, bad blocks, unprotected engines, and interaction held through the wrong window need per-decision metrics.
- Decision-quality metrics now include attack/lethal/block quality and resource-preservation signals from richer combat traces. Longer matchup samples are still needed before using the metrics as balance or expert-play proof.

### Simulation and diagnostics
- The regression matrix and overnight round-robin now cover representative archetype spread, but they can still be expanded to larger samples and higher tick budgets.
- Long-form replay drilldown can still be improved for faster root-cause attribution, although structured AI TRACE drift now distinguishes stack-target, mode-choice, and face-choice mismatches and anomaly clustering now splits out pass loops, X-value errors, cost-payment failures, and unsupported Oracle fallbacks. The API anomaly scan now counts the same main-phase pass loops, repeated X-value errors, and card-level Oracle fallbacks.
- Replay comparison outputs now include a concise first-divergence excerpt so the exact divergent lines and nearby context are visible in batch and regression outputs.
- Overnight round-robin diagnostics now include the missing battlefield snapshot implementation and classify anomaly clusters from structured counters, so ordinary priority passes are not mislabeled as stalls; long games and pass-with-legal-action cases remain distinct.
- Training exports now include a lightweight board-role hint for each AI decision, and the priors builder can consume those exports in addition to raw replay traces.
- The simulator should continue to separate genuine stalls from long but valid games in its reporting, although timeout classification now distinguishes long-active games from likely stalls and rules issues.
- A six-deck best-of-three matrix reproduced a Ramp tutor-choice loop; after AI search-choice materialization was added, the same trace has no invalid-search errors and only the underlying legal long-game closure case remains.
- A six-deck verbose round robin completed with no hard rules errors or missed-land windows; its prior generic `pass_priority` cluster output was corrected to two pass-with-legal-action cases and one legal long-game case.
- Decision-trace diagnostics now share a move taxonomy across overnight and head-to-head runners: pass actions and restricted combat placeholders are excluded, while cycling, activated abilities, and equipment are treated as meaningful options.
- A fresh four-deck six-game round robin using the shared taxonomy completed with 0 invalid targets, 0 cost failures, 0 additional-cost failures, 0 missed-land windows, and 0 stall streaks. It produced two legal long-game timeouts and one control hold-up pass for follow-up reasoning labels.
- AI verbose traces now include `reason_code`, raw `reasoning`, and `legal_action_types`; training exports and card-play analytics preserve and aggregate those fields, and anomaly clustering can identify deliberate `hold_up_interaction` passes separately from unexplained meaningful-option passes.
- Cycling draw resolution now uses the ordinary replacement-aware draw path, and cycling discard triggers are ordered above the cycling ability. Optional cycling triggers can be declined through the existing stack choice path.
- Alternate cycling variants now support fixed and variable landcycling/basic-landcycling costs, validated X choices, explicit library-search candidates, selected-card resolution, and deterministic post-search shuffling. The focused cycling/rules/AI regression set passes `225` tests; the three-game deterministic replay smoke remains at 0 failures.
- Ramp fallback data now uses canonical Cultivate and Migration Path basic-land search text. Search inference supports basic-land filters, counts, shuffle instructions, and tapped battlefield placement; the combined cycling/search/rules/AI suite passes `199` tests and the three-game deterministic replay smoke has 0 determinism failures.
- Triggered self-counter wording now resolves generically against the permanent that owns the trigger, covering named patterns such as “put a +1/+1 counter on [this creature]” without card-name handlers; event/oracle/search regression coverage passes `71` tests.
- Counted creature-type life-loss triggers now resolve from the controller's battlefield at resolution time, including token/type-line subtypes and plural type names; the broader cycling/search/trigger/rules/AI suite passes `201` tests and the three-game deterministic replay smoke has 0 failures.
- Top-N hand/exile/bottom selection now has a reusable structured effect for Expressive Iteration-style Oracle text, including temporary play permission for the exiled choice; focused top-choice/Oracle/event/legal-move/AI coverage passes `162` tests.
- Master AI strategic planning now uses an adaptive two-ply horizon on developed late-game boards, while keeping early turns at one ply; activated abilities, cycling, equipment, and attacks are eligible proactive candidates. The AI/replay suite passes `93` tests and the three-game replay completed with 0 determinism failures and 0 drift labels.
- Master combat planning now enumerates bounded legal blocker assignments on small boards, resolves cloned combat states, and compares lethal prevention, trades, and post-combat value before using the heuristic assignment path.
- Common Saga rules now advance lore counters at precombat main, resolve chapter abilities through the stack, and sacrifice after the final chapter resolves; Fable fallback metadata includes its Saga type and chapters.
- Common Vehicle crew now exposes explicit legal creature selections, taps the crew, grants temporary creature status through cleanup, and is materialized by Master AI.
- Restricted target validation now rejects stale or cross-zone card IDs before stack placement while preserving broad any-target protection/hexproof handling.
- Farewell-style mass creature exile now uses a distinct ownership-correct effect with battlefield-leave events instead of destroy/death semantics.
- Mass creature destruction now emits the same battlefield-leave event before moving cards to graveyards, so leave triggers observe the zone change consistently across exile and destroy effects.
- Batched mass zone changes now collect simultaneous leave/death triggers before stack placement and deduplicate `one or more` trigger text, while preserving per-object triggers for ordinary wording.
- Modal choice extraction now supports Scryfall bullet formatting and `Choose two` schemas while preserving readable mode labels for human and AI choices.
- Battlefield topdeck tutors now expose validated candidate selections to humans and AI, and Collected Company-style creature deployment honors the selected cards instead of always taking the internal ranking.
- Stack countering now honors source-level `can't be countered`/`cannot be countered` text and moves countered spells to their owners' graveyards rather than their controllers' zones.
- Spell-created “this turn” restrictions now persist through the active turn, survive snapshots, block later life gain or damage prevention, and expire at cleanup.
- Legend-rule state actions now use ownership-correct death replacement and emit battlefield-leave, permanent-death, and creature-death events when the duplicate actually dies.
- Combat now handles generic Bushido, Rampage, and Flanking modifiers at blocker declaration, including temporary cleanup-scoped stat changes and lethal-damage interaction.
- AI action materialization now supplies validated library-search selections for tutor casts; the reproduced Topiary Stomper invalid-target loop is fixed, while legal no-threat control endgames remain a separate closure-tuning item.
- Graveyard spell-target hints now participate in legal-move generation and Master action materialization, restoring common recursion finishers such as Torrential Gearhulk-style cards.
- Transform upkeep triggers now use a generic top-card type check and apply the selected back-face metadata without moving the revealed card; Delver-style transform regression coverage passes `155` tests.
- Day/night now tracks spell casts, applies zero/two-spell upkeep transitions, persists through snapshots, and transforms matching battlefield double-faced permanents; focused day/night/replay coverage passes `14` tests.
- Day/night state changes now emit stack-backed transition events for matching “becomes day/night” triggers.
- Characteristic-defining power/toughness now supports distinct card-type counts across all graveyards, feeding effective combat stats and AI evaluation dynamically; continuous-effect/AI coverage passes `102` tests.
- Current focused implementation gate combines cycling, search, top-card choices, bounce, Saga, Vehicle, mass exile, target legality, Oracle, event, replacement, continuous-effect, modal, topdeck-tutor, stack, temporal-restriction, legendary-state, combat-family, conditional-target, database-path, top-library permissions, X triggers, and AI search-budget tests: `341 passed`.
- The deterministic replay matrix now supports seeded best-of-1/3/5/7/9 matches, aggregates per-game wins and hashes, and validates the complete match sequence for determinism; a best-of-three two-deck smoke completed with zero replay failures.
- Remaining Scryfall/network edge cases are now mostly transient or offline-only rather than an unhandled hot path.
- Card metadata refreshes are now resilient even when the upstream API is temporarily unavailable after retries.
- Card-data completeness reports now identify uncached cards and fallback-backed Oracle data instead of silently treating partial metadata as complete.
- Saved-deck completeness is now available through `/decks/completeness` and `/decks/{deck_id}/card-completeness`, covering distinct mainboard and sideboard names for release diagnostics.
- Batch analytics now reports Wilson 95% confidence intervals and flags extreme, skewed, or insufficient-sample win rates; the Testing Simulator renders those balance alerts instead of presenting small samples as settled matchup truth.
- A complete balance pass still requires seeded best-of-3/best-of-9 round-robin coverage across the built-in corpus, with full card-play and hand/board snapshots for anomalous games. One-off smoke matches are not sufficient acceptance evidence.

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
5. Add coverage for Battles, Classes, Dungeons, Initiative, and other modern card structures; common Saga and Vehicle progression is now implemented.
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
1. Expose replacement candidates and simultaneous trigger ordering as explicit human/API choices, with a pause/resume path that re-evaluates the modified event after each selected replacement.
2. Implement the next high-value replacement/layer slice: explicit effect timestamps, dependency ordering, prevention/can't overrides, and multiple replacement choices, each with integration coverage.
3. Expand the now-zero-fallback corpus coverage with adversarial state tests for Realmwalker top-library permissions, Hydroid Krasis X triggers, self-cast triggers, and conditional replacement choices; keep future metadata gaps separate and never fill cache gaps with guessed card text.
4. Extend Master tactical search using the new decision-quality metrics, then add stronger crack-back and post-combat evaluation, hidden-information signals, and explicit resource-preservation plans across all archetypes.
5. Run seeded best-of-3/best-of-9 round-robin batches with full hand/board/action analytics, classify every anomaly, and fix defects before using results for balance tuning.
6. Finish bulk card/token completeness reporting plus frontend replay/anomaly drilldown, then validate LAN deployment and long-session UX.

### Latest audit correction

- Fixed cwd-dependent SQLite resolution in `backend/persistence/db.py`; API servers, sync jobs, and corpus diagnostics now share the canonical backend cache when launched from either the repository root or `backend/`.
- Added `backend/tests/test_database_path.py` to lock this behavior down.
- Re-ran the corpus audit from the repository root after the fix. The authoritative result is 81 unique cards / 3,780 copies, with 0 parser-fallback copies and 0 missing-Oracle copies in the shipped corpus; remaining work is adversarial rules fidelity, not cache-path repair.

### Rules corpus milestone

- Added generic conditional stack targeting and payment choices for `counter target noncreature spell unless its controller pays {N}`.
- Added generic noncombat-damage replacement to `-1/-1` counters, power-based death-trigger damage, self-cast X triggers, X-counter entry handling, and ETB graveyard instant casting.
- Added Realmwalker-style chosen-creature-type persistence and legal casting of the matching creature from the top of the library, including snapshot support.
- Broadened top-card choice wording and plural number parsing, and classified supported triggered/event surfaces separately from true parser fallbacks.
- The current corpus audit is now 3,441 structured-effect copies, 155 structured-event copies, 184 static/no-op copies, and zero parser-fallback or missing-Oracle copies.

### Audit findings and acceptance criteria

The following are the remaining gaps that can still make a deck appear to play below seasoned-player level:

- Unsupported or partially supported Oracle text can still resolve through a logged fallback, especially for rare modal, multipart, attachment, replacement, and modern permanent structures.
- Layer dependencies, timestamps, prevention ordering, and "can't" overrides are not yet a complete general model.
- Library-search, top-library, common modal modes, and topdeck battlefield-tutor choices are now explicit for their supported families; complex modal multi-effects, complete simultaneous trigger ordering, and additional battlefield-tutor restrictions still need the same treatment.
- Combat search is bounded and heuristic; it still needs stronger assignment search and post-combat evaluation for complex boards. Bushido, Rampage, and Flanking are now explicit; banding and other assignment-changing families remain open.
- Hidden-information inference, sideboarding, matchup plans, and long-run archetype tuning are not complete.
- Simulator diagnostics are strong for deterministic drift and common anomalies, but full-corpus attribution and statistically meaningful balance samples remain unfinished.
- Card/token completeness and frontend replay inspection need release-level verification, especially offline and LAN deployments.

Each item is complete only when it has application-code coverage, focused regression tests, at least one full-game or replay validation, and synchronized README/changelog/Graphify output where applicable.

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

## Audit Decision Rules

- A card is not considered supported because it imports, displays, or resolves without an exception. It must produce the correct zones, choices, targets, timing, triggers, and state-based consequences for its covered wording.
- An AI matchup is not considered healthy because it finishes. It must avoid repeated illegal or obviously dominated actions and expose enough trace context to explain unusual decisions.
- A win-rate result is not a balance conclusion below the configured confidence/sample threshold. Extreme results are regression candidates, not automatic deck nerfs.
- Every milestone must update this plan, the README’s current-state sections, the changelog, and Graphify output, then pass the focused backend gate, frontend build, and deterministic replay smoke.

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
