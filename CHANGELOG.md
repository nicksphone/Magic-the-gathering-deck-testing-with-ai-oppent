# Changelog

This file tracks milestone-level changes. The root README stays focused on the current product state.
## 2026-07-18

- Choice and search resolution:
  - Added a shared library-search matcher for type, subtype, basic-land, permanent, and mana-value restrictions.
  - Tutor and landcycling moves now expose candidate cards and a validated selection schema to callers.
  - Explicit search selections are carried onto the stack and revalidated when they resolve, while older AI/replay callers retain deterministic first-match behavior.
  - Added frontend multi-select controls for human tutor choices.
  - Added regression coverage for legal non-first selections and rejected nonmatching cards; the consolidated rules/AI gate passes 225 tests and the three-game replay smoke has zero determinism failures.

## 2026-07-16

- Simulator diagnostics:
  - Centralized legal-move taxonomy across verbose round-robin and head-to-head traces. Restricted combat placeholders and ordinary passes no longer count as actionable options, while cycling, activated abilities, and equipment are included as meaningful decisions.
  - Added regression coverage for restricted placeholders and newly classified meaningful actions.
  - Added stable AI `reason_code` labels, raw reasoning, and legal action-type summaries to verbose traces. Training export, card-play analytics, and anomaly clustering now preserve these labels and distinguish deliberate interaction holds from unexplained passes.

- Rules coverage:
  - Cycling draws now pass through draw-replacement effects, and discard triggers caused by cycling are placed above the cycling ability on the stack.
  - Added regression coverage for optional cycling triggers and discard-trigger ordering.
  - Added fixed and variable landcycling/basic-landcycling search actions with validated X values, hand destination, and post-search shuffling.
  - Corrected Ramp fallback data for Cultivate and Migration Path, and expanded reusable search resolution for basic-land filtering, counts, shuffle instructions, and tapped battlefield placement.
  - Added generic named self-counter trigger resolution so triggered permanents can put counters on themselves without card-specific handlers.
  - Added resolution-time counted creature-type life-loss effects for common tribal ETB triggers, including plural subtype normalization.
  - Added a reusable top-N hand/exile/bottom choice effect with temporary play permission for the exiled card, covering Expressive Iteration-style selection.
  - Master AI now uses an adaptive bounded two-ply strategic search on developed late-game boards and includes activated abilities, cycling, equipment, and attacks in proactive planning candidates.
  - Added generic upkeep top-card transform resolution for double-faced cards, preserving the revealed card and applying back-face metadata only when the type condition passes.
  - Added dynamic characteristic-defining power/toughness for distinct card types across all graveyards, covering Tarmogoyf-style effects without card-name-specific logic.

- Rules coverage:
  - Damage-prevention overrides now distinguish global, target-player, target-permanent, combat-only, controller-scoped, and named-source “can't be prevented” text. Combat callers now pass explicit combat context.
  - Additional cast and activated costs now share generic sacrifice eligibility for creatures, artifacts, enchantments, permanents, and artifact-or-creature requirements. The chosen permanent is moved through ownership-aware replacement handling before the ability resolves.
  - Cycling now emits a structured cycle event after the activation is on the stack. Generic and named-card cycling triggers are matched through the event layer, with the trigger ordered above the cycling draw ability.
  - Activated abilities now parse and pay common combined costs such as `{T}, Sacrifice a creature`, `{1}, Discard a card`, and life payments before putting the ability on the stack. Unsupported cost forms remain unavailable rather than partially paying.
  - Added a first-class `cycle_card` action for fixed-cost cycling from hand. Cycling now pays through the normal mana engine, discards to the owner's graveyard as a cost, resolves its draw through the stack, and emits the normal discard event path.
  - Generic variable-cost cycling such as `Cycling {X}{1}{U}` now exposes only mana-payable non-negative X values and carries X into supported dynamic cycling triggers; alternate cycling costs remain future coverage.

- AI quality:
  - Master lookahead now resolves unanswered activated-ability and cycling stacks during simulation, while preserving branches where the opponent has a legal response.
  - Master and lower difficulty ranking now recognize cycling as a card-filtering action, while preferring land drops and meaningful spells when those options are available.
  - Activated sacrifice/discard outlets are now exposed to the same legal-move and tactical ranking paths as simple mana abilities.

- UI:
  - Human players can activate available cycling actions directly from the hand, including cards that are also castable.

