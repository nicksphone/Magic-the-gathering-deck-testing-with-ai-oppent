# MTG Deck Testing Lab

MTG Deck Testing Lab is a desktop-first Magic: The Gathering deck testing application for rules-aware playtesting, AI-vs-AI validation, and long-run matchup analysis.

It is designed for serious deck work:
- Human vs AI playtesting
- AI vs AI simulation
- Batch matchup analysis and replay diagnostics
- Persisted diagnostic-run browsing with bounded anomaly/root-cause snapshots
- Custom deck import and deck library management
- Rules-engine-first gameplay logic with local persistence

## Current Features

### Gameplay
- Two-player match flow with turn structure, priority, stack, combat, cleanup, and turn advancement
- London mulligans through zero cards, with deliberate ordered bottom-card selection for human seats
- Manual phase progression and autoplay
- Land drops, casting, activated abilities, combat actions, and response windows
- Seat-aware human hand and ability controls, including permitted exile/top-library spells, explicit crew selection and Ninjutsu; unhandled legal action kinds show a warning
- Both public graveyards and face-up exile zones are available as compact, scrollable lists with card preview on hover or keyboard focus. Face-down exiles contribute to the total count without exposing their identities; AI hands remain hidden.
- Bounded typed deck/action inputs, checked copy-on-write human actions, structured request errors and visible manual-action failure feedback
- Live match, legal-move and saved-match discovery responses pass bounded runtime shape checks before entering the UI; broader generated API contracts remain unfinished
- Public live-match responses hide AI-controlled hands while retaining hand counts; AI legal-move queries cannot expose their playable cards
- Unrevealed hand-tutor and top-card hand-choice results are omitted from the public match log; publicly exiled cards remain named. AI-owned pending mechanic choices expose only a generic status, not hidden library options or order. Shared-device human-vs-human still lacks per-seat authorization.
- Testing Simulator job responses check status, progress and completed summary metrics at runtime; the result no longer crosses the UI boundary as `any`
- Batch results and the Testing Simulator label win rates `exploratory`, never rules-certified; they list detected unsupported mechanics in the input decks. This does not block a run or certify cards with no warning.
- Saved-match discovery/refresh recovery, automatic-play pause/resume, one coordinated UI writer and durable revision/idempotency metadata for guarded match mutations and match creation
- Interactive BO3 matches persist a root seed and derive per-game seeds without exposing them during play. The prior game's human loser chooses play or draw between games; AI losers choose play by default. The choice and subsequent game survive match restore.
- Simultaneous life/poison state-based losses end the game in a draw. Drawn BO3 games do not award a point, and the same play/draw chooser retains the choice for the next game; this is covered through snapshot, HTTP and rendered controls. Seeded diagnostic series distinguish drawn games from timeout games and report an explicit draw cap.
- Attempting to draw from an empty library is recorded until the next state-based-action check, rather than immediately assigning a winner. Both players failing to draw before that check produce a draw; multi-card draw effects stop and do not claim undrawn cards in the log. Snapshot and replacement-path regressions cover this bounded rule.
- Exact "Each player draws N/X cards" clauses use active-player-first order, with each player's individual draws, replacements and choice continuation handled by the shared draw path. Vision Skeins and Prosperity fixtures cover stack resolution, X, snapshot continuation and simultaneous deck-out; other multi-player draw wordings remain unverified.
- Seeded AI-vs-AI BO3 regressions use real built-in Aggro/Burn and Control/Ramp decklists, restore the controller from SQLite between games, and verify natural match finishes through HTTP; an Aggro/Burn series also finishes through rendered UI controls. Scripted human-vs-AI and human-vs-human BO3s use Mono Red Aggro against a 60-Island opponent through rendered mulligan, land, cast, attack, pass, trigger-order and next-game controls. These are lifecycle checks, not competitive AI or broad human-game acceptance.
- Default spell timing: sorceries and non-flash permanents require an empty-stack main phase; instants and flash remain usable in response windows
- Damage, prevention, protection, replacement effects, trigger resolution, and state-based actions
- Declared attackers deal combat damage automatically on entering the combat-damage step, before priority; an explicit repeated damage action cannot deal it twice
- Combat with first or double strike uses separate first and regular damage priority windows; live autoplay, batch simulation and replay advance through priority passes rather than forcing both windows closed. Participants are recorded for snapshot-safe second-step eligibility, and the UI labels the active window.
- Human controllers can divide combat damage among multiple blockers, or among multiple attackers blocked by one creature, before the damage step resolves. The numeric choice survives snapshots; trample checks lethal damage assigned by all attacking sources in that step before damage reaches the defender. A pending split can be restarted before damage is dealt. AI uses a bounded threat-based allocation, while low-level unattended calls retain a deterministic fallback. First- and double-strike steps request separate choices.
- Supported spell-driven discard now lets the affected human choose cards from their current hand at resolution; the choice survives snapshots and resumes later spell effects. AI-controlled seats choose lower-retention cards instead of the first hand entries. Explicit random discard uses seeded RNG without a choice window. This is not complete coverage of every discard wording or cross-event trigger interaction.
- Supported "each player discards N cards" spells now request choices in active-player order, keep earlier selections private, and discard both players' selections in one event batch after all choices are made. The real Delirium Skeins spell is covered by engine, snapshot, AI and two-seat browser tests. Random variants bypass human selection. Another-player chooser wording and competing replacement ordering remain open.
- Supported "target opponent reveals their hand; you choose a card; that player discards it" wording now targets only an opponent and gives the caster the resolution choice. The Coercion path exposes the revealed options in that caster's legal move, retains ordinary hidden-hand behavior outside the reveal window, and survives a snapshot. The player-target dropdown now has an accessible label. Other revealed-hand selection wordings and per-seat authorization for shared-device human matches remain open.
- Selective revealed-hand discard also supports the printed nonland restriction on Thoughtseize and noncreature, nonland restriction on Duress. The public match log records the entire revealed hand, while the chooser offers only cards eligible under the printed restriction. Thoughtseize's 2-life loss waits until the selection resolves and still occurs when no card qualifies; it does not occur if its sole target becomes illegal. Human and AI use the same filtered choice options. Other reveal-and-choose grammars remain unverified.
- The same revealed-hand chooser supports Inquisition of Kozilek's nonland mana-value ceiling and Despise's creature-or-planeswalker restriction. These are exact supported Oracle patterns; other comparisons, conjunctions and reveal effects are not implied.
- Supported reveal-and-choose clauses may exile the chosen card instead of discarding it. Appetite for Brains applies its mana-value minimum, lets the caster choose at resolution, and moves the chosen card from hand to exile without a discard event. The reveal and chosen exile are logged. Both battlefield exile trays now list and preview face-up exiled cards; a face-down exile is count-only and its identity is withheld from the public response. Effects that exile cards face down remain outside the supported rules corpus.
- Live matches, restored matches, batch analytics and verbose head-to-head diagnostics now supply both deck archetypes to their agents; the diagnostic runner also enables the same AI mechanic-choice windows as replay. When selecting from an opponent's revealed hand, AI hand-retention scoring uses that opponent's archetype when known. This is a bounded heuristic, not a general strategic model.
- Combat-damage events include actual trample damage to a defender and damage dealt by blockers; source-specific player-hit triggers do not fire for another creature's damage. The damage step stages those events with resulting death triggers before a shared APNAP trigger-order choice, and staged triggers survive snapshots. Human death-replacement continuation and broader state-based-action waves still need certification.
- If a blocker has banding, its defending controller chooses the attacker's supported damage split; if a blocker is blocking an attacker with banding, the active player chooses that blocker's supported split. The UI and AI follow the choice owner. Ordinary banding is inferred from Oracle text in live deck construction, distinct from "bands with other." Human players can select an ordinary attacking band; its legal direct blocks propagate to all live members and persist through snapshots. "Bands with other" remains unsupported, and AI does not yet form bands strategically.
- Current verification: 1,278 isolated backend tests pass; frontend lint/build/unit and the full loopback Chromium harness pass, including drawn-game BO3 advancement, public graveyard/exile inspection, both-seat discard, and Coercion/Thoughtseize/Duress/Inquisition/Despise/Appetite revealed-hand choices. The browser harness also covers both compleated payment branches with rendered loyalty, modal spells, graveyard return, human-chosen X-life cost, conditional lands, capped draws, manual nonland mana, combat and trigger choices, recovery and natural BO3 paths. A seeded three-game BO3 replay resolved in 60 total turns without timeout, anomaly label or determinism drift; an earlier four-deck matrix completed 15 games without timeout or determinism drift. These checks are not load, balance, rules-corpus or AI-quality certification.
- Land identity and deck-analysis land counts follow explicit card types/type lines, with exact basic-name fallback only for missing metadata; mana abilities and land-name substrings do not create land plays, and AI land priority uses offered legal moves only
- Lands with the supported "pay 2 life or enter tapped" wording offer explicit choices on land plays and resumable choices when effects put them onto the battlefield from hand, library or graveyard. Forced-tapped effects and payment legality share the same pre-entry helper. Multiple effect-driven entries now defer payment and ETB triggers until all choices and entries finish, preserving human trigger ordering across a snapshot. This is bounded wording support, not general replacement-effect certification.
- Life-total locks with the supported "can't change" wording suppress gain/loss and noninfect damage life changes, prevent nonzero life payments, and still allow damage to count for an unlocked opponent's lifelink. Activated and additional costs may pay exactly the remaining life when no lock applies. Positive payments now emit separate amount-bearing events; supported Font of Agonies-style counter triggers are staged above the paid-for spell or ability, including land-entry payment. Other pay-life wording and broader simultaneous replacement ordering remain unverified.
- Spells with the supported "pay X life" additional-cost wording require an announced affordable X and offer a bounded human input. Supported all-creatures `-X/-X` resolves across both battlefields through cleanup; AI uses a bounded board-value choice rather than always spending maximum life. The specific Toxic Deluge path is engine, HTTP and browser tested; other variable-cost/effect wordings remain unverified.
- Battlefield re-entry clears the prior object's counters, marked damage and until-end-of-turn power/toughness modifiers before supported Escape/entry counters are added. Direct and mass exile paths clear old counters after supported leave triggers inspect the departing object; graveyard paths clear them after supported death triggers are collected. Printed "counters remain ... other than hand or library" wording preserves real counters where allowed. Battlefield exits reset transformed faces, break old attachments and end temporary control durations after leave triggers are collected, including lethal spell damage. Departing permanents retain a snapshot of pre-exit effective power, toughness, controller, types and Oracle face for supported death triggers; simultaneous wipes capture all affected permanents before moving any. The snapshot survives match restore and is cleared on battlefield re-entry. Copied characteristics, broader last-known-information consumers and other zone-change state still need a wider audit.
- The supported artifact-to-graveyard trigger clause fires when an artifact actually reaches the graveyard through destruction, sacrifice, or a simultaneous creature wipe, including when its trigger source dies in that wipe. Marionette Master's printed opponent-life-loss clause uses its effective or last-known power. Rest in Peace replacement suppresses the graveyard trigger. Optional-payment variants and other artifact-death effects are not covered by this clause implementation.
- A sacrifice groups its supported leave, graveyard-death and sacrifice triggers into one ordering window, preserving an enclosing staged action. Merchant of Venom's printed untargeted counter trigger can be ordered with Marionette Master's graveyard trigger; it also sees an opponent's sacrifice or one replaced by exile. Supported one-damage "any target" sacrifice triggers such as Mayhem Devil now choose a player, creature or planeswalker as the trigger enters the stack and recheck legality at resolution. This does not cover Battles or arbitrary triggered clauses.
- Combat lifelink routes one gain-life event per damaging source through supported gain replacements, including Alhammarret's Archive-style doubling and Nefarious Lich-style gain-to-draw conversion. Human matches can choose between multiple applicable gain replacements; the paused damage step, remaining gains, state-based actions and staged triggers survive snapshots. Double-strike damage windows apply gains separately. Broader cross-event replacement ordering remains unverified.
- Deck archetype estimates use cached layout to distinguish split cards from modal/transform faces; modal front-face cost and type drive curve and creature-density priors. These descriptive estimates do not prove strategic play quality.
- Continuous-effect and replacement ordering use deterministic battlefield tie-breaks when timestamps collide
- Multiple prevention/replacement candidates use one explicit or deterministic timestamp-ordered choice per event, with source metadata preserved for replay diagnostics
- Continuous and replacement sources carry persisted monotonic effect timestamps, with deterministic tie-breakers for legacy snapshots and same-timestamp entries
- Continuous-effect diagnostics expose explicit layer ordering for supported keyword and power/toughness effects
- Supported `can't have` keyword overrides remain authoritative even when a later effect grants the keyword
- Draw/life replacement chains preserve consumed sources to prevent repeated application loops
- Canonical unconditional and "except the first one you draw in each of your draw steps" draw-doubling text is supported per actual draw. Multiple sources, spell/turn draws, dredge pauses, human choices and snapshot-safe draw-step counts have focused coverage. Alhammarret's Archive-style life-gain doubling is separate from its draw clause. Other conditional replacement families remain unsupported.
- Supported "each player/opponent can't draw more than one card each turn" static abilities count successful draws on either player's turn. Prohibited draws are skipped before replacement or dredge choices and do not cause empty-library loss; the count survives snapshots and resets when the turn changes. Spirit of the Labyrinth, Narset and Divination fixtures cover this family. Other draw prohibitions and optional multi-draw wording remain unverified.
- Human-controlled matches pause supported top-level and direct draw-step replacement events and present legal `choose_replacement` buttons; pending draws and stack items survive snapshots and resume after selection. AI/replay uses deterministic timestamp ordering.
- Human-controlled simultaneous trigger groups pause before stack insertion and expose validated `choose_trigger_order` moves; APNAP grouping and AI/replay fallback remain deterministic.
- Supported single-target ETB, self-cast and bounded sacrifice-damage abilities choose targets in their trigger window, separate from the permanent spell. Human choices survive snapshots; unattended play selects a legal target, and target legality is rechecked on resolution. Supported optional triggers offer a separate accept/decline decision at resolution. This is not yet a general triggered-ability target/mode model.
- Unconditional battlefield text granting a player hexproof or shroud now filters spell and trigger target choices and is rechecked at resolution. Hexproof still permits the protected player's own spells; shroud does not. Untargeted damage still applies. Conditional/temporary player grants and player protection from a quality remain outside this bounded implementation.
- For supported single-target player-or-permanent actions, selecting one target in the GUI clears the other, including on selected modal faces. Multi-target actions retain independent selections.
- Supported `Choose one` and `Choose two` spells expose only modes with legal mandatory targets; targetless modes stay castable when targeted modes cannot be chosen. AI and the human mode picker use the same available-mode list. Selected modes compile in printed order with independent target announcements. Cryptic Command counter/return can target a stack item and a permanent; Kolaghan's Command destroy/damage can target two different permanents. Either valid mode resolves when the other target becomes illegal; both illegal targets stop the spell. The printed return-creature-card mode uses the announced card in your graveyard, not an arbitrary card. Human and AI casts use per-mode target choices. Repeated modes, multiple targets within one mode, and general Oracle interpretation remain open.
- AI target materialization now selects only players offered by legal target hints. Battlefield target hints also omit creatures and other permanents protected by hexproof, shroud, or protection from the source. When a player shield leaves a pure direct-damage spell with only friendly targets, automated play holds that spell instead of attempting an illegal cast or burning its own player; an exposed opposing creature remains a valid damage target. This bounded safeguard does not plan around all modal or multi-effect spells.
- Divided-damage spells recheck each announced recipient at resolution. Illegal recipients take no damage, legal recipients retain their original allocation, and a spell with no legal recipients does not resolve. Protection is checked for divided recipients at announcement as well as resolution.
- Human-controlled lethal creature deaths in state-based actions and combat cleanup pause for multiple die replacements and resume through the same ownership-correct zone-change path.
- Human-controlled legend-rule zone changes use the same resumable die-replacement choice contract; chained prevention choices and simultaneous SBA batching remain under active rules hardening.
- Damage prevention re-evaluates the modified event and applies remaining applicable sources once each; human matches receive follow-up choices for the chain, while AI/replay uses deterministic timestamp ordering.
- Common continuous `can't have` keyword overrides are applied after applicable grants through deterministic layer ordering.
- Simultaneous lethal creature state-based actions batch zone changes and deduplicate supported `one or more` death triggers before stack insertion.
- Supported "when this creature dies" abilities are collected from the departed creature after zone movement; a Doomed Traveler combat regression resolves its 1/1 flying Spirit. Generic colored-token parsing separates the token name from its color, preserves that color across snapshots, and exposes it in the card view and hover preview.
- Saga chapters can create one-shot next-creature entry counters and transform a double-faced Saga through the stack; pending delayed entries survive snapshots and expire at cleanup.
- Master+ uses a bounded three-ply strategic search on late, developed boards with a reduced candidate beam; early states retain cheaper search.
- AI land-only target actions now materialize the selected land without depending on a creature-target candidate; the regression covers a Nissa-style loyalty action. This prevents a simulator crash, not a claim of optimal planeswalker play.
- For supported colored-permanent X-loyalty sweeps, Master AI tests board-changing X thresholds on copied game states and accounts for both players' lost permanents and the paid loyalty. It forces the sweep only when the evaluated gain clears a bounded threshold; other X-loyalty families and opponent-response planning remain open.
- Single-clause "any target" actions announce one player or permanent. For fixed damage, AI takes lethal player damage first; otherwise it chooses a killable creature over nonlethal creature damage when a player is legal. Supported sacrifice-damage triggers now use a separate AI target policy with the same lethal-first intent; a killable opposing creature or planeswalker can beat nonlethal player damage. These are local tactical rules, not general damage-planning search.
- Planeswalker loyalty abilities, including X-cost loyalty abilities
- Oracle `−` and ASCII `-` loyalty costs are normalized before activation. Supported X-cost mass exile checks each battlefield permanent's color and mana value on both sides; colored zero-mana tokens are included and colorless permanents are excluded. Supported noncreature-land animation adds printed counters and vigilance/haste. Canonical Ugin and Nissa fixtures cover these paths, but broader loyalty-effect and AI ability-selection fidelity remain open.
- Explicit `{C}` mana handling separate from generic mana
- Ownership-aware zone movement for stolen permanents
- Support for common Oracle patterns such as reanimation, graveyard recursion, tutor effects, and battlefield-tutor resolution
- Supported topdeck creature/permanent battlefield effects inspect and choose cards at resolution: legal cast hints reveal only counts, human choices can select up to the limit after a response window and snapshot restore, and live/simulator AI uses contextual ranking. Direct effect calls without a match chooser retain deterministic fallback. Random-order bottom clauses consume the persisted match RNG; supported "any order" clauses offer a second ordered human choice.
- Resolution-time library-search candidates and validated choices for human and AI controllers. AI hand searches rank mana fixing and near-term card value; graveyard searches instead rank recursion value and avoid exiling premium targets under supported graveyard replacement. Direct low-level effect calls retain deterministic fallback selection.
- Unrestricted one-card and creature-limited library searches can put selected cards into the graveyard, including supported "from anywhere" exile replacement. A human must select an available card for a mandatory unrestricted search; "up to" searches may select none. AI can decline an optional graveyard search when every candidate would be exiled. Entomb has an HTTP choice regression and Buried Alive has a snapshot-choice regression.
- Canonical Ramp tutor handling for Cultivate and Migration Path, including basic-land counts, shuffle, tapped battlefield placement, and Cultivate's first-to-battlefield/second-to-hand split
- Fixed, variable, and alternate cycling, including draw replacement, discard/cycle triggers, optional trigger choices, and basic-landcycling searches
- Broader support for artifact, enchantment, permanent, and combined artifact-or-enchantment trigger wording
- Generic named self-counter triggers for common cast/combat/ETB payoff patterns
- Resolution-time counted creature-type effects for tribal ETB payoffs
- Structured top-card hand/exile/bottom choices with temporary play permissions
- Look-at-top creature reveals with printed mana-value or power limits, optional human selection at resolution, ranked AI selection, and random-order bottom placement where Oracle text requires it
- Shared cast-choice plumbing for modes, faces, X values, and targets; library-search selection occurs at resolution
- Generic conditional target legality for common type exclusions and mana-value ceilings, including nonartifact/nonland/noncreature, creature-or-planeswalker, controlled-basic-land, and controller-graveyard restrictions
- Simple single-target player-or-permanent Oracle alternatives expose both candidate types and use one combined human target selector; damage to a planeswalker reduces loyalty, with prevention and printed clause order respected. Multi-target and more complex alternatives remain unsupported.
- Conditional counterspell payment and noncreature stack-target legality, with explicit API payment choices and deterministic automated fallback
- Stack targeting distinguishes spells from activated and triggered abilities. Counterspell cannot target a Sheoldred draw trigger or move its battlefield source to the graveyard; canonical Stifle wording can counter supported activated or triggered abilities. Negate resolves as a counterspell and excludes creature spells at selection and resolution. Broader copy/stack interactions remain uncertified.
- Drown in the Loch's selected counter mode limits stack targets by the target spell's mana value and its controller's current graveyard count, including announced X; the target is rechecked at resolution.
- Canonical Memory Deluge-style text now looks at cards equal to mana spent, puts two chosen cards into hand without causing draw triggers, and bottoms the rest in random order. Both humans and AI choose at resolution; AI uses library-choice scoring. Basic printed Flashback costs can be paid from the graveyard, and those spells exile on resolution or when countered. A seeded Dimir Control vs Ramp replay completed both games without timeout and exercised normal and Flashback selections. Unusual cost changes and broader Flashback interactions still need coverage.
- Oracle reminder text is excluded from executable effects on its source, so quoted token abilities are not mistakenly granted to the creator card. When that same printed text defines a named artifact token, the engine can create it with its own printed ability: Food and Blood tokens can be activated, paid for, sacrificed, and cease after leaving play. Witch's Oven uses the sacrificed creature's effective toughness for its one-or-two Food replacement. This does not yet cover named tokens without a supplied definition, deliberate sacrifice selection, or Cauldron Familiar's graveyard Food ability.
- Reflection of Kiki-Jiki-style activated text now creates a token copy of a legal other nonlegendary creature you control, copies its base characteristics without counters, adds the printed haste exception, and sacrifices the token at the next end step regardless of whose turn it is. This supports the checked-in Fable back face, not arbitrary copy-layer interactions; Fable's Goblin token attack ability is covered separately below.
- Fable's chapter-I Goblin token retains its quoted attack trigger and creates Treasure when it attacks. An offline [Scryfall-backed token seed](backend/card_data/builtin_token_seed.json) provides exact Oracle text and token types for Food, Blood and Treasure. Supported nonland tap mana abilities can be activated manually by a human or consumed during automatic cost payment; Treasure offers five colored choices and is sacrificed as a cost, while summoning-sick creatures cannot tap. Printed fixed same-color output (Sol Ring/Llanowar Tribe) and fixed amounts of any one color (Gilded Lotus) retain leftover mana. Legal-move affordability and automatic payment share an exact allocation search over supported fixed-output sources, including mixed land/artifact pools; each physical source is consumed once. Supported two-part hybrid symbols such as `{W/U}`, `{2/W}` and `{C/W}` enumerate legal mana payments, and mana value uses the largest hybrid component. A human may select every printed hybrid branch in the cast controls for legal hand, graveyard, exile or top-library casts, or leave all on Auto; AI and older clients use the first payable branch. Supported Phyrexian symbols also offer colored-mana or two-life payment, including hybrid Phyrexian choices; the cast and activated-ability controls expose the life branch. Supported self-activated single-keyword grants (including Pestilent Souleater gaining infect) persist through snapshots and expire at cleanup. Human branch choice for cycling, interactions among loyalty-entry replacement effects, broader snow-spend-dependent effects and dynamically changing snow-source types, multiple abilities on one source, variable or mixed-color output and complex mana-trigger ordering remain open.
- Activated abilities printed with "Activate only as a sorcery" are offered only during their controller's empty-stack main phase, and direct out-of-window actions are rejected before costs are paid. Other activation timing clauses still need coverage.
- A compleated planeswalker cast with life for a Phyrexian mana symbol enters with two fewer loyalty counters per symbol; this payment choice persists through stack snapshots. Mana payment leaves its printed starting loyalty unchanged, and leaving play restores printed loyalty for a later cast. Tamiyo, Compleated Sage covers the supported entry case; interactions with other loyalty-entry replacement effects are not yet certified.
- Supported `{S}` costs require mana from a snow source, following [Comprehensive Rules 107.4h](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). The pool tracks each color's snow-produced subset across manual taps, automatic payment and saved matches; colored and generic spending use ordinary mana first when available. The battlefield displays the snow subset as `(nS)` beside each pooled color. For supported fixed-output sources, the engine records how much snow-produced mana paid a spell, including colored and generic costs; copied spells count zero. Search for Glory uses that record to gain life after its snow-permanent/legendary/Saga library search, including when a human search choice pauses and resumes resolution. Icehide Golem, Snow-Covered Forest, Boreal Druid and Search for Glory have focused fixtures. Dynamic snow supertypes, arbitrary mana-source abilities and other snow-spend-dependent Oracle wordings still need coverage.
- Offline built-in play uses a checked-in 95-card Scryfall-backed Oracle seed instead of handwritten approximations. It includes the 11 built-in decks, additional cards, front-face data and double-faced/Adventure face metadata. A catalog test checks that each color has land sources scaled to its spell package. App-managed built-in and expansion templates refresh in place, preserving saved deck IDs and leaving user decks alone. These format-agnostic examples use original dual lands with no entry condition rather than approximating shock-land life-payment choices. Custom cards outside the seed still require cache sync; canonical text alone does not imply full mechanics support.
- Replacement candidates are queryable through `/matches/{match_id}/replacement-options`, and explicit source IDs can be carried through structured cast choices; deterministic timestamp selection remains the AI/replay default
- Replacement-option responses identify the deterministic policy as `latest_effect_timestamp` and suppress choices that a supported prevention override makes impossible
- Generic noncombat-damage replacement to -1/-1 counters, power-based death triggers, self-cast X triggers, and X-counter entry handling
- Realmwalker-style chosen creature-type persistence and legal casting of the matching creature from the top of the library
- Modal target generation selects the mode before materializing targets, and `Choose two` modes resolve through ordered structured effect sequences
- AI tutor selection happens at resolution, not by peeking at library candidates during cast; its current ranking is heuristic rather than deep tactical planning
- AI mechanic choices preserve lands and high-value creatures against Annihilator when expendable permanents exist, and choose cleanup discards from the whole hand instead of dropping the first cards by library order
- Opening-hand mulligan checks count only mandatory colored pips for supported two-part hybrid costs, so a blue source does not falsely appear unable to cast a `{W/U}` spell. Land-selection demand distributes optional hybrid-color interest rather than treating the first half as required. Phyrexian mana colors are optional in this heuristic because life can pay the printed cost; it does not yet budget life across an opening hand.
- Graveyard spell targets are legal AI actions for recursion effects such as Torrential Gearhulk-style abilities
- Legacy combat keywords such as `shadow`, `fear`, `intimidate`, and landwalk in blocking logic
- Manual and autoplay-driven best-of-three matches; human seats can inspect current mainboard/sideboard counts and submit one sideboard swap between games. AI seats with supplied sideboards make up to four conservative, color-source-checked swaps between games using opposing types observed in public zones or on the stack across the match; that type-only memory survives restart but never reads a hidden hand. AI-vs-AI testing can also use its known matchup archetype. This is a narrow heuristic, not optimized tournament sideboarding.