- Validation:
  - Added focused regression coverage for legal cycling moves and stack-timed cycling draws.
  - Added named cycling-trigger ordering coverage; focused cycling/event/legal-move tests pass `44` tests.
  - Added X-value and dynamic cycling-trigger coverage. Full backend suite passes `438` tests with 43 deprecation warnings; frontend production build and deterministic replay smoke remain green.
  - Added regression coverage for artifact-or-creature additional costs.
  - Full backend suite passes `442` tests with 43 deprecation warnings; frontend production build passes; a three-deck deterministic replay smoke completed 3 games with 0 determinism failures.
  - Full backend suite now passes `443` tests after AI lookahead regression coverage.
  - Added regression coverage for tap-plus-sacrifice activated costs.
  - Full backend suite passes `435` tests with 43 deprecation warnings; frontend production build passes; a three-deck deterministic replay smoke completed 3 games with 0 determinism failures.

- Rules coverage:
  - Named-source attack triggers now match the attacking permanent generically, including Goblin Guide-style defending-player top-card reveals.
  - Added event-to-stack regression coverage so the trigger resolves through the structured Oracle effect path instead of being silently skipped.

- Validation:
  - Backend suite now passes `431` tests with 43 deprecation warnings.
  - Frontend production build passes after the trigger and regression updates.

- Simulator diagnostics:
  - Restored the missing battlefield snapshot helper in the overnight round-robin runner, allowing full verbose batches to execute.
  - Reworked anomaly clustering to use structured counters and termination status instead of treating every priority pass as a stall.
  - Six-deck diagnostics showed no invalid targets, cost failures, repeated error bursts, or missed land windows; a fresh three-deck run completed without anomalies.
  - Deterministic replay matrix now supports seeded best-of-1/3/5/7/9 match aggregation and validates the full match hash; best-of-three regression coverage was added.

- AI quality:
  - Added a generic graveyard-recursion tactical tag and qualifying-graveyard check so control threats that can recast spells are valued when they have real targets, without card-name-specific exceptions.
  - Added regression coverage for recursion-aware cast valuation.

- Card data reliability:
  - Card cache rows now persist Scryfall rulings and retain them through card and deck serialization.
  - Added `/cards/completeness` to report uncached cards, fallback-backed Oracle text, missing costs/type lines/legalities/rulings, face metadata gaps, and placeholder art.
  - Added regression coverage for complete, fallback-backed, and unresolved card metadata.
  - Deck import UI now displays the completeness summary immediately after a deck is imported.
  - Added saved-deck completeness endpoints for one deck or all distinct saved decks, including sideboard card names.

- Balance diagnostics:
  - Batch simulation now reports Wilson 95% confidence intervals and explicit extreme, skewed, and insufficient-sample alerts.
  - Testing Simulator now renders balance alerts alongside win rates and anomaly counters.
  - Win rates and confidence intervals now use resolved games only; timeout-only samples are reported as insufficient data instead of false 0%/100% matchups.

- Oracle coverage diagnostics:
  - Simulator analytics now counts unhandled Oracle-effect fallbacks separately from generic errors and attributes each fallback to the affected card.
  - Testing Simulator output now displays the cards that still use the fallback path, making rules-coverage work actionable instead of requiring raw-log inspection.
  - Added regression coverage for fallback counting and card-level attribution.

- Validation:
  - Backend suite now passes `421` tests.
  - Frontend production build passes after adding the unsupported-Oracle diagnostics panel.
  - Four-deck deterministic replay smoke completed 6 games with 0 determinism failures, 0 drift labels, and 0 anomaly hits.

- Rules correctness:
  - Controller-scoped creature, permanent, artifact, and enchantment ETB/death triggers are now evaluated before broad Oracle prefix matches, preventing opponent-controlled events from incorrectly firing “under your control” abilities.
  - Added regression coverage for opponent-controlled ETB events and retained coverage for scoped death events.
  - A completed Blue Control vs Ramp audit now reports card-level Oracle fallbacks; the next implementation targets are Arboreal Grazer, Torrential Gearhulk, and Nissa, Who Shakes the World.
  - Arboreal Grazer-style land-from-hand ETB resolution and Torrential Gearhulk-style graveyard instant/sorcery casting now use reusable effect handlers and the ordinary stack path.
  - Nissa's static/loyalty text is no longer reported as a false cast-time Oracle fallback; its actual layer-aware land and loyalty behavior remains tracked as unfinished work.
  - Nissa-style land mana doubling, target-land animation, and green-creature deployment are now implemented through reusable mana and effect handlers.
  - Storm the Festival-style top-five permanent deployment and Shark Typhoon-style X/X flying Shark triggers now use reusable top-library and spell-cast effect handlers.
  - Three-deck deterministic replay smoke completed 3 games with 0 determinism failures, 0 drift labels, and 0 anomaly hits.
  - Simple mana-cost activated abilities now generate legal actions and resolve through the stack; added Recruitment Officer-style top-four creature search coverage.
  - Temporary exile play permissions now persist in match snapshots, expire by turn, and generate legal cast/land actions from exile; added Light Up the Stage-style coverage.

- AI runtime stability:
  - `_cast_bias` now initializes board-role context before evaluating engine-tagged control spells, which removes a head-to-head crash in the simulator path.
  - Added regression coverage for the engine-tagged control cast-bias path.

- Validation and simulator diagnostics:
  - Overnight regression summaries now classify timeouts into long-game, stall, and rules-issue buckets instead of treating every timeout the same.
  - The CI regression gate now ignores long active games while still failing on likely stalls or rules regressions, which makes small validation runs less noisy.
  - Added regression coverage for the timeout classifier so long active games, stall loops, and rules issues stay distinct.

- Card data normalization:
  - Fallback card lookup now normalizes spacing and punctuation before resolving metadata, which improves coverage for common import-name variants.
  - Double-faced import names now also fall back to their front face before giving up, which improves hydration for Delver-style and other transform-style cards.
  - Added regression coverage for normalized fallback card-name lookup.

- Deck import parsing:
  - Deck parser import now accepts common `Mainboard`, `Maindeck`, `Sideboard`, and `SB:` section headers in addition to the previous sideboard-only cue.
  - Deck parser import now strips common set annotations like `[M11]` and `(XLN)` before exact and fuzzy lookup, which improves pasted decklist hydration.
  - Deck parser import now accepts `4x Card Name` multiplier notation and ignores common comment lines, which broadens pasted-list support.
  - Added regression coverage for those import headers.

- Rules coverage:
  - Prevention/replacement matching now covers broader controller/target wording for damage prevention, plus artifact-or-enchantment die replacement variants.
  - Added regression coverage for the expanded prevention/replacement wording.
  - Instant and sorcery resolution now places the spell into its owner's graveyard, closing a controller-vs-owner zone-movement bug on stack resolution.
  - Added regression coverage for owner-based graveyard placement from stack resolution.
  - Common "one or more" dies/discard trigger variants are now recognized alongside the singular forms, which broadens older-card and multiplayer-style Oracle coverage.
  - Added regression coverage for one-or-more creature-dies and discard triggers.
  - Subject-scoped base power/toughness setters now respect scoped Oracle text and deterministic battlefield order instead of falling back to a blanket controller-wide parse.
  - Added regression coverage for subject-specific base-PT setting and ordered base-PT overrides.
  - Damage-prevention replacements now recognize "you or a permanent you control" style wording, which broadens common ward/fog-style prevention templates.
  - Added regression coverage for the broader damage-prevention wording and for self-directed life-gain locks.
  - Artifact- and enchantment-specific enter-battlefield and death triggers now share the same event path as creature and generic permanent triggers, which keeps noncreature engines from dropping into the generic fallback path.
  - Combined artifact-or-enchantment trigger wording now matches the same event path as the separate artifact and enchantment clauses, which broadens noncreature engine coverage further.
  - Sacrifice triggers now also match artifact/enchantment wording and combined artifact-or-enchantment wording, which broadens aristocrats-style noncreature sacrifice engines.
  - Direct sacrifice resolution now uses card ownership for stolen permanents, matching the additional-cost sacrifice path and the destroy/death zone rules.
  - Library search now understands type-based tutor text for artifact, enchantment, permanent, and similar searches instead of relying only on name substrings.
  - Library search can now also move found cards directly onto the battlefield for battlefield-tutor wording, which broadens Collected Company-style resolution paths.
  - Battlefield tutors now respect count and mana-value limits when they move cards directly onto the battlefield.

- AI quality:
  - Block assignment now prefers preserving mana creatures when a better block exists, while still assigning them when they are the only profitable defense.
  - Added regression coverage for mana-creature preservation and forced blocking when only a mana creature is available.
  - Matchup-aware scoring now credits ramp acceleration more heavily in the early game and gives stabilization lines more weight when the board is under pressure.
  - Added regression coverage for ramp-vs-draw line selection and control-vs-sweeper line selection.
  - Engine-heavy artifacts and enchantments now receive explicit tactical weight in board evaluation and move scoring, so trigger engines are not treated like blank permanents.
  - AI trace exports now preserve opponent hand, library, and graveyard counts alongside the acting player's state, which improves hidden-information tuning for control and response-window play.
  - Opening-hand evaluation now uses a broader hand-profile model, which lets mulligan decisions keep real two-land ramp/control hands while still rejecting hands that lack early pressure.
  - Attack selection now uses the same hand-profile and board-role context, which keeps conservative decks from sending small attackers into hopeless blocks while still letting pressure decks commit when they are actually ahead or racing.