### Card Data
- Local card cache synced from live card data
- Oracle text, mana cost, type line, colors, rulings, legalities, and image metadata
- Double-faced, split, modal, adventure, and token-aware card handling
- Double-faced type lines use the front face until a legal transform selects the back face, avoiding premature creature/land characteristics from combined metadata
- Both battlefield transform paths normalize face power, toughness, loyalty and keywords through the shared face adapter; AI threat checks use effective power rather than raw printed strings
- Generic upkeep top-card transform handling for double-faced cards
- Core day/night state transitions from per-turn spell counts, including daybound/nightbound battlefield transformations
- Day/night transition triggers use the normal stack and APNAP ordering path
- Reusable Aura and Equipment attachment legality, target-choice exposure, and state-based cleanup for invalid Auras
- Generic temporary control-change effects with ownership-safe battlefield movement, cleanup restoration, and snapshot persistence
- Shared battlefield-leave events for destruction, exile, sacrifice, lethal combat, and state-based actions, including common leave-trigger resolution
- Token-aware death replacements that distinguish nontoken clauses from token permanents
- Non-battlefield tokens cease to exist at the next state-based check without suppressing dies triggers already generated. Token identity survives type changes and snapshots; supported graveyard returns, recasts, dredge, escape costs, hand discard, Ninjutsu and hand-to-battlefield effects reject departed tokens before that check. Other same-resolution library/exile transfers remain unverified.
- Canonical Rest in Peace graveyard replacement and ETB exile sweep, with HTTP action and SQLite-restore regressions for damage-spell resolution, suppressed dies triggers, and existing graveyards; interacting replacement choices remain uncertified
- Owner-scoped opponent-card graveyard replacement for Leyline of the Void wording: opposing cards are exiled from discard, stack and battlefield paths, but tokens and the controller's own cards are not; a resolved opponent spell is HTTP/restore-tested, while Leyline's opening-hand permission remains unsupported
- Dynamic characteristic-defining power/toughness for graveyard card-type counts
- Corpus audit distinguishes structured cast effects, structured event/replacement paths, and static/no-op cards; the shipped 81-card corpus currently has zero parser-fallback or missing-Oracle classifications
- Fuzzy matching for deck import correction
- Cached fallback metadata when remote lookups fail
- Token creation uses cached art or an immediate local fallback, never a network request in the rules path; explicit token-art sync stores local art for later games
- Diagnostic replay scripts hydrate cards from the local cache before simulation; unknown cards retain unknown characteristics instead of being silently treated as generic 2/2s