- UI clarity:
  - The controls panel now shows explicit interrupt-window state, including the current priority seat/controller and whether the timer is live, paused, or idle, so human response windows are easier to read during long games.

- Replay diagnostics:
  - First-divergence replay reports now include compact trace-context summaries for each side, which makes it easier to compare hands, boards, life totals, and action states without opening the full log.
  - Batch and matchup summaries now carry the same compact first-divergence trace context, so replay drilldown is consistent across the main reporting surfaces.
  - The Testing Simulator UI now renders that compact trace context directly, so the first divergence can be inspected without opening the raw JSON blob.

- Continuous-effect ordering:
  - Continuous-effect and replacement tie-breaks now use battlefield position in addition to timestamp-like metadata when multiple sources land in the same ordering bucket.
  - Added regression coverage for same-timestamp continuous sources so battlefield order now decides the winner instead of falling back to card id ordering.

## 2026-07-15

- Card sync / cache hydration:
  - Cached card serialization now accepts both ORM rows and dict-shaped repository returns, which closes a fallback path that could throw during blank-cache hydration.
  - Blank cached cards now merge fallback oracle text, mana cost, and type line during sync serialization, which keeps imported decks readable even before a remote refresh.
  - Added regression coverage for blank cached card hydration through the sync service.

- Rules coverage:
  - Battlefield-to-graveyard and battlefield-to-exile movement now uses card ownership for zone placement, which keeps stolen permanents from landing in the wrong graveyard or exile list.
  - Die-to-exile replacement now covers generic permanent wording as well as creature-only wording, so noncreature permanents respect the same exile replacement patterns.
  - Death-trigger collection now covers generic permanent-dies wording in addition to creature-dies wording, which lets common artifact and enchantment death synergies resolve from the same event path.
  - Legacy evasion keywords `shadow`, `fear`, and `intimidate` now affect blocking legality, which broadens older-card combat coverage.
  - Explicit `{C}` mana symbols are now tracked separately from generic mana, so colored mana can no longer pay colorless costs.
  - Generic "add one mana of any color" style triggers now choose a deterministic mana color from the controller's hand needs, which keeps landfall-style mana production aligned with the current game plan.
  - The mana preview checker now consumes pool mana while simulating payment, so one mana can no longer satisfy both a colored pip and a later generic requirement.
  - Replacement-source selection now follows timestamp-like battlefield ordering instead of raw player enumeration, which makes prevention and replacement resolution more deterministic.
  - Reanimation-style Oracle inference now targets creatures from any graveyard, not just the caster's graveyard.
  - Generic permanent-card recursion from a graveyard now resolves for lands and other permanent types, not just artifact or enchantment permanents.
  - Prowess-style noncreature-spell triggers now grant a reusable until-end-of-turn power/toughness pump instead of silently dropping the buff.
  - Magecraft-style cast-or-copy spell triggers now fire for copied instants and sorceries as well as the original cast.
  - Scryfall sync and token art lookups now retry on 429 responses with a shared backoff helper.
  - Card sync now falls back to cached metadata if the retryable Scryfall lookup still fails.
  - Continuous PT-setting effects now recognize common "become 1/1" style phrasing in addition to explicit base power/toughness wording.
  - Additional-cost sacrifices now send stolen permanents to the owner's zone instead of the controller's zone.
  - Oracle target hints now surface artifact and enchantment permanents for Disenchant-style removal spells, which lets the AI and effect resolver choose noncreature permanents without card-specific hardcoding.
  - Oracle target hints now also surface generic nonland permanents, which broadens Vindicate-style and permanent-tap removal coverage.
  - Oracle inference now recognizes counter-target-activated-ability and counter-target-triggered-ability wording, which lets the stack resolver counter abilities instead of only spells.
  - Interactive X-spells now fall back to the smallest positive legal X when the card has a real target, which prevents the zero-value retry loop seen on March of Otherworldly Light-style plays.
  - Graveyard recursion now supports artifact and enchantment permanents in addition to creature recursion, which broadens support for common return-to-battlefield effects.
  - Added regression coverage for stolen permanents dying into their owner's graveyard.
  - Added regression coverage for graveyard recursion that targets an opponent's graveyard.
  - Added regression coverage for the shared 429 retry helper.
  - Added regression coverage for cached card fallback after repeated Scryfall failure.
  - Added regression coverage for common PT-setting phrasing.
  - Added regression coverage for ownership-aware additional-cost sacrifices.
  - Added regression coverage for prowess-style noncreature-spell triggers and cleanup expiry.
  - Added regression coverage for copied-spell magecraft-style trigger behavior.
  - Fixed the legend-rule state-based-action loop while tightening ownership-aware zone movement.
- AI quality:
  - Board-role planning now distinguishes stabilize, convert, race, and control states so complex boards are not scored as one flat midgame heuristic.
  - Mode scoring for modal, split, and X-style spells now weighs board role and board pressure more directly, which improves counter, removal, token, draw, and ramp choices on live boards.
  - Modal and transform face selection now uses board pressure and conversion context rather than defaulting to the first printed face.
  - X-value selection now scores token, draw, and damage spells against board pressure and archetype pressure so the AI avoids low-value early dumps.
  - Log priors now record board-role-specific cast timing from replay traces so the AI can separate control-board timing from race-board timing when choosing between pass and cast lines.
  - The priors builder now also consumes exported training examples, which lets board-role hints from extracted decision rows reinforce the same timing model.
  - The fallback card corpus now covers a much broader set of common aggro, tokens, control, and elf-shell cards, so blank-oracle imports are less likely to turn into simulator no-ops.
  - Added regression coverage for the new board-role classification and role-sensitive pass bias.
- Simulation diagnostics:
  - Replay comparison outputs now include a concise first-divergence excerpt with the exact divergent lines and nearby context, which makes root-cause review faster in batch reports and regression matrix output.
- Training data exports:
  - AI training examples now include a lightweight board-role hint so downstream tuning can separate stabilize, convert, race, and control states without re-parsing raw logs.

- Verification:
  - Confirmed the focused ownership and legend-rule regressions pass.
  - Confirmed the full backend test suite passes.
  - Confirmed the frontend production build still succeeds.

## 2026-07-10

- Rules coverage:
  - Oracle inference now supports common graveyard-to-battlefield reanimation text for creature cards.
  - Added regression coverage for graveyard-target hints, oracle inference, and battlefield reanimation resolution.

- Simulator corpus refresh:
  - Diagnostic scripts now refresh built-in and expansion decks before head-to-head, replay, and CI-gate runs so simulations do not accidentally use stale local deck rows.
  - Added regression coverage for the shared builtin-deck bootstrap helper.

- Runtime tooling:
  - Backend diagnostic scripts now bootstrap the backend import path correctly when run directly from `backend/`, so head-to-head, replay, and regression helpers no longer fail with `ModuleNotFoundError`.
  - The bounded CI regression gate now forwards `--max-decks` into the overnight round-robin stage, so small verification runs stay bounded instead of expanding to the full corpus.
- AI stability:
  - The AI now ignores restricted placeholder combat actions such as `attack_restricted`, which removes the repeated declare-attackers stall that could trap some simulator runs.
  - Added regression coverage for ignoring restricted combat placeholders during AI decision selection.
- Verification:
  - Confirmed `pytest -q` passes after the runtime-tooling and AI-loop fixes.
  - Confirmed a bounded CI regression gate completes successfully on a small deck sample.
  - Confirmed direct head-to-head simulations finish without the restricted-attack stall on representative pairings.

- Rules coverage:
  - Loyalty ability parsing now recognizes `-X`/`+X` style planeswalker abilities and carries X-value handling through move generation, resolution, and AI materialization.
  - Added regression coverage for X-loyalty planeswalker abilities so they resolve with the chosen X value instead of failing like a malformed cost.
- AI deck analysis:
  - Deck analysis now distinguishes actual split cards from other face-based imports so combined mana costs are only used for split-style cards while modal/adventure-style imports keep their primary face cost.
  - Imported deck analysis now folds `card_faces` into archetype scoring so split and modal cards contribute their actual text and type data instead of being flattened to the front face only.
  - Added regression coverage for face-aware deck analysis on synthetic modal/split imports.
- AI tactical valuation:
  - Board evaluation now reads the active face of modal/transform permanents when scoring battlefield value.
  - Added regression coverage for active-face board valuation.
- AI matchup profiling:
  - Matchup profiles now differentiate control, ramp, tempo, and token matchups more aggressively so the agent's timing heuristics have better inputs.
  - Added regression coverage for control-vs-aggro hold-up bias and tempo-vs-control proactivity bias.
  - Move scoring now applies matchup-profile pressure directly to pass, attack, and cast choices instead of only using it in a couple of early heuristics.
  - Added regression coverage showing matchup pressure now changes score outputs for counterspells and tempo attacks.