### AI
- Archetype-aware AI with difficulty levels: `casual`, `strong`, `master`, `master_plus`
- Hand-profile-aware mulligan decisions, curve evaluation, interaction timing, threat assessment, attack selection, and combat math
- X-spell value selection that trades off board pressure, archetype pressure, and mana efficiency
- Modal, split, and transform-face selection based on board state and matchup pressure
- Board-role-aware planning for stabilize, convert, race, control, and related board states
- Matchup-aware scoring for control, ramp, tempo, tokens, midrange, aggro, and attrition lines
- Exact shared-draw casts are screened against both library sizes and current hand disparity before forced-play heuristics. Master AI holds Vision Skeins when it would mostly refill the opponent, avoids self-decking, and keeps an opponent-decking line; this is bounded tactical screening, not a general shared-resource planner.
- Replay-prior tuning and training exports for deeper decision analysis
- Adaptive bounded two-ply Master planning on developed boards, including spell sequencing and resource-preserving proactive actions
- Master-level bounded blocker-assignment search on small combat boards, resolving cloned combat states to compare lethal prevention, trades, and post-combat board value
- Combat AI evaluates resolved effective stats and blocker ownership, including counters, continuous buffs, temporary changes, and characteristic-defined values
- On boards too large for bounded block search, AI fallback checks the engine's direct-block legality before assigning a blocker. It counts all attacking members stopped by a legal band block; this does not make AI form bands strategically.
- AI block search and fallback use the same engine minimum-blocker requirement, including creatures that require three or more blockers; choosing no block remains legal. This is not a claim that all combat decisions are optimal.
- Complexity-bounded Master deep search: dense token boards fall back to deterministic heuristic/combat evaluation so long simulations remain responsive
- Combat search preserves blockers when a non-lethal line would only chump without removing an attacker, while retaining lethal-prevention and profitable-trade lines
- Engine-tagged control spell scoring now uses board-role context without crashing the head-to-head simulator

### Simulation and Diagnostics
- AI vs AI autoplay
- Batch simulation with progress tracking
- Replay inspection and deterministic regression checks
- Seeded best-of-3/5/7/9 replay validation with per-game hashes, legal-action traces, and timeout classification
- Timeout classification distinguishes isolated legal conditional-counter payment failures from repeated recent cost failures; low tick caps can still end legitimate long games
- Match logs, anomaly output, and training trace export
- Stable AI decision-reason labels and legal-action summaries in verbose traces, analytics, and training exports
- Card-play analytics flag pass-with-unused-mana and main-phase land-not-first decisions with the surrounding hand/board context
- Card-play analytics excludes tapped blockers from attack-quality warnings and preserves hand/board context for missed-land investigations
- Tactical analytics record effective keywords, attacker/blocker assignments, evasion-aware bad attacks, lethal misses, block trades, and resource-preservation decisions
- First-divergence drilldown with compact trace context for both sides
- Per-game batch results and matchup summaries
- Diagnostic scripts for head-to-head runs, replay regression, anomaly clustering, and training-data extraction
- Corpus audit script for ranking parser fallbacks and missing Oracle metadata across built-in and expansion decks
- SQLite cache resolution is stable across launch directories; API, sync jobs, and diagnostics use `backend/mtg_lab.db`