- Simulator diagnostics:
  - Anomaly clustering now recognizes multi-word land-drop misses and repeated main-phase pass loops from AI trace data.
  - Added regression coverage for the improved anomaly classifier.
- UI readability:
  - Battlefield zones now show compact mana-pool pips so floating mana stays visible without adding wide text blocks.
  - The match status grid now surfaces the active priority seat directly.
  - The compact battlefield, stack, priority, and mana presentation builds successfully after the latest layout refinement.
- Simulator diagnostics:
  - The deterministic regression matrix now selects representative decks across archetypes before filling any remaining slots, which improves pair coverage in bounded runs.
  - The verbose overnight round-robin diagnostics now use the same representative deck selection, so long-run validation no longer truncates to the first source-filtered rows.
  - The shared representative selector now accepts both ORM rows and script-local deck dictionaries, which keeps diagnostics consistent across scripts.
  - Added regression coverage for archetype-spread deck selection and unknown-archetype fallback.
- AI tactical planning:
  - Control and midrange agents now deploy a large finisher earlier on a safe turn-four board instead of waiting for a fixed turn-five threshold.
  - Master difficulty now invokes the deeper strategic planner earlier in complex midgame boards for control, counter-heavy, midrange, ramp, and tempo shells.
  - The deeper strategic planner now evaluates a wider candidate beam on master difficulty so complex boards are less likely to miss the best non-obvious line.
  - Combo-lite matchup profiles now bias toward proactive conversion against control and counter-heavy shells instead of staying at the default generic profile.
  - Card-play analytics now separate strategic main-phase pass windows from combat-step passes so stall summaries do not over-report harmless blocker windows.
  - The analytics summary now includes pass-window examples and richer pass accounting for later drilldown.
  - Verbose AI traces now include active-player and priority-player context.
  - Training exports now preserve active-player and priority-player context for downstream AI analysis.
- Card hydration:
  - Partial cache rows now merge with fallback metadata so common cards keep oracle text, mana cost, and type-line data instead of logging blank oracle misses.
  - Missing art now falls back to name-specific local SVG placeholders instead of generic blanks, which makes token and uncached-card images easier to identify at a glance.
  - Cached double-faced cards now reuse face-level art when the root image is missing, which improves display coverage for transform and modal imports.
  - Token creation now emits enter-the-battlefield triggers, which lets Soul Warden-style and token-ETB cards see the same event path as normal permanents.
  - Token art fallback now prefers a generic token creature asset before the blank placeholder path, improving readability when remote token art is unavailable.
  - Enter-the-battlefield trigger matching now covers token creation and permanent-ETB wording under your control, which improves token engines and permanent-based trigger cards.
  - ETB matching also recognizes the common “another permanent enters the battlefield under your control” wording, which broadens token and engine synergies beyond creature-only cases.
  - Sacrifice-trigger emission now fires from normal sacrifices and additional-cost sacrifices, which improves aristocrats-style payoff cards.
  - Discard-trigger emission now fires from normal discard effects and additional-cost discards, which improves Wheels and Waste Not-style payoff cards.
  - Combat-damage trigger emission now fires when attackers connect in combat, which improves combat-step payoff cards and creature combat triggers.
  - Attack-trigger emission now fires when attackers are declared, which improves attack-step payoff cards and combat synergies.
  - Block-trigger emission now fires when blockers are assigned, which improves block-step payoff cards and defensive synergies.
  - Trigger resolution now falls back to the oracle parser for action-bearing trigger text, which broadens support for create, destroy, tap, discard, and similar triggers.
  - State-based actions now emit death/permanent-death events for lethal creatures and 0-loyalty planeswalkers, which keeps SBA-driven triggers aligned with explicit destroy/sacrifice paths.
  - Board evaluation now rewards trigger-engine permanents, improving AI recognition of sacrifice, ETB, discard, and combat payoff engines.
  - Replay drift classification now recognizes attack, block, sacrifice, discard, ETB, death, and combat-damage log lines, which improves root-cause reports.
  - Land plays now emit battlefield-entry events, enabling landfall-style triggers from actual land drops.
  - Damage-prevention replacements now apply to creature-targeted damage as well as player-targeted damage, broadening common fog/ward-style interactions.