### UI
- Desktop-first battlefield layout with readable stack, priority, mana, and hand presentation
- Explicit interrupt-window state in the controls panel
- Hover inspection and card zoom for readable long-session testing
- Density-aware battlefield scaling for crowded boards
- Match simulator panel with progress and first-divergence reporting
- Testing Simulator can browse persisted diagnostic summaries without loading raw anomaly logs; selected runs show bounded samples and cluster metadata

## Architecture

Gameplay logic lives in application code. SQL is for storage only.

### Backend Layers
- `backend/card_data` - card sync/cache, image cache hydration, and fuzzy lookup
- `backend/rules_engine` - turn structure, priority, stack, combat, timing, state-based checks, and rules inference
- `backend/effects` - modular effect handlers and resolver registry
- `backend/game_state` - canonical state model and serialization
- `backend/ai` - tactical AI, archetype detection, matchup policies, and endgame behavior
- `backend/decks` - deck parser/import, built-ins, expansion decks, and sideboarding support
- `backend/analytics` - batch simulation, replay summaries, diagnostics, and anomaly analysis
- `backend/persistence` - storage layer only
- `frontend/src` - match UI, deck UI, controls, logs, and simulator views

## Setup

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9999 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

The Vite development server proxies `/api` and `/card-images` to the backend on port `9999`. Production builds also default to same-origin `/api`, so a static deployment must proxy both `/api` (stripping that prefix) and `/card-images` to the backend. For a separate backend origin, copy `frontend/.env.example` to `.env.production` and set `VITE_API_BASE_URL` before building, for example `http://192.168.1.50:9999` on an HTTP-only LAN. Use an HTTPS backend origin when serving the frontend over HTTPS; the app no longer guesses an HTTP backend on port `9999`.

### Open the App
- Frontend: `http://<server-ip>:5173`
- Backend: `http://<server-ip>:9999`

## Testing

### Backend
```bash
cd backend
pytest -q
```

### Frontend
```bash
cd frontend
npm run build
```

The dependency-free Chromium action regression is available through `npm run test:browser` after starting its isolated fixture API and browser. Setup and coverage limits: [human action browser tests](docs/testing/human-actions-browser.md).

To smoke the built frontend through an isolated HTTPS proxy and a separately configured HTTPS backend origin (requires `openssl`, Chromium, and the backend venv):

```bash
npm --prefix frontend run build
D=$(mktemp -d /tmp/mtg-routing-XXXXXX)
git ls-files backend | tar -cf - -T - | tar -xf - -C "$D"
python3 frontend/tests/production_proxy_smoke.py --backend-dir "$D/backend" --dist-dir frontend/dist --python "$PWD/backend/.venv/bin/python" --browser --cross-origin
```

The harness writes only to the disposable backend copy, uses a temporary self-signed certificate, and restores the original frontend build after its cross-origin variant. It checks the built page in Chromium plus HTTPS health, import, match start/action and card media in both modes. It is not a trusted-certificate LAN deployment or an authorization test.

The production frontend shows a backend health indicator and polls `GET /health`. A red/offline indicator means the page loaded but cannot reach the API; use the Retry control after correcting `VITE_API_BASE_URL` or the reverse-proxy route.

The rules engine exposes explicit choice contracts for supported tutor and top-library effects. Expressive Iteration-style effects inspect the current library at resolution; a human orders the inspected cards as hand, exile, then library bottom through a pending choice, while AI uses a deterministic fallback. Supported library searches likewise expose eligible cards only when the search resolves. Invalid or incomplete choices are rejected without changing state. Broader search wordings and strategic AI tutor selection remain to be verified.

Common tempo bounce is also handled through the rules engine: nonland-permanent and creature returns use legal target hints, preserve ownership for stolen cards, emit battlefield-leave events, and return the permanent to its owner's hand. Master AI additionally evaluates small-board attack subsets through blocker search and combat resolution before committing attackers.

### Expanded keyword engine

Battlefield controls follow the acting human seat instead of assuming player 1. Legal-move responses include public card views for playable non-hand cards; exile/library/graveyard casting preserves its source flags. Ordinary permanent abilities offer target/mode controls and advanced JSON choices. Ability targets are checked before paying activation costs, and adjacent mana symbols are retained. Variable activated mana costs are explicitly unsupported and are not offered as legal actions.

Cleanup offers deliberate discard selection to human seats, persists that choice through snapshots, and emits the same discard events used by spells. Damage and turn-duration effects expire after discarding; resulting state-based actions/triggers open priority and force another cleanup. Normal cleanup cannot cast spells or activate abilities. The controls panel exposes pending cleanup, draw-replacement and mandatory sacrifice choices with the correct acting seat.

Live starts, sideboarding and diagnostics share face-aware cached-card hydration. Public views retain both faces and the selected face, expose effective battlefield stats separately from base stats, and include counters, damage and effective keywords. Hover previews display this information. The generic token fallback ships as a tracked asset and is installed into an empty image cache automatically; artwork retrieval still prefers real token images.

Dedicated core handlers now cover Infect/Wither damage, poison loss, Toxic combat damage, Ninjutsu, Annihilator sacrifice choices, Escape graveyard costs and Prototype alternative characteristics. Dredge is optional per draw; draw-step and spell draws share the replacement-aware handler. Pending draw/sacrifice choices and resolving spells survive snapshots, including multi-draw effect continuations. Activated abilities and cycling do not count as casting spells.

These are engine/API foundations, not all-card certification. Competitive-opponent human-game/browser acceptance, complex action choices, interacting replacement choices, Prototype copy/layer edge cases, and complete combat assignment semantics still need integration work. Morph/Manifest, Suspend, Mutate, Discover, Craft, "bands with other," and complete Battle rules remain unfinished. See `docs/rules/expanded-keywords.md` for contracts and coverage limits.

Master attack search is intentionally bounded to late-game positions with no more than three candidate attackers and two untapped blockers. Larger boards use the normal tactical heuristic so long-running simulator batches remain responsive.

Master two-ply and rollout search is also bounded by total battlefield permanents and legal-action count. This keeps token-heavy matchups responsive; it is a performance guard, not a claim of exhaustive search or pro-level optimal play on large boards.

Common Sagas now receive lore counters during precombat main, put matching chapter abilities on the stack, and are sacrificed by state-based actions after the final chapter resolves.

Vehicles expose explicit crew actions. The engine validates creature power and pays tap costs at activation, then puts a counterable crew ability on the stack. On resolution, the same battlefield Vehicle becomes a creature until cleanup; the AI selects a legal crew group but skips redundant repeat activations. Crewing an already-creature Vehicle remains legal for humans. Vehicle-specific "becomes crewed" triggers and unusual copy/layer interactions still need broader coverage. See [crew timing checks](docs/testing/crew-stack-timing.md).

Targeted actions are validated against the current candidate set before entering the stack. Stale, cross-zone, or restricted-card IDs are rejected, while broad “any target” effects continue through protection and hexproof checks.

Farewell-style mass exile of creatures is handled separately from destruction: ownership is preserved, battlefield-leave triggers are emitted, and creatures move to their owners' exile zones.

### Diagnostics
```bash
cd backend
python3 scripts/debug_head_to_head.py --deck-a Tempo --deck-b "Blue Control" --matches 1
python3 scripts/debug_head_to_head.py --deck-a Tempo --deck-b "Dimir Control" --matches 1 --seed 849124 --out-dir diagnostics
python3 scripts/card_play_analytics.py --games-jsonl diagnostics/RUN_DIR/games.jsonl --out diagnostics/card-play.json
python3 scripts/regression_matrix_replay.py --matches-per-pair 1 --max-decks 2
python3 scripts/ci_regression_gate.py --matches-per-pair 1 --max-decks 2
```
The head-to-head runner records full hand/board decisions, effective keywords and marked damage. Its trace uses the shared five-metric decision-quality evidence path. `--seed` records per-game seeds for reruns; generated stack IDs can still differ in raw logs, so compare normalized actions rather than raw bytes. Replace `RUN_DIR` with the run directory printed by the preceding head-to-head command. Metrics may remain unavailable when a complex combat line cannot be validated.

The `debug_head_to_head.py` smoke path now completes cleanly for Tempo vs Blue Control in local verification.

### Canonical Card Knowledge

The knowledge database can ingest every unique Oracle card from Scryfall's official bulk dataset, including face data, keywords, legalities, image URLs and provenance. This stores metadata, not new rules implementations or trained AI behavior. Same-name token variants retain separate Oracle identities; their exact printed names remain in the canonical payload.

```bash
cd backend
./.venv/bin/python -m scripts.sync_all_card_knowledge
./.venv/bin/python -m scripts.sync_corpus_cards --out knowledge/data/corpus-sync-summary.json
./.venv/bin/python -m scripts.knowledge_gap_report --require-rulings
./.venv/bin/python -m scripts.card_mechanics_inventory --out knowledge/data/mechanics-inventory.json
```

The bulk command writes `CardKnowledge` in the application's SQLite database without replacing the gameplay/image cache. Repeated imports reuse the downloaded dataset and unchanged rows. Bulk download files and summaries live in ignored `backend/knowledge/data/`; rebuild them after a fresh checkout. Back up `backend/mtg_lab.db` before refreshing local data. Both sync commands accept `--database /path/to/isolated.db` for isolated ingestion.

The 95-card offline built-in seed is tracked at `backend/card_data/builtin_oracle_seed.json`, with Scryfall IDs for provenance. After syncing the gameplay card cache, regenerate it with `PYTHONPATH=. ./.venv/bin/python scripts/export_builtin_oracle_seed.py` from `backend/`. The exporter fails if a built-in card lacks verified cached metadata; it does not invent an Oracle clause. Starting loyalty for four built-in planeswalkers was checked against Scryfall's exact-name API because the current card-cache schema omits that field. Face art is intentionally not bundled; sync images separately or use the tracked generic fallback.
The head-to-head diagnostic uses the same card hydrator as live matches. In a local seed-100 Tempo/Dimir comparison, offline and cache-backed games had identical normalized actions and final state after that duplicate-hydration path was removed; this is a one-seed parity check, not a broad rules certificate.

Bulk data does not include downloaded rulings. The corpus command verifies them separately, treating a successful empty list as valid and marking failed fetches as errors. Use repeatable `--name "Card Name"` or `--query "f:standard" --limit 200` to verify additional cards; `--force` refreshes previously verified entries. Knowledge coverage does not certify gameplay support, and the current AI does not yet consume this table.

The September 27 local import contains 38,690 unique Oracle records and 6,433 faces. Rulings verification passes for the shipped/saved corpus (88 requested names, 87 verified canonical records). The mechanics inventory records metadata and explicit gap candidates, including Morph, Suspend, Infect, Ninjutsu, Mutate, Discover and Escape; it does not infer complete support from a keyword match. Counts and provenance are recorded in `docs/plans/baselines/2026-09-27-card-knowledge.json` and `2026-09-27-mechanics-inventory.json`.

## Deck Import

Supported text format:
```text
4 Lightning Bolt
3 Counterspell
20 Island

Sideboard
2 Negate
2 Dispel
```

Import sources:
- Paste deck text
- Upload a `.txt` deck file
- Choose built-in decks
- Choose expansion decks