- Rules coverage:
  - Added generic Oracle inference and handlers for targeted and mass artifact/enchantment removal.
  - The new coverage includes `destroy target artifact or enchantment` style cards and `destroy all artifacts and enchantments` sweepers.
  - Creature death replacement now applies consistently through destroy, sacrifice, combat cleanup, and state-based actions.
  - Death replacement now also matches common `nontoken` and `another creature` Oracle variants instead of only one phrasing.
  - Death-trigger collection now respects controller-scoped clauses such as `a creature you control dies`.
  - Additional-cost sacrifice now also respects exile-instead-of-dying replacement effects.
- Simulator diagnostics:
  - Batch simulation now records the first divergence between the first two games in a matchup.
  - The Testing Simulator UI now surfaces that first-divergence report directly in the results panel.
  - Pair-level AI diagnostics now also surface the first divergence for each suspicious matchup, so replay drift is visible without manual log comparison.
  - Anomaly clustering now separates pass loops, X-value errors, stack-target mismatches, and cost-payment failures so simulator logs point at the actual root cause faster.
  - API-level anomaly scans now count main-phase pass loops and repeated X-value errors in the same way as the offline cluster report.
  - The Testing Simulator panel now renders anomaly counters as named rows, not just raw JSON.
- AI X-spell policy:
  - Low-impact X-spells now require a meaningful minimum X instead of being forced at trivial values.
  - Token-producing X-spells such as `Secure the Wastes` are skipped early when they would only produce an insignificant board state.
- AI control pacing:
  - Control, Counter-heavy, and Tempo agents now distinguish urgent interaction from stable value turns so they do not over-pass into draw-spell lines.
  - Stable main phases can now prefer castable value spells over idle hold-up when no real response is needed.
- AI face selection:
  - Modal and transform-style face selection now scores the actual face `type_line`, which improves role-sensitive choice on split/DFC-style cards.
  - AI valuation now better separates creature, instant, and value faces when the board state changes.
  - Modal face scoring now accounts for matchup pressure and archetype so control decks favor interaction faces while aggro decks favor board-development faces.
  - Split and multi-mode spell selection now scores the actual mode text so the AI can pick interaction, value, or board-building modes based on state instead of defaulting to printed order.
- AI X-spell selection:
  - X-spell casts now choose a value based on archetype, board pressure, and diminishing returns rather than always taking the highest legal X.
  - Control decks now avoid overcommitting into empty boards when a smaller X is tactically cleaner.
- Diagnostics classification:
  - Replay divergence now classifies common root causes such as pass-vs-action, land-drop mismatch, cast-choice mismatch, and cast-resolution error.
  - Structured AI TRACE divergence now distinguishes stack-target, mode-choice, and face-choice mismatches when the first divergence is a cast decision.
  - Anomaly clustering now recognizes land-drop misses correctly instead of relying on a broken regex pattern.
  - Timeout classification now separates likely stalls, rules issues, and long-but-active games in replay diagnostics.
- UI battlefield scaling:
  - Crowded battlefield rows now shrink density-aware card and land render sizes earlier so large boards stay readable before they become cramped.
  - Hover preview remains available for closer card inspection when the board is compressed.
- UI density polish:
  - The stack log and priority-stop controls now use more compact layouts for long-session scanning.
- Regression coverage:
  - Added backend tests for the batch first-divergence report and the stricter X-spell selection floor.
  - Added regression coverage for control choosing a value draw spell over idle pass priority in a stable main phase.
  - Added regression coverage for replay classification and anomaly clustering buckets.
  - Added regression coverage for modal face scoring that reacts to face type lines and board state.

## 2026-07-09

- Sideboarding flow hardening:
  - Match controllers now track whether a player has already sideboarded for the current finished game.
  - The `/matches/{match_id}/sideboard` endpoint now rejects repeated sideboard applications before the next game starts.
  - The next-game transition clears the per-game sideboard lock so BO3 flow remains consistent across games.
- Test coverage:
  - Added regression coverage for the single-sideboard-per-game contract and the reset that happens on `next-game`.
- Search and cleanup polish:
  - Library search effects now collect all matching cards instead of stopping at the first hit.
  - Destroyed permanents clear stale damage and prevention counters before moving to the graveyard.
- Phase/progress correctness:
  - Turn progression regression coverage now explicitly exercises postcombat main, end step, cleanup, and the next untap.
  - `_deal_unblocked_damage()` now has a consistent integer return type contract.
- Oracle fallback cleanup:
  - Unresolved Oracle text now maps to an explicit `noop` effect instead of pretending to be life gain.
- BO3 UI polish:
  - The match controls panel now shows score, game number, match target, and sideboard availability in a denser status grid.
  - The between-games panel now says explicitly whether sideboarding is open or the match is already complete.