The parser accepts common `Mainboard`, `Maindeck`, `Sideboard`, and `SB:` section headers, set annotations such as `[M11]`, `4x` multiplier notation, and common comment lines.
Known cached art-series, token and emblem objects are reported as non-playable on import and rejected before a match starts. Unknown cards still require metadata sync before play.
The import panel shows a mana curve computed from cached Oracle mana costs, with lands and unresolved cards counted separately. For modal/transform cards the curve uses the front face; X is zero outside the stack. Spell-color counts use cached card colors and exclude lands, so they are not a mana-source analysis. Archetype analysis receives resolved metadata, but remains a heuristic rather than a verified deck strategy.
The card-data report checks both mainboard and sideboard and flags known unsupported Oracle mechanics: "bands with other", Morph, Manifest, Suspend, Mutate, Craft, and Discover. It also inspects cached face text. It distinguishes `known_unsupported` from `not_certified`; no card is currently presented as rules-certified. Live cards retain cached color metadata for color-based rules; selected faces use their own cached colors, and uncached hybrid costs are parsed as a fallback. Combat lethal deaths use the shared state-based-action pass, which rechecks the battlefield after a permanent leaves and evaluates supported simultaneous death replacements before moving their sources. Supported "from anywhere" graveyard replacement text, including Rest in Peace, redirects common death, discard, cost, mill, cycling and spell-resolution moves to exile; its entry trigger exiles existing graveyards. Metadata completeness is not rules certification, and other unsupported or approximate effects may still be unflagged.

## Card Data and Images

The app syncs and caches card data locally.
- Card metadata is stored for repeatable testing
- Missing art falls back to local placeholder handling
- Cached double-faced cards reuse face-level art when the root image is missing
- Exact cached card names take precedence over face aliases; non-playable art-series records cannot masquerade as a land or other split-face alias
- Token art resolves from the local index when available, with a generic token fallback before blank placeholders; game actions never wait on Scryfall
- Fallback card lookups normalize punctuation, spacing, and common transform-face import names

To prefetch a token image explicitly, run from `backend`:

```bash
python -m card_data.token_images "White Soldier" 1 1
```

This network operation writes the image and `token-index.json` into the disposable image cache. Without prefetching, newly created tokens use the shipped generic art until a later game loads a synced image. Back up the image cache if retaining token art across installations matters.

## API Overview

Base backend default: `http://0.0.0.0:9999`

`0.0.0.0` is a bind address; browsers use the host's real address. Operation is currently private, single-user and single-worker. Per-match locks coordinate this process only; they do not provide network authorization or multiworker consistency. Do not expose the dev service to the public internet.
Human-vs-human mode is a shared-device sandbox, not a private two-account game: both human hands remain available to the same unauthenticated client. Seat authentication and per-viewer redaction are required before claiming hidden-information privacy for separate human players.
The single-process API admits one batch simulation at a time across synchronous and background-job routes; additional requests receive `429 simulation_busy`. This bounds concurrent batch execution, not on-disk job retention, cancellation, multiworker coordination or total CPU used by the admitted job. Interrupted jobs are marked failed after backend restart.
The process keeps at most 20 completed/failed simulator jobs in memory; older results remain queryable from SQLite. Database retention and automatic cleanup are not yet configured.

Start/batch payloads accept `{quantity, card_name}` entries, resolving gameplay data from the card cache/source rather than arbitrary client Oracle text. Mainboards require 60-250 cards; `sandbox: true` permits 1-250. The upper bound is an application resource limit, not a Magic rule. Sideboards are capped at 15. See [input contracts](docs/api/input-contracts.md) for actions, errors and remaining guarantees.

Key endpoints:
- `GET /health`
- `GET /cards`
- `POST /cards/sync`
- `POST /cards/sync-bulk`
- `GET /decks`
- `POST /decks/import`
- `POST /decks/import-file`
- `GET /decks/builtin`
- `GET /decks/expansion-top`
- `POST /decks/analyze`
- `POST /matches/start`
- `GET /matches`
- `GET /matches/{match_id}`
- `GET /matches/{match_id}/legal-moves`
- `POST /matches/{match_id}/action`
- `POST /matches/{match_id}/autoplay`
- `GET /matches/{match_id}/replay`
- `POST /matches/{match_id}/sideboard`
- `POST /matches/{match_id}/next-game`
- `POST /simulate/batch`
- `POST /simulate/batch/start`
- `GET /simulate/batch/{job_id}`
- `POST /ai/diagnostics`
- `GET /diagnostics/runs`
- `GET /diagnostics/runs/{run_name}`
- `GET /diagnostics/compare`
- `GET /diagnostics/compare/replay`
- `GET /diagnostics/runs/{run_name}/games/{game_index}`
- `GET /ai/priors`
- `POST /ai/priors/rebuild`
- `GET /analytics/history`

## Current Status

The application currently supports:
- Rules-aware 2-player testing with turn structure, priority, stack, combat, cleanup, and turn advancement
- Shared cost-modifier handling for supported static spell taxes, including opponent-scoped taxes
- Human vs AI, AI vs human, and AI vs AI matches
- Manual phase progression and autoplay-driven simulation
- Built-in deck imports, expansion deck imports, file/text deck import, and deck saving
- Local card caching with image fallback handling
- Replay logs, batch simulations, matchup stats, anomaly diagnostics, turn-level AI trace summaries, and training trace export
- Compact first-divergence drilldown for replay drift analysis
- Bounded persisted-game replay comparison with categorized first-divergence context
- Paginated persisted game-log playback with bounded response pages
- Role-aware log priors derived from replay traces and training exports
- AI seat control with archetype detection, hand-profile mulligan logic, curve evaluation, interaction heuristics, attack heuristics, and keyword-aware battlefield evaluation
- Matchup profiles for control, ramp, tempo, token, and removal-heavy shells
- Responsive desktop UI with readable stack, priority, mana, and hover inspection

Current focus:
- expanding targeted trigger choices beyond bounded ETB/self-cast clauses, non-damage multi-target rechecks and broader face mechanics
- competitive-opponent and more varied full-game browser acceptance, extended match-creation recovery and broader successful-response runtime validation
- broader AI sideboarding plans, competitive-opponent BO3 browser coverage and full response-contract acceptance
- expanding Oracle coverage for older and unusual cards
- improving replacement, prevention, and layer fidelity in edge cases
- deepening tactical AI for complex board states and matchup-specific heuristics
- broadening deterministic replay coverage across more representative deck pairings
- keeping the UI dense and readable during long sessions
- validating LAN and long-session UX, then adding richer state-by-state replay reconstruction

GitHub Actions runs a clean-checkout backend test suite, frontend `npm ci`/build/hooks lint/unit checks, and a separate loopback Chromium action/recovery flow on pushes and pull requests. The browser job includes backend-process restart and scripted complete BO3 flows; these are not competitive-opponent, long-session or deployment tests. Local instructions are in [the human-action test guide](docs/testing/human-actions-browser.md).

Run frontend unit checks with `cd frontend && npm test` (`npm run test:unit` is the equivalent explicit script).

## Development Notes

- Gameplay rules live in application code, not in SQL.
- `README.md` describes the current product state.
- `CHANGELOG.md` records milestone-level history.
- `plan.md` tracks the remaining finish work.

## Known Limitations and Next Upgrades