- Replay diagnostics:
  - Replay comparison logic now lives in reusable analytics helpers.
  - Diagnostics can report the first diverging log line and classify whether the mismatch is an action mismatch or a broader replay drift.
  - AI diagnostics now emit turn-level trace summaries with board snapshots for the first game in each matchup.
- Batch determinism:
  - Batch simulation now seeds each game deterministically from the matchup and game index.
  - Batch responses now include per-game results with seeds, winners, turn counts, and timeout flags.
- Rules coverage:
  - Generic destroy-all-creatures resolution now exists for Oracle text that says to wipe the board.
  - The resolver path is covered by regression tests using a real sweep effect.
- Simulator UI polish:
  - The Testing Simulator now shows per-game batch results in addition to the first-game excerpt and aggregate stats.
- AI tactical evaluation:
  - Battlefield scoring is now keyword-aware and values evasive or protected threats more accurately.
  - Control removal decisions now weigh target threat level instead of treating all removal targets equally.
- Training export enrichment:
  - Structured training rows now include board snapshots derived from AI trace logs.
- Simulator UI polish:
  - The Testing Simulator now shows live job status, a progress bar, failure output, and compact first-game turn/log summaries while batch jobs run.
- Custom deck analysis:
  - Archetype classification now uses cached card metadata and curve shape when available, not just deck-name keywords.

## 2026-06-11

- Continuous-effect diagnostics:
  - Layer traces now expose ordered applied layer entries for overlapping static effects.
  - Combined power/toughness plus keyword clauses are parsed as a single static effect instead of dropping the keyword half.
- Deck metadata completeness:
  - Deck import responses now include resolved cached card metadata for mainboard and sideboard lines when available.
  - This exposes face data, image URIs, oracle text, and legality metadata alongside the parsed deck list.

## 2026-06-07

- Combat protection and prevention fixes:
  - Trample spillover into protected planeswalkers now respects protection.
  - Combat damage now respects `damage can't be prevented` before consuming prevention shields.
  - Regression coverage added for both cases.
- Rules/AI groundwork:
  - Modal/split face selection is preserved through cast resolution and AI valuation.
  - Replay determinism remains stable on the current regression matrix.
  - Trigger ordering metadata, replacement traces, and continuous-effect traces are available for diagnostics and training export.

## 2026-06-06

- Combat flow fixes:
  - Blocker declaration hands priority back to the active player after assignment.
  - The block-declaration window is single-use per combat step to prevent repeated blocker prompts.
  - A Tempo vs Drain timeout loop was eliminated by the combat window fix.

## 2026-05-18

- AI and diagnostics milestones:
  - Added stack-only 2-ply tactical search for complex counter windows.
  - Added inevitability-driven control endgame policy.
  - Improved threat scoring for artifacts, enchantments, and planeswalkers.
  - Added deterministic replay drift labeling and first-divergence reporting.
  - Added structured training trace export from verbose head-to-head logs.

## 2026-05-17

- Core AI stability improvements:
  - Fixed land-play legality leaks in the AI action selector.
  - Added priority-pass logging for deeper debugging.
  - Improved control matchup behavior and built-in deck color correctness.

## 2026-05-16

- Early infrastructure and matchup improvements:
  - Better deck deduplication in `/decks`.
  - Expanded fallback metadata for control/removal package cards.
  - Land tapping logic improved for dual/multi-color lands.
  - Added matchup profile scaffolding and endgame policy hooks.
## 2026-07-16 - Runtime Connectivity Hardening

- Added production API URL resolution for separate frontend/backend deployments.
- Added a frontend backend-health indicator with periodic checks and retry control.
- Documented `VITE_API_BASE_URL`, LAN usage, and reverse-proxy routing.

## 2026-07-16 - Durable Sessions and Ability Boundary

- Added application-level JSON snapshots for active matches, including mutable zones, stack, priority, and RNG state.
- Restored active matches and simulator job metadata during backend startup.
- Marked interrupted simulator workers as failed with an explicit restart reason.
- Added a structured `AbilitySpec`/`EffectSpec` boundary around Oracle inference and regression coverage for unsupported action text.
- Corrected AI combat evaluation to use effective granted keywords instead of only printed card keywords.
- Revalidated the current branch with a 15-game representative matrix: zero determinism failures and no drift labels.
- Expanded combat landwalk legality beyond the five basic types to cover nonbasic, snow, desert, wastes, and legendary landwalk variants.
- Fixed the built-in deck API route's missing `BUILTIN_DECKS` import and added API smoke coverage for health, deck loading, and card images.
- Routed triggered-ability fallback parsing through the structured ability boundary used by spell and loyalty resolution.