- Supported spell and ability copies are independent stack objects with response windows. Copies preserve announced modes, X and targets, survive the original being countered, and can themselves be countered without moving the original card. A resolving permanent-spell copy enters as a token without being "created"; Lithoform-style "copy target permanent spell you control" filters the stack by controller and permanent type. Search for Glory and Memory Deluge copies count zero mana spent to cast. Twincast- and Lithoform-style single-target copies can keep or legally change their target before priority resumes; AI handles the same choice. Supported divided-damage spell copies let the controller decide each target separately without changing target count or allocated damage, including across snapshots. Explicit per-mode modal targets with one target and one effect per mode can also be changed independently; the copied effect payload changes while the original spell stays intact. AI redirects supported copied removal/damage modes away from its own side. Activated-ability target legality is rechecked at resolution, and supported targeted triggered copies use their trigger clause. Other multi-target, divided-damage ability copies, non-damage distribution, shared-target modal forms, Battle/token entry, copy-layer/last-known-information and permanent-entry replacement interactions remain uncertified.
- The supported "pay X life" additional-cost wording requires an announced affordable X, emits a life-payment event, and can resolve the matching all-creatures `-X/-X` effect through cleanup. The [Toxic Deluge boundary audit](docs/audits/2026-09-29-variable-life-cost-and-name-fallback.md) has engine, snapshot, HTTP and AI-choice regressions. This is not blanket support for variable costs, all continuous-effect layers, or seasoned-player AI; unsupported Oracle clauses still need explicit corpus review. Card-name effect guesses no longer override present Oracle text.
- Expansion-labeled decks currently reuse supported archetype templates; they are not verified tournament decklists from their named sets. Format/era legality and historically sourced expansion lists remain future work.
- Conditional land entry now has a shared choice path for the supported pay-2-life wording, including effect-driven entry and snapshot continuation. Human play and effect choices passed browser/API scenarios; a seeded AI replay paid 2 life deterministically. Other entry replacements, competing replacements, arbitrary Oracle wording and broader replay/matchup acceptance remain open; see the [entry-boundary audit](docs/audits/2026-09-28-battlefield-entry-choice.md). Built-in lists still use unconditional duals rather than assuming this narrow fix certifies all conditional lands.
- The supported look-at-top creature-reveal pattern is tested with Recruitment Officer and Militia Bugler text. Creature/permanent topdeck battlefield, Expressive Iteration-style placement, and supported library-search choices now occur at resolution, with browser-tested human controls. Entomb/Buried Alive graveyard destinations have focused engine/HTTP checks. Storm the Festival's random-order bottom clause and Collected Company's two-step human "any order" choice are snapshot-tested; other search wordings and full Oracle clause fidelity need further coverage. A successful parser match is not proof of correct resolution.
- Conventional permanent spells compile separately from their later abilities: resolving them puts them onto the battlefield rather than executing activated or triggered Oracle text. Aura attachment and supported entry choices remain intact; modern "enters" wording uses the entry-event matcher. Bounded single-target ETB, self-cast and sacrifice-damage triggers choose targets in the ability window, with an optional accept/decline decision at resolution where applicable. Other trigger families, modal/multi-target clauses and multiple ability clauses remain local-beta blockers. See [targeted trigger boundary](docs/testing/targeted-trigger-choices.md).
- Canonical modal spell faces have independent timing/cost/target moves, selected stack characteristics, snapshot restoration and correct spell/permanent resolution zones in the tested fixtures. Humans can select available faces; AI materialization and cast bias use the offered face. [Face-boundary tests and limits](docs/testing/modal-spell-faces.md) cover this narrow contract, not every face mechanic. Common modal land-face plays and Adventure resolution/exile permission paths are [tested separately](docs/testing/land-adventure-boundary.md). Divided-damage recipients and pay-2-life land entries have bounded legality coverage; non-damage multi-target spells, other conditional entry families, split-card restrictions and full face-specific restart/browser acceptance remain open. Older cache rows need force-sync to acquire canonical layout.
- Guarded match writes persist history/snapshots together and restore memory on storage faults. Match creation now commits a start-key receipt with its snapshot; ambiguous successful responses retry the same key, including after reload. Saved-match restore, overlap suppression and lost-response reconciliation have focused browser coverage. Extended disconnect/soak acceptance remains open. Legacy headerless callers have no stale-version guarantee.
- New interactive matches persist root/per-game seed provenance and previous-loser play/draw choice. Human sideboard inventory is visible only between games for human-controlled seats; a swap survives reload and changes the next game's deck in bounded HTTP/browser tests. AI seats use a bounded public-evidence sideboard heuristic when a sideboard was supplied; public card types are remembered across actions and SQLite restore even after a card leaves view. Next-game HTTP, full-AI autoplay and hidden-hand privacy have regressions. Scripted human-vs-AI and human-vs-human BO3s complete through the browser against a noncompetitive all-Island opponent; competitive-opponent and more varied full-series coverage, broader sideboard strategy, and legacy seed migration remain open. Existing saved matches without root seeds remain unseeded in later games.
- Human action browser fixtures cover focused paths including two-step Collected Company, ordered top-library and tutor choices, nested draw/dredge replacement, and both BO3 play/draw choices. Two additional paths play complete scripted human-vs-AI and human-vs-human series against an all-Island opponent. The crew scenario checks a responseable stack ability and the cast-trigger scenario checks target choice above a creature spell; variable activated mana costs remain explicitly unsupported.
- Incomplete type metadata for a nonbasic card is no longer guessed to be Land from mana text or a basic-land word in its name. Canonical cache hydration must supply that card's type line; the AI will not bypass missing legal moves by fabricating a land action.
- Replay timeout labels now inspect the timed-out game alone; a prior game's cost error cannot make a long control game look like a rules failure. Deliberately low tick caps can still truncate legitimate games, so simulator conclusions require the recorded cap, seed and termination status.
- Target declaration checks cover supported patterns, not complete multi-role/controller-qualified Oracle targeting. Player hexproof/shroud currently recognizes only unconditional "You have ..." battlefield clauses; conditional/temporary grants, player protection from a quality, and all Battles as "any target" remain open. Generic AI allocation is legal for tested clauses but not a complete tactical optimizer.
- First/double-strike priority windows and controller-chosen numeric damage division have focused engine, HTTP and browser tests, including Palace Guard, multiple blockers, shared-source trample, deathtouch, banding choice ownership and planeswalker damage. Ordinary attacking-band declaration and block propagation are supported with focused engine tests; "bands with other," simultaneous damage-replacement interactions and unusual keyword changes remain open. See the [combat assignment audit](docs/rules/combat-damage-assignment-audit.md).
- Private single-user/single-worker operation only: authentication, bounded job admission, cross-worker coordination and production HTTPS/proxy validation remain release gates.
- Long-tail Oracle coverage is still incomplete for fringe older cards and uncommon wordings.
- Some replacement and prevention interactions still rely on heuristic inference instead of a fully generic rules model.
- The [life-total-lock audit](docs/audits/2026-09-28-life-total-lock.md) covers a bounded Platinum Emperion-style interaction. Combat gains use the shared replacement handler. The [Font of Agonies pay-life trigger audit](docs/audits/2026-09-28-life-payment-triggers.md) records the repaired payment event and stack timing boundary; unusual payment wording and competing replacements remain open.
- The [lifelink event audit](docs/audits/2026-09-28-lifelink-events.md) covers per-source gain triggers, supported gain doublers, gain-to-draw conversion, human choice continuation and double-strike windows. Nested draw-replacement choices and general simultaneous replacement ordering remain uncertified.
- Layer ordering and timestamp resolution still need more fidelity in obscure overlapping effects.
- The AI still needs more long-run tuning for control, tempo, ramp, token, and combo-lite matchups.
- Master AI can now cast fixed-cost planeswalkers whose later loyalty text mentions X and choose profitable X values for the supported colored-permanent sweep. This is not a general X-loyalty planner or broad decision-quality certification.
- Larger deterministic replay matrices and longer validation runs would improve confidence in balance and edge-case coverage.
- Persisted replay inspection is paginated and bounded; state-by-state card highlighting and full long-session/LAN validation remain future work.
- The UI still has room for more polished long-session deck-testing ergonomics.
