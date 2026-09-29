# Changelog

- Battlefield re-entry now clears stale until-end-of-turn power/toughness modifiers from the returning card object. A real Giant Spider bounce-and-return snapshot regression covers the previous leakage after Toxic Deluge; 1,135 isolated backend tests, the standalone full Chromium harness and a three-game deterministic replay pass. A browser recovery check timed out once while the backend suite ran concurrently, then passed alone. Wider zone-change counter/characteristic resets remain open.

- Added announced variable additional-life costs, reusable all-creatures temporary `-X/-X`, human X range/cost disclosure and board-aware AI X choice. Present Oracle text now blocks unrelated card-name effect guesses. Toxic Deluge engine/snapshot/API/Chromium regressions replace three strict xfails; 1,134 isolated backend tests, frontend lint/build/unit and the full Chromium harness pass. A separate seeded BO3 replay finished without timeout or drift. Broader variable costs and continuous-layer fidelity remain open. See the [boundary audit](docs/audits/2026-09-29-variable-life-cost-and-name-fallback.md).

- Added a live FastAPI integration regression for real Withering Boon and Font of Agonies: legal moves expose only the creature spell as a stack target, and casting returns a 3-life payment with Font's trigger above the counterspell. Verification: 1,124 isolated backend tests pass. This closes the engine-to-HTTP evidence gap, not a claim of complete counterspell or pay-life Oracle coverage.

- Effect-driven multiple land entries now defer payment/ETB triggers until all pre-entry choices complete, rather than overwriting an earlier human trigger-order request. A two-Sacred-Foundry/two-Font-of-Agonies regression restores a snapshot between choices, orders all four triggers, and resolves the correct counters. Verification: 1,123 isolated backend tests and the full Chromium harness pass. Competing replacement effects remain open.

- Routed positive activated, additional and land-entry life payments through one amount-bearing event; supported pay-life counter triggers now stage above paid-for spells and abilities and survive snapshots. Repaired generic type-qualified counterspell target inference and validation, exposed by a real Withering Boon regression. The prior Font of Agonies strict xfail is now a passing test. Verification: 1,122 isolated backend tests, frontend lint/build/unit and the full Chromium harness pass. Broader Oracle wording and nested payment/replacement timing are still open.

- Historical audit: real Font of Agonies and Cruel Sadist text reproduced the missing payment trigger with one strict xfail among 1,115 passing tests. The [audit](docs/audits/2026-09-28-life-payment-triggers.md) records that pre-repair finding; the bounded repair above supersedes this status.

- Added real Nefarious Lich/Boon Reflection combat fixtures for gain-to-draw replacement order, multiple lifelink sources, human choice and snapshot continuation. A Vampire Nighthawk granted double strike verifies Archive applies separately in first and regular damage windows without duplicate damage. Verification: 1,115 isolated backend tests pass; the previously run frontend gates and full Chromium harness remain green. Nested draw-replacement choices and broader simultaneous ordering remain open.

- Combat lifelink gains now use the shared life-gain replacement handler instead of direct life mutation. Archive and Boon Reflection-style doublers apply to each source's event; human replacement choice can pause combat and resume after a snapshot before death state-based actions. The previous strict expected failure is removed. Verification: 1,113 isolated backend tests, frontend lint/build/unit and the full Chromium harness pass. Broader cross-event ordering remains open.

This file tracks milestone-level changes. The root README stays focused on the current product state.

## 2026-09-28

- Combat lifelink now stages a gain-life event per source rather than silently incrementing life. One source damaging multiple blockers produces one event; two sources produce two. Real Vampire Nighthawk and Ajani's Pridemate fixtures verify supported gain-life triggers. Replacement choices were completed in the subsequent entry above.
- Added a shared life-total-lock check for supported "can't change" wording across gain/loss effects, player damage, combat lifelink, land-entry payments and activated/additional costs. Paying exactly remaining life is now legal when no lock applies. Real Platinum Emperion, Cruel Sadist, Vampire Nighthawk and Glistener Elf fixtures cover the bounded contract; simultaneous lifelink replacements and payment triggers remain open.
- Added a shared pre-entry choice for lands with the canonical pay-2-life-or-enter-tapped wording. Land plays and hand/library/graveyard battlefield-entry effects use it; human choices pause and survive snapshots, while AI pays only when untapped mana enables a current cast. Focused tests cover forced tapped entry, invalid choices, simultaneous entries and life-zero timing. Browser/API choices and one seeded AI replay pass; this does not certify other replacement families or broad replay behavior.
- Audited battlefield-entry choices against the current Comprehensive Rules. Reproduced a conditional land entering untapped without its 2-life payment; inventoried the land-capable effect paths and set a shared pre-entry, choice, snapshot and replay acceptance gate. This is an audit, not a rules fix.
- Rebalanced remaining colored mana bases using three more Scryfall-verified unconditional duals: Blue/Dimir Control, Burn, Midrange and Tempo now have more sources for substantial secondary-color packages. A catalog guard scales minimum sources with colored spell copies rather than accepting any nonzero source. Two seeded Tempo/Dimir games finished 1-1 versus 2-0 before this pass, and two each of Midrange/Drain and Burn/Blue Control exercised the new sources without timeout. These traces show access, not optimal deck construction or win-rate evidence.
- Corrected four built-in mana bases: Ramp, Drain, Tokens and Tribal previously contained colored spells with no matching land source. Added five Scryfall-verified original dual lands to the offline seed and a catalog-wide color-source invariant. Saved app-managed built-in and expansion templates now refresh changed mainboards in place, preserving deck IDs and user decks. Seeded Ramp/Tokens games finished 1-1 after the change versus 0-2 before with Ramp in seat A; Drain/Tribal also exercised formerly unreachable spells. These are small diagnostics, not balance evidence. Original duals are intentional because conditional shock-land entry choices are not yet supported.
- Added bounded board-value planning for supported colored-permanent X-loyalty sweeps. AI evaluates only X thresholds that can remove opposing colored permanents, using copied rules states so loyalty payment and friendly losses count; it does not force a low-value sweep. Real Ugin/Gearhulk/Sheoldred/Meathook fixtures and two seeded Dimir/Ramp traces cover X=6 and X=4 lines. The two games finished without timeout or parser-fallback lines; no win-rate or broad tactical claim follows.
- Enforced exactly one announced player or permanent for supported single-clause "any target" actions. AI materialization no longer submits both, and fixed-damage AI avoids nonlethal creature damage when a player target is available while still taking lethal creature hits. Lightning Bolt fixtures cover both choices and rejection; the same two-seed Dimir/Ramp replay sends Ugin's 3 damage to a player instead of repeatedly marking a 5/6 Gearhulk. Broader tactical sequencing remains open.
- Corrected AI cast materialization so X in a permanent's later loyalty text does not invalidate its fixed-cost spell. A traced Ramp/Dimir game now casts Ugin rather than passing with a legal eight-mana play. Normalized Unicode loyalty minus signs, preventing `−X`/`−10` from increasing loyalty. Added a shared colored-permanent mana-value mass-exile handler and extended noncreature-land counter/animation parsing, including printed vigilance/haste. Canonical Ugin/Nissa and token fixtures pass; two seeded Dimir/Ramp games finish 1-1 with no timeout or parser-fallback log lines. This is a two-game diagnostic, not matchup balance or optimal-play evidence.
- Enforced supported one-draw-per-turn static restrictions before dredge and draw-replacement choices. Successful draws are counted across a whole turn, persisted through match snapshots, and reset on turn transition. Real Spirit of the Labyrinth/Narset/Thought Reflection/Divination fixtures cover multi-draw, prior draws, controller scope, dredge, and empty-library suppression; the browser casts Divination under Spirit. Verification: 1,077 isolated backend tests, frontend build/lint/unit, full browser harness, and a three-game replay without timeout or drift. Other static draw prohibitions and optional-draw edge cases remain open.
- Recognize bounded printed number words in nonland "Add N mana of any one color" abilities. Gilded Lotus now offers five three-mana choices to humans and supplies the full chosen amount during automatic payment; the browser fixture clicks a three-red-mana activation. Verification: 1,073 isolated backend tests, frontend build/lint/unit, the full browser harness, and a three-game replay without timeout or drift. Variable amounts and any-combination output remain unsupported rather than guessed.
- Changed mana affordability to account for each physical land/nonland source once instead of summing its color options independently. Automatic payment now prefers less flexible sources for a needed pip; Treasure `{R}{G}` rejection and Island/Watery Grave `{U}{B}` success have focused tests. Verification: 1,072 isolated backend tests, the full browser harness, and one deterministic three-game replay without timeout or anomalies. This remains a greedy allocator, not a complete search over all mana abilities and payment orders.
- Corrected supported fixed-output nonland mana abilities to produce their printed quantity in manual activation and automatic payment. Sol Ring and Llanowar Tribe fixtures cover colorless and colored output, leftovers and card-view amounts; the browser verifies the two-colorless-mana control. Verification: 1,070 isolated backend tests, frontend build/lint/unit, and the full browser harness pass. Mixed/variable output and flexible-source allocation still need work.
- Added checked manual activation of supported nonland tap mana sources, including Treasure and mana creatures. The public card view exposes currently available colors, the human UI shows controls only on owned ready sources, and wrong-color/wrong-seat requests are rejected without changing saved state. Verification: 1,068 isolated backend tests, frontend build/lint/unit, and the full browser harness pass. Multi-output and complex mana abilities remain outside this increment.
- Preserved printed quoted abilities on created creature tokens, enabling Fable's Goblin attack trigger to create Treasure. Added an offline Food/Blood/Treasure token seed with Scryfall IDs and Oracle text, and made shared nonland mana payment consume printed self-sacrifice costs. A direct Fable chapter-to-Treasure-to-red-mana test and 99 focused rules tests pass; three seeded Midrange/Drain games completed without inference misses. Manual nonland mana activation and broader token/mana interactions remain open.
- Added legal target generation, resolution rechecks and a reusable creature copy-token handler for Reflection of Kiki-Jiki-style text. Copies preserve base card data but not counters, gain haste when printed, and use the next end step's delayed sacrifice even on the opponent's turn. Focused tests pass; two same-seed Drain/Midrange replays completed with zero prior Reflection inference misses. Copy-layer edge cases and Fable's Goblin token attack ability remain open.
- Added reusable named artifact-token creation from Oracle reminder definitions, token-owned activated abilities and self-sacrifice costs. Food/Blood end-to-end tests cover payment, resolution, snapshot restoration and token ceasing; Witch's Oven's printed toughness threshold uses effective toughness. Two seeded Drain/Midrange games finished without stalls and exercised Food creation/activation, but also exposed an unsupported Reflection of Kiki-Jiki copy-token ability.
- Enforced printed sorcery-speed restrictions on activated abilities in both legal-move generation and authoritative action execution, with generic own-main, opponent-turn and nonempty-stack regressions. Other activation timing restrictions remain open.
- Excluded parenthetical Oracle reminder text from executable effect, target, trigger and activated-ability parsing. Replaced an internal zero-life-gain trigger placeholder with an explicit no-op and updated its prowess fallback. Representative Blood/Food reminder regressions pass; this milestone did not yet implement the named artifact tokens added above.
- Replaced the canonical Memory Deluge one-card-draw misinterpretation with a reusable mana-spent top-card selection effect. Added persisted human/AI two-card choices, correct non-draw zone movement, and printed Flashback cost admission/exile on resolution or countering. Focused normal-cast, Flashback, countering, snapshot and AI tests pass; a two-game seeded Dimir Control vs Ramp replay completed with normal and Flashback selections. Broader cost-modification and Flashback edge cases remain open.
- Replaced 81 handwritten fallback entries with an 87-card Scryfall-ID-backed offline seed covering every built-in deck card and six extras. A read-only exporter regenerates the seed from a synced cache, including double-faced/Adventure front and face metadata; four planeswalker loyalty values were verified against the exact-name API. Cached explicit zero stats now take precedence over fallback face stats. Removed the head-to-head runner's duplicate hydrator, which dropped cached face/layout/color data. Verification: 1,044 backend tests pass in an empty-cache tracked-source copy; byte-for-byte seed re-export and seed-100 Tempo/Dimir offline/cache normalized-action/final-state parity pass. This does not certify all 87 effects or custom cards.
- Repaired mana-value-restricted stack targeting for Drown in the Loch: the selected modal clause controls target restrictions, a target's announced X counts toward mana value, and changing graveyard size can make the target illegal before resolution. Verification: 1,043 isolated backend tests; five canonical-cache Tempo/Dimir games resolved with four Drown casts and no invalid-target or missing-inference logs. Corpus audit also found 61 of 81 handwritten fallback Oracle texts differ from local canonical cache; offline fallback replacement is now a priority, not claimed fixed here.
- Fixed canonical Negate being parsed as a no-op: it now counters noncreature spells, while both ordinary and conditional counter handlers reject creature spells even if called with a stale or forged target. Focused parser, target-hint and handler regressions and 1,040 isolated backend tests pass; broad counterspell clauses remain uncertified.
- Fixed a rules/zone corruption found by seeded AI diagnostics: Counterspell could target Sheoldred's draw trigger and move its source card to the graveyard while leaving a ghost entry in the battlefield list. Spell and ability stack items are now distinguished in target hints and counter handlers; canonical Stifle's "activated or triggered ability" wording is recognized. Focused legal-move, rejected-cast and handler regressions pass; 1,039 isolated backend tests pass. On Tempo/Dimir seeds 100-104, all five games resolved, the reported battlefield had at most one Sheoldred, and bad blocks fell from one to zero. This repairs one supported stack boundary, not all ability/copy rules or AI combat quality.
- Unified the verbose head-to-head trace with the shared decision-quality producer. Previously a completed Tempo/Dimir game yielded only land-drop and unused-mana metrics; reruns now report all five metrics, including lethal misses, bad blocks and stall streaks. Battlefield trace entries include effective keywords and marked damage so suspicious blocks can be inspected. Two subsequent games resolved with all five metrics available and no bad blocks; an earlier single bad-block warning lacks a saved seed/state and remains unclassified. Added `--seed` with per-game provenance; two 600-tick runs reproduced the same card/action sequence, while raw generated stack IDs differed. Verification: 1,037 isolated backend tests, focused trace tests, and Graphify refresh. This improves diagnostics, not AI decision quality itself.
- Repaired an AI target-materialization crash exposed by an isolated three-deck replay: a land-only target branch referenced an unassigned creature-target variable. A Nissa-style loyalty-target regression reproduces the failure before the fix. Afterward, 1,035 isolated backend tests pass; the Tempo, Dimir Control and Ramp three-pair replay completes without crashes or determinism drift. Tempo/Dimir reaches the 1,600-tick short cap but resolves at turn 65 under a 3,000-tick cap, again with no drift. These runs do not establish stronger AI.
- Removed a public-log leak in Expressive Iteration-style top-card choices: the card put into hand and the card put on the library bottom are not named, while the face-up exiled card remains named. An isolated HTTP regression reproduced the leak before the change; 1,034 isolated backend tests and frontend lint/build/unit checks pass afterward. This does not make shared-device human-vs-human play per-seat private or scrub older saved logs.
- Closed two search-related hidden-information leaks: [Wizards' Demonic Tutor notes](https://magic.wizards.com/en/news/feature/commander-masters-release-notes) say its found card is not revealed, so unrevealed hand searches now log only the count while explicitly revealed or public-destination searches may log names. Public match responses redact AI-owned pending mechanic options and library order without mutating internal choices; the frontend validates that redacted shape. Verification: 1,033 isolated backend tests and frontend lint/build/unit checks. Human-vs-human remains a shared-device sandbox without seat authorization.
- Preserved "up to" optionality in library-search effects and enforced the mandatory count for unrestricted searches under [Comprehensive Rules 701.23d](https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf). An HTTP Entomb choice now rejects an empty selection without moving cards, and the UI disables that invalid confirmation; Buried Alive AI chooses zero when Rest in Peace would exile all candidates. Verification: 1,031 isolated backend tests, 58 focused tests after a search-clause parser adjustment, and frontend lint/build/unit checks. Other search grammars remain unverified.
- Made AI library-search ranking destination-aware. A reproduced Reanimator decision with Reanimate in hand previously chose a Swamp over Griselbrand for a graveyard tutor; it now values reanimation targets and graveyard-playable spells rather than hand mana fixing. When Rest in Peace redirects the searched card to exile, it no longer chooses the premium creature. A second-archetype snapshot fixture guards against a card-name or archetype-only fix. Verification: 1,031 isolated backend tests and a seeded Tempo/Dimir Control BO3 with no timeout or drift at a 3,000-tick cap; the shorter 1,200-tick cap truncated one long game. This is bounded decision evidence, not general AI-strength certification.
- Corrected library-search destination inference for Entomb and Buried Alive patterns: unrestricted card selection is legal, selected cards enter the graveyard rather than hand, and Rest in Peace-style replacement still redirects that move to exile. Focused engine, snapshot-choice and HTTP-action regressions cover the boundary; other search wordings are not certified. Verification: 1,030 isolated backend tests, frontend lint/build/unit checks and a two-game seeded replay without determinism drift.
- Bounced tokens are no longer counted or selected for activated/additional discard costs, generic land/creature hand-to-battlefield effects, Ninjutsu, or legal-move generation before SBA. Exile play permission also excludes tokens. A generated land-token regression reproduces the former illegal action and verifies cost, effect and legal-move rejection. Verification: 1,027 isolated backend tests and a two-game replay without drift; the remaining transfer paths are inventoried in the token-transfer audit.
- Departed tokens can no longer be returned, recast, dredged, discarded, exiled for escape, or swept into exile from a graveyard before the next state-based check. The generic guard distinguishes immutable token identity from mutable card types; snapshots preserve that identity and older type-only snapshots remain readable. A type-changed token still suppresses nontoken dies triggers. Verification: 1,026 isolated backend tests before the final snapshot-helper cleanup, 68 focused tests afterward, frontend lint/build/unit checks, and a two-game replay without drift. Other same-resolution library/exile transfers require a broader transfer audit.
- Tokens that leave the battlefield now cease to exist on the next state-based action check. The engine removes them from graveyard/exile counts and records an internal `ceased` state while retaining source history for already-triggered abilities. Generated Soldier-token fixtures cover ordinary death, Rest in Peace exile, snapshot persistence and a Bastion of Remembrance dies trigger. Verification: 1,023 isolated backend tests and a two-game replay with no determinism failures or drift labels. Attempts to move a departed token again before that check remain uncertified.
- Extended the shared graveyard destination check for the canonical opponent-card clause on Leyline of the Void. It now uses the card's owner, excludes tokens, and evaluates simultaneous death destinations before the source leaves. Discard, resolved spell, stolen creature and mass-enchantment regressions pass; an HTTP action/SQLite-restore test covers an opponent-owned spell. A seeded two-game replay has zero determinism failures or drift labels. Leyline's opening-hand permission is not implemented by this change.
- Added HTTP action and SQLite-restore regressions for canonical Rest in Peace: Lightning Bolt exiles Doomed Traveler without creating its dies-trigger Spirit, and casting Rest in Peace exiles cards already in both graveyards when its ETB trigger resolves. An isolated backend run passed 1,016 tests before the final Doomed Traveler assertion; both final HTTP cases passed focused tests. Simultaneous human replacement choice remains open.
- Rest in Peace's canonical "from anywhere" graveyard replacement now routes supported death, discard, cycling, dredge-mill, cost, spell-resolution and state-based moves to exile. Its enters trigger exiles existing graveyards through the stack. The two strict expected failures now pass, with cross-zone real-card regressions; five older Rest in Peace fixtures now use its actual Oracle text. Verification: 1,014 isolated backend tests before the final fixture-only correction, 107 focused tests afterward, the full Chromium harness, and a two-game replay without drift or anomaly labels pass. More replacement ordering and human simultaneous-choice cases remain uncertified.
- Earlier in this milestone, two strict canonical Rest in Peace expected failures exposed battlefield death and hand discard; they were removed only after the shared destination path passed those fixtures.
- Combat lethal deaths now use the shared SBA path instead of a sequential combat-only remover. Supported replacement destinations for a simultaneous death batch are chosen while all sources are still on the battlefield. A canonical Lorcan, Warlock Collector/Arrogant Poet fixture tests the general creature-subtype replacement parser and source-death timing. Verification: 1,006 isolated backend tests before a final test-fixture data correction, a 72-test focused rerun afterward, the full Chromium browser harness, and a two-game seeded replay without drift or anomaly labels pass. Human multi-replacement choices and all-zone Rest in Peace behavior remain open.
- State-based actions now stabilize across successive waves before generated triggers are stacked. A real Elvish Clancaller/Llanowar Elves cascade and Grim Haruspex trigger-order snapshot test cover the case where an anthem source dies before its dependent creature. Verification: 1,004 isolated backend tests, the full Chromium browser harness, and a two-game seeded replay without drift or anomaly labels pass. Complex simultaneous replacement choices remain outside this bounded fix.
- Live deck hydration now carries canonical cached colors into the rules state. Color-based interactions prefer the selected face's colors, distinguish confirmed colorless from missing metadata, and parse hybrid symbols when only a mana cost is available. Figure of Destiny, Ruination Guide and Valki/Tibalt fixtures verify the boundary. Verification: 1,002 isolated backend tests, frontend lint/build/unit, and a two-game seeded replay without drift or anomaly labels pass. Broader color-changing continuous effects remain open.
- Fixed departed creatures' own "when this creature dies" triggers in the shared event collector. A real Doomed Traveler combat regression now puts its trigger on the stack and resolves a 1/1 flying Spirit. Generic token parsing separates printed color from token name, and token colors survive snapshot restore and appear in the public card/hover view. Replaced a fabricated token parser test card with the canonical Call the Cavalry text. Verification: 999 isolated backend tests, frontend lint/build/unit, full Chromium harness and a two-game replay without drift or anomaly labels pass. Named/atypical death wording and unusual token clauses still need broader coverage.
- Added persisted trigger staging across combat damage and the immediate state-based actions. The former strict-xfail Ohran Frostfang/Grim Haruspex case now offers one shared order choice; focused real-card APNAP and snapshot tests pass. A real human death-replacement pause/resume and later SBA waves remain unverified.
- Batched actual combat-damage events from a damage step before adding their triggers to the stack. Two creatures hitting simultaneously now present one human trigger-order choice instead of two independent insertions; the choice survives snapshot restore. Focused Ohran Frostfang/Grizzly Bears/Centaur Courser coverage passes, as do 994 isolated backend tests before the final test-only assertion, that assertion's focused rerun, and a two-game replay without drift or anomaly labels. Ordering against death and other state-based-action triggers remains open.
- Filled two combat-event gaps: trample spillover and blocker-to-attacker damage now emit actual `combat_damage_dealt` events, and source-specific damage triggers no longer fire when a different creature deals damage. Real Ohran Frostfang, Charging Monstrosaur, Shadowmage Infiltrator, and Grizzly Bears fixtures cover positive and negative trigger paths. Verification: 993 isolated backend tests, frontend lint/build/unit checks and a two-game seeded replay with no drift or anomaly labels pass. Broader simultaneous-trigger ordering remains open.
- Extended the conservative rules-gap warnings to Morph, Manifest, Suspend, Mutate, Craft and Discover, including cached card-face text. The simulator lists detected cards but still reports all win rates as exploratory; this adds diagnostics, not mechanic implementations or card certification. Verification: 989 isolated backend tests plus frontend lint/build/unit checks pass.
- Added a bounded rules-coverage trust label to card reports and persisted batch results. The Testing Simulator now marks win rates exploratory and lists detected unsupported cards; a shared pure classifier keeps deck diagnostics and analytics consistent. Verification: 986 isolated backend tests, frontend lint/build/unit and full Chromium harness pass. No arbitrary-card certification or hard simulation gate is claimed.
- Aligned both AI block paths with the engine's minimum-blocker count instead of assuming every restricted attacker needs exactly two blockers. Real Guile/Grizzly Bears fixtures cover a legal three-blocker fallback and the small-search choice to leave Guile unblocked rather than propose an illegal partial block. Verification: 985 isolated backend tests and a seeded two-game Burn/Dimir Control replay with zero timeout, anomaly labels or deterministic drift. Broader strategic evaluation remains open.
- Corrected large-board AI fallback blocking: it no longer assigns a ground blocker to a flyer or another attacker it cannot legally block, and it values the other band members blocked through a legal direct block. A five-attacker real-card fixture reproduces the old illegal choice and verifies propagated blocking. Verification: 983 isolated backend tests and a seeded Burn/Dimir Control BO3 replay with two resolved games, no timeout, anomaly or determinism drift. Strategic AI formation of attacking bands remains open.
- Deck card-data diagnostics now flag the unsupported "bands with other" mechanic from cached or fallback Oracle text and show affected card names in the import panel. Mainboard and sideboard are included. Verification: 982 isolated backend tests, frontend lint/build/unit and the full Chromium harness pass. This is a bounded warning, not a complete rules-support classifier; ordinary Banding remains supported separately.
- Corrected live-deck keyword inference: Oracle text beginning with ordinary Banding now produces the engine keyword, while "bands with other" does not. This closes a factory-to-combat gap missed by manually constructed banding fixtures. Benalish Hero and Old Fogey regression fixtures use their real card types, text fragments and printed stats. Verification: 981 backend tests pass in an isolated source/database copy; no frontend source changed in this repair.
- Added ordinary attacking-band declaration with server-side eligibility checks, snapshot/public-state persistence, and propagation of legal direct blocks to every live band member (including a flyer not directly blockable by the same ground creature). The combat UI now lets humans select attackers and band numbers rather than forcing all available attackers. Verification: 980 isolated backend tests, frontend lint/build/unit, and a Chromium fixture for band declaration and propagated blocking pass. A seeded 1,200-tick Tempo/Dimir BO3 replay has no drift but one long-game timeout. "Bands with other" and strategic AI band formation are not implemented.
- Applied the ordinary banding damage-assignment controller exceptions: a banding blocker transfers an attacker's split to the defending player, while a blocker facing a banding attacker transfers its split to the active player. AI chooses defensively when it controls an opponent's damage; restart retains the other player's provisional choices. Focused engine and browser fixtures use Benalish Hero, Palace Guard and printed stats. Verification: 972 isolated backend tests, frontend lint/build/unit, the full loopback browser harness and a deterministic two-game replay pass. Attacking bands and "bands with other" are still outside this increment.
- Validate trample against all damage assigned by the attacking player in one step, including a shared blocker receiving damage from another attacker or deathtouch source. Earlier splits remain provisional until the final attacking assignment; invalid totals reject without mutation, and the human can restart before damage. AI now accounts for prior assignments instead of wasting later tramplers on an already lethally assigned blocker. Real-card Palace Guard/Charging Monstrosaur fixtures and a browser restart path cover this boundary. Verification: 968 isolated backend tests, frontend lint/build/unit and the full loopback browser harness pass; a seeded two-game replay resolves in 40 turns without timeout or drift.
- Added resumable controller-selected combat damage splits for multiple blockers and shared blockers, with strict per-recipient API validation, numeric human controls and a bounded AI heuristic. Trample requires lethal assignment before defender damage; first/double-strike steps request fresh choices. Engine/HTTP/browser fixtures cover Palace Guard, trample to a player or planeswalker, snapshot restore, invalid choices and pre-damage power freezing. Validation: 964 isolated backend tests, frontend lint/build/unit, full loopback browser harness and a deterministic two-game replay pass. Cross-source trample and exotic simultaneous replacements remain open.
- Capped a blocker that blocks multiple attackers to its effective power once per combat-damage step. A Palace Guard regression with Llanowar Elves and Elvish Mystic reproduced illegal doubled damage before the fix; 48 focused combat tests, 955 isolated backend tests, the full Chromium harness and a seeded two-game replay pass afterward. At that milestone assignment still defaulted to the first attacker; the subsequent entry above adds a controller choice.
- Narrowed replay timeout attribution: a Spell Pierce payment failure followed by a countered spell is a normal game event, not a rules stall, even if it occurred in a game later truncated by the tick cap. Repeated recent unexplained payment failures still flag a rules issue. Focused classifier tests cover both cases. The seeded Tempo/Dimir 1,200-tick replay now labels its one truncated game `timeout_long_game` with zero deterministic drift; 954 backend tests pass in a clean isolated copy.
- Removed legacy forced `combat_damage` actions from live autoplay, batch/round-robin simulation, replay and AI rollout. Those shortcuts skipped the response window after first-strike damage. Focused live-autoplay and replay regressions preserve both windows; a seeded Tempo/Dimir BO3 replay finishes at a 3,000-tick cap with zero deterministic drift or anomalies. The 1,200-tick version timed out, so short caps remain unsuitable for long control games. Validation: 953 backend tests in a separate isolated copy, frontend lint/build/unit checks, and the full Chromium harness pass.
- Split supported first/double-strike combat into persisted first and regular damage windows with priority between them. First-strike blockers now deal damage even when the blocked attacker does not deal in that window; keyword eligibility is captured at the first window for correct regular-step behavior. Engine, snapshot and browser regressions cover these cases; multi-block assignment and interacting replacements still need certification. Validation: 951 isolated backend tests, frontend lint/build/unit checks and the full Chromium harness pass.
- Fixed the normal human combat path: unblocked attackers now deal damage as the combat-damage step begins, before players receive priority, without an internal-only `combat_damage` action. An engine pass-through regression and a natural human-vs-human browser BO3 caught and verify the repair. The browser series uses a noncompetitive all-Island opponent; first-strike windows were added afterward as noted above.
- Extended the played BO3 browser harness to control both human seats through mulligans, land drops, priority and the previous loser's play/draw choice. The human-vs-AI path remains covered; neither fixture estimates AI strength or matchup balance.
- Added a complete scripted-human browser BO3 using real Mono Red Aggro against a 60-Island AI deck. The test clicks production mulligan, land, spell, attack, priority, trigger-order and next-game controls and waits for authoritative revisions; no winner or state is forced. It is lifecycle evidence, not competitive AI acceptance; human-vs-human coverage was added afterward as noted above.
- Fixed simple Oracle single-target player-or-permanent alternatives across target hints, admission, human choice and damage resolution. A combined selector prevents announcing both targets. Canonical Lava Spike and Skullcrack regressions cover player/planeswalker choice, invalid targets, loyalty loss, prevention and printed-order turn restrictions; a browser action casts Lava Spike at a planeswalker. Complex multi-target clauses remain open.
- Removed synchronous Scryfall token-art fetches from game actions. Token creation now uses a persisted local token-art index or the shipped fallback immediately; `python -m card_data.token_images NAME POWER TOUGHNESS` explicitly prefetches art for later games. This avoids network-dependent rules stalls but unsynced tokens show generic art.
- Added live HTTP BO3 regressions using shipped Mono Red Aggro/Burn and Blue Control/Ramp lists, plus an Aggro/Burn browser path. They play natural seeded AI-vs-AI series through autoplay and rendered `AI Step x30` controls, restore the HTTP matches from SQLite between games, and check completed score and game progression. The battlefield exposes its public revision for browser synchronization. This is lifecycle coverage, not balance evidence or a full human browser game.
- Corrected deck-archetype shape estimates for cached modal/transform cards: a `//` name alone no longer makes them split cards, and back-face Land/Creature types no longer distort cheap-spell and creature-density priors. Canonical Valki, Delver and Bala Ged fixtures cover the distinction; the heuristic remains an estimate, not an AI-strength claim.
- Corrected replay timeout attribution to inspect only timed-out games in a BO3 and require repeated missed legal land drops before labeling a stall. A fixed-seed Tempo/Dimir game timed out at a deliberately low 1,200-tick cap but resolved at 1,836 ticks under a 3,000-tick cap; a separate resolved-game cost error no longer contaminates its timeout label.
- Unified game-state, rules, AI and deck-analysis land classification around explicit front-face types/type lines and exact basic-name fallback. Removed AI/backend land-action fabrication when legal moves omit a land, and hardened the backend guard against AI-selected card IDs not present in offered moves. Replaced obsolete tests that treated mana creatures and a made-up land as lands.
- Show human-controlled mainboard/sideboard inventory between games, prevent post-match and AI-seat manual swaps, clear draft swaps on seat changes, and verify a swap survives reload into game two through HTTP and browser tests. Deliberate AI sideboarding and a complete played BO3 remain open.
- Validate saved-match discovery summaries before recovery uses them; malformed IDs, mode, revision, turn or player names now fail at the API boundary. Unit and browser recovery paths pass.
- Validate successful legal-move responses at the frontend boundary, rejecting malformed actor, revision, move and card-view fields before they drive UI actions. Unit and browser contract gates pass; generated/shared API types remain open.
- Reuse a pending match-start key when Start is clicked again after ambiguous failures, preventing a second match before reload. Browser regression covers the repeated-click path.
- Added durable idempotency for match creation. A start-key receipt and snapshot commit together; same-key retries return the same game after a lost response or backend memory restore, while changed requests conflict. The frontend retains pending creation across reload and browser tests verify one match after one or two dropped successful responses. Extended multi-window and network operation remain open.
- Added a loopback browser CI job for 19 human action paths and three full-App recovery/restart checks against a copied backend database. Hosted run `36370371065` passed all three jobs, including 918 backend tests. The runner uses Chrome because hosted Chromium did not expose CDP; the ephemeral test browser runs without its sandbox. Full-game browser acceptance remains separate.
- Added TypeScript/React-hooks ESLint and a CI lint step. Fixed stale-hook dependencies in autoplay, response passing, deck refresh and legal-move filtering; no lint rules were suppressed. Clean `npm ci`, lint, build and unit checks pass locally, as do 19 browser action paths and App recovery/restart checks. The earlier baseline CI run passed both jobs; the new lint step awaits its hosted run.
- Added a clean-checkout GitHub Actions baseline for backend tests and frontend install/build/unit checks. Removed remaining frontend `any` casts in API environment access and match-mode selection; Vite environment types now provide the contract. Disposable `npm ci`, build and unit checks plus seven fresh-venv API smoke tests pass locally; hosted CI, lint and browser CI remain unverified.
- Supported the canonical draw-doubling exception for the first actual draw in each of your draw steps, including multiple sources, dredge-replaced first draws and snapshot persistence. Alhammarret's Archive-style life doubling is handled as an independent replacement clause; event-scoped consumed-source IDs allow its life and draw clauses to both apply without a replacement loop. Validation: 918 isolated backend tests, frontend build/unit checks, 19 browser action paths, and a deterministic two-game BO3 replay. Other conditional replacements remain open.
- Added reusable unconditional draw-doubling replacement handling for canonical Thought Reflection wording. Each source applies once per draw event; replacement-created draws can encounter other sources without infinite loops. Human draw-step and per-draw stack choices, nested dredge pauses, snapshots and later spell clauses retain ordered continuations.
- The production Controls/API browser harness now covers a draw replacement followed by nested dredge decisions (19 passing scenarios). Paused damage replacement chains also finish their originating stack item after the final choice.

- Corrected AI Annihilator sacrifices to prefer expendable tokens and weak creatures over lands or stronger threats. AI cleanup now pauses for a persisted legal discard choice and evaluates the full hand rather than discarding the first cards. The shared mechanic-choice setting retains compatibility with prior snapshot field names.

- Generalized persisted library choices to AI-controlled topdeck battlefield, creature-reveal and hand/exile/bottom effects. Live/replay AI now ranks resolution-time options rather than relying on each effect handler's fixed first/highest-cost fallback. Direct handler calls still have deterministic behavior, and the AI ranking is not expert-level planning.

- AI-controlled live, replay and batch matches now pause supported library searches at resolution and choose legal targets using current hand color demand and a bounded card-value heuristic instead of first-in-library order. Search-choice state survives snapshots; a regression covers selecting an Island needed for a blue spell. This is a tactical improvement, not a broad AI-strength claim.

- Added a second resolution-time human choice for supported topdeck effects with "any order" library-bottom text. Canonical Collected Company keeps the spell pending across both choices and snapshots, validates the complete bottom order, and completes through the production Controls/API browser path. Unattended play retains deterministic ordering.

- Supported topdeck battlefield effects now randomize the unchosen library-bottom cards only when Oracle text requires it. Storm the Festival's post-snapshot order matches the persisted match RNG; its older abbreviated test fixture was replaced with the canonical effect sentence.

- Moved supported library-search candidate selection from cast time to resolution and removed stale AI preselection from hidden cast hints. Human search choices survive snapshots and stack completion; one-card tutor inference now selects one card, not every match. Corrected a noncanonical Cultivate fixture and implemented its first-land-to-battlefield-tapped/second-land-to-hand split. Focused and browser tests cover the shared path. Broader tutor wordings and strategic AI search choice remain open.

- Moved Expressive Iteration-style hand/exile/bottom placement from cast-time library peeking to a resolution-time ordered human choice. Response-window library changes, snapshot/stack continuation and turn-relative exile permission have focused regression coverage; the production Controls/API browser path passes. Library search remains a separate cast-time timing gap.

- Moved supported creature/permanent topdeck battlefield selection from cast-time hidden-library previews to resolution-time pending choices. Human choices survive snapshots and resume stack cleanup; AI retains deterministic selection. Focused Collected Company and Storm the Festival tests cover changed library order, up-to limits and cast-time secrecy; the shared mana-value helper also counts `{C}` correctly for creature eligibility. Expressive Iteration-style and library-search timing remain open.

- Fixed a real Oracle-effect gap found in a full live API match: Recruitment Officer's mana-value-limited top-four ability no longer resolves as a no-op. The reusable creature-reveal handler also covers power limits, optional human choice after snapshot restoration and through HTTP, and random-order bottom placement. Corrected a prior test that used altered Recruitment Officer text. A seeded Ramp/White Weenie scripted-human/AI BO3 completes with zero unresolved-effect lines; this does not establish balance or broad top-library correctness.

- Added a reproducible self-signed HTTPS release-routing smoke using a disposable backend checkout. The built frontend passes same-origin `/api`/media and explicit HTTPS cross-origin modes in Chromium; both paths exercise health, deck import, match start/action and fallback art. Real deployment/security acceptance remains separate.

- Bounded the in-process simulator history to 20 terminal jobs. Startup loads recent results and reconciles unfinished jobs; older results remain available from SQLite. Focused tests cover pruning and database fallback. This does not limit on-disk retention.

- Public match responses now redact AI-controlled hands while retaining hand counts; AI legal-move queries no longer reveal hand card views. HTTP regressions cover human-vs-AI and AI-vs-AI visibility without mutating authoritative state. Separate-client human-vs-human privacy still requires authentication and per-seat views.

- Capped batch simulation admission to one concurrent run in the supported single-process API, shared by synchronous and background-job routes. Busy requests receive structured 429; focused tests cover competing requests and slot release on failure. Queueing, cancellation, retention and multiworker/network controls remain open.

- Testing Simulator job status now validates progress and completed result metrics at runtime and uses a typed record instead of `any`; malformed responses fail before the panel presents them. Build and unit tests pass. This does not validate every analytics field.

- Added a runtime match-response boundary on all live match API calls. It rejects malformed player/card views and non-list block assignments instead of trusting the TypeScript cast; unit cases and one backend-serialized match pass. Generated OpenAPI types and full response-contract coverage remain open.

## 2026-09-27

- Production frontend routing now defaults to same-origin `/api` rather than guessing an HTTP backend on port `9999`; card-image routing follows the same deployment policy. A separate backend remains configurable through `VITE_API_BASE_URL`. Build and routing unit tests pass; actual HTTPS/reverse-proxy acceptance remains open.

- Replaced deck-import name guesses for mana curve/colors with cached card metadata. The curve distinguishes zero-cost spells, lands and unknown cards, and uses front-face costs for modal/transform cards. Imported archetype analysis now receives resolved metadata; the UI displays the resulting curve and spell-color counts. This is descriptive analysis, not a mana-base or strategy certificate.

- Deck import now reports cached art-series/token/emblem objects as non-playable, and match-start admission rejects them with a structured 422 before any match is created. The shared check preserves legitimate transform cards. A real `Mountain // Mountain` art-series HTTP regression covers both entry points.
- Validation: 880 backend tests pass in a fresh isolated source/database copy; frontend TypeScript/Vite build and unit checks pass. The browser harness was not rerun for this backend-only admission change.

- Fixed cache alias precedence: exact card names now beat later face aliases, and art-series `Card` records cannot supply split-face aliases. Exact-only deck hydration avoids a full cache scan. A real `Mountain // Mountain` art-series regression prevents a basic Mountain from being mis-hydrated as a non-playable Card.
- Validation: 878 backend tests pass in a fresh isolated source/database copy; frontend TypeScript/Vite build and unit checks pass. The existing 15-path Chromium harness was not rerun for this backend-only cache change.

- Fixed a real-card AI crash after double-faced permanents transform: both transform handlers now apply numeric face characteristics and keywords through the shared adapter, and sweeper threat assessment uses effective power. Canonical Kumano/Delver regressions fail before and pass after. A corrected local-Oracle Mono Red Aggro/Burn interactive autoplay BO3 completes 2-0 without a stall; this one series does not establish balance.
- Validation: 877 backend tests pass in a fresh isolated source/database copy; frontend TypeScript/Vite build and unit checks pass. The interactive real-card BO3 is an additional diagnostic, not a determinism matrix.

- Added two browser regression paths for the previous loser's BO3 play/draw choice through production Controls and `/next-game`; both verify game-two starter and that live seed metadata stays hidden. All fifteen Chromium paths and the frontend build/unit checks pass. The fixture begins between games, so full-series and sideboarding acceptance are still open.

- Interactive BO3 now stores a root seed and derives repeatable per-game seeds without exposing live hidden-library order. The previous game's human loser chooses play or draw in the UI/API; AI losers choose play. Focused helper and HTTP tests cover chooser validation, game-two opener replay and persisted restore. Existing unseeded saved matches remain legacy; full-browser BO3 and AI sideboarding are open.
- Validation: 875 backend tests pass in a fresh isolated source/database copy; frontend production build and unit checks pass. A seeded two-game Mono Red Aggro/Dimir Control BO3 diagnostic replay has no timeout, anomaly label or determinism drift. That diagnostic does not exercise the interactive play/draw choice or prove balance.

- Supported divided-damage spells now recheck each recipient at resolution, ignore illegal recipients without reallocating announced damage and fail when all recipients are illegal. Protection checks include distribution recipients at cast time. Canonical Pyrotechnics regressions cover zone changes, protection, hexproof, player recipients and snapshot restoration. Other multi-target effect families remain open.
- Validation: 871 backend tests pass in a fresh isolated source/database copy; frontend production build and unit checks pass. A seeded Mono Red Aggro/Dimir Control BO3 completes two games in 36 turns with no timeout, anomaly label or determinism drift. This does not measure balance or AI quality.

- Supported self-cast single-target triggers now choose targets in their ability window, not on the creature spell. Canonical Ulamog tests cover separate stack objects, snapshot choice, no legal target, trigger-before-spell resolution and trigger survival after the spell is countered. Cast-only triggers and prowess no longer fire for copied spells, while explicit cast-or-copy effects retain their separate event path. A thirteenth browser action path covers Ulamog through the production UI/API. Modal, multi-target and broader cast-trigger semantics remain open.
- Validation: 866 backend tests pass in a fresh isolated source/database copy; frontend production build/unit checks and thirteen Chromium action paths pass. A seeded two-game Aetherdrift Aggro/Karlov Manor Control BO3 completes in 40 turns without timeout, anomaly label or determinism drift. This is bounded regression evidence, not balance or expert-AI proof.

- Crew now pays creature tap costs on activation and animates a Vehicle only when its counterable stack ability resolves. Source-creature removal does not undo the paid cost; the same Vehicle can change controllers before resolution, while a departed/re-entered object is not affected. Already-creature Vehicles can be crewed again; AI skips redundant animation and duplicate pending crew activations. Canonical Smuggler's Copter/Soul Warden tests and the existing browser crew path cover the response window. Vehicle-specific crew triggers and complex copy/layer effects remain open.
- Crew resolution now restores Artifact and Creature where needed; cleanup removes only types this crew effect added, preserving an already-creature Vehicle. Validation: 861 backend tests pass in a fresh isolated source/database copy; frontend production build/unit checks and all twelve Chromium action paths pass. A seeded two-game Aetherdrift Aggro/Karlov Manor Control BO3 completes in 40 turns without timeout, anomaly label or determinism drift. This does not establish balance or expert AI.

- Added resolution-time human accept/decline for supported optional triggered effects. Target announcement remains mandatory and earlier; an illegal target skips the optional decision. Pending choice is snapshot-safe and validated for the controlling seat; declining prevents effect/replacement application. Canonical Reclamation Sage tests and a twelfth browser action path cover both decisions.
- Validation: 854 isolated backend tests, frontend production build/unit checks and twelve Chromium human-action paths pass. A seeded two-game Aetherdrift Aggro/Karlov Manor Control BO3 replay completes in 40 turns without timeout, anomaly label or determinism drift. These are bounded regressions, not balance or expert-AI evidence.

- Added human target selection for supported single-target ETB triggers after simultaneous ordering. Choices persist in snapshots, validate acting seat and legal candidates, and fizzle on target loss; unattended play prefers an opposing permanent for destructive effects. Shared unqualified target hints now include friendly permanents. Canonical Reclamation Sage/Sol Ring/Copter fixtures cover ownership, ordering, no-target and illegal-target cases; browser fixture covers the production API/UI path. Non-ETB/multiple targets and broad Oracle semantics remain open.
- Validation: 853 backend tests pass in an isolated source/database copy; frontend production build and unit checks pass; all eleven Chromium human-action paths pass. A seeded two-game Aetherdrift Aggro/Karlov Manor Control BO3 replay finishes in 40 turns without timeout, anomaly label or determinism drift. This is regression evidence, not a balance or expert-AI assessment.

- Added independent modal land-face play actions and unconditional tapped entry; face characteristics persist through snapshots. Added Adventure resolution-to-exile permission for the caster, normal-face recasting, consumed permissions, counter/fizzle-to-graveyard behavior and single-target legality recheck before spell resolution. Stolen-card owner/caster battlefield placement follows the caster.
- Expanded the human action browser harness to ten paths, including a tapped land face and Stomp into exile then Bonecrusher Giant from exile. Canonical regression fixtures also cover both Pathway mana colors, expired temporary exile, Adventure counter/target loss, flash timing, AI face targeting and delayed casting after snapshot.
- Validation: 847 isolated backend tests, frontend production build/unit checks and ten browser scenarios pass. Seeded Aggro/Dimir BO3 replay has two games in 36 total turns without timeout or drift. Conditional land entries, multi-target rechecks, split mechanics and strategically optimal face retention remain open.

- Preserved canonical card layout and face loyalty/colors through cache sync, hydration and snapshots, with an additive legacy-cache migration. Selected modal spell faces now drive timing, costs, types/stats, stack identity and printed-characteristic restoration instead of using the front face's types or cost. Known transform-only backs are rejected as direct casts.
- Modal spell legal moves expose independently affordable faces; the human renderer selects available faces, resets stale costs/targets and pays the selected cost. AI materialization and cast bias use the offered face. Land-face actions, Adventure exile permissions, split restrictions and old-cache layout backfill remain unfinished.
- Validation: 836 backend tests pass in a new isolated source/database/cache copy (102.42 seconds, 798 deprecation warnings); production build, frontend unit checks and eight component/production-HTTP browser paths pass. A seeded two-game Aggro/Dimir BO3 replay has no timeout/drift. Canonical face fixtures test boundary contracts, not complete Oracle semantics or expert strategy.

- Separated conventional permanent spell compilation from later activated/triggered Oracle effects. Aura attachment and supported entry choices survive; entry events carry X and recognize modern "enters" wording. Canonical fixtures verify no activated damage on entry, delayed ETB draw/destruction, no self-trigger for "another" and no premature Aura draw.
- Validation: all five new cases fail before the fix and pass after; 827 isolated backend tests pass. Seeded Aggro/Dimir BO3 completes two games in 36 total turns without timeout/drift. Human trigger targets/optional choices, multiple ability clauses and mixed-type selected-face stack/zone handling remain open; no broader rules or AI certification is claimed.

- Added saved-match discovery and frontend ID-based restore, explicit automatic-play pause/resume, a shared non-queuing mutation gate, revision-checked legal reads, bounded fetch timeouts and lost-write reconciliation. Write keys use `getRandomValues`, including plain HTTP LAN pages.
- Match history/snapshot mutations now commit together with rollback of in-memory state on failure. Revisions and the latest 100 idempotency fingerprints survive restore; stale/conflicting guarded writes return 409 and matching retries return current authoritative state without applying again. Legacy headerless calls remain supported; creation/multiworker/network controls are not complete.
- Permanent cast hints/target admission no longer borrow later activated/triggered ability targets, and spell availability now includes artifact/enchantment/land/general-permanent candidate surfaces. Added cast-admission regressions across those families; resolution-time ability isolation and targeted trigger windows remain tracked blockers.
- Validation: 822 isolated backend tests, production build, frontend error/gate/key checks and six human-action browser paths pass. Additional full-App browser checks pass for refresh/duplicate clicks, an intercepted accepted response and an actual test-backend process restart. Original live database/servers remain untouched.

- Added bounded name/quantity deck contracts, explicit small-deck sandbox policy, discriminated human action/choice inputs and shared cached hydration for batch admission. Invalid shapes and unsupported fields return 4xx rather than reaching unchecked engine mutations.
- Checked human actions execute on copied state before publication; local per-match locks coordinate reads and writes. Added actor/source/face/cost/target checks, deliberate ordered London mulligan bottoms through zero cards, and visible frontend action errors. Persistence-failure atomicity, versions/idempotency, resume and multiworker safety remain open.
- Fixed real divided-damage wording/budget validation and generic AI activation targeting; own permanents remain legal any-target candidates without becoming default AI damage targets. Complete multi-role targeting and optimized allocation remain unfinished.
- Validation: 806 backend tests pass in isolated source/database; frontend build, seven error-message assertions and six Chromium component/HTTP flows pass. Seeded two-game BO3 replay has no timeout/drift. One fresh authorized Jev review supports bounded design claims, not release certification; no app LLM dependency was added.

- Added acting-seat battlefield controls, ordinary permanent activation/target forms, explicit crew selection, Ninjutsu and permitted non-hand card casting. Legal-move HTTP responses carry card views without enlarging AI search moves. Unknown action kinds warn instead of silently disappearing.
- Validated ability targets before costs, rejected invalid player/stack/graveyard targets, and fixed adjacent activated mana symbols being truncated. Variable activated costs remain explicitly unsupported, with no payment or legal-move offer. Added reusable isolated Chromium fixtures; full human-game and crew-stack acceptance remain open.
- Validation: 768 backend regressions pass in an isolated empty-cache/database source copy using existing pinned dependencies; TypeScript/Vite build (including harness typing) and five Chromium action scenarios pass. Graphify refreshed; live database and pre-existing coder plan preserved.

- Added snapshot-safe human cleanup discards, shared ownership-correct discard operations, deferred cleanup triggers, simultaneous damage/duration expiry, state-based stabilization and exception priority/repeated cleanup. Ordinary cleanup no longer permits casts/activations. GUI controls now expose draw, sacrifice and cleanup choices for either owning seat.
- Fixed the standalone deterministic replay runner to initialize an empty database before reading decks; it no longer relies on API/test startup. Cleanup and choice regressions plus a seat-2 render probe cover the new paths; full browser/restart and complex replacement acceptance remain open.
- Cleanup validation: full existing suite passes 762 tests after the final engine refinement; all five cleanup regressions pass, including an additional cascading-SBA fixture. Frontend build passes. A clean standalone Aetherdrift Aggro/Karlov Manor Control BO3 completes two games without timeout or deterministic drift; evidence is in `docs/plans/baselines/2026-09-27-cleanup-replay.json`.

- Repaired local-beta foundations: tracked generic-token fallback installation, shared API/diagnostic hydration preserving cached faces and zero stats, and public effective/base stats, faces, keywords, counters and damage. Updated typed hand/battlefield views, list-valued block assignments and hover details. Added HTTP/snapshot/empty-cache regressions; broader human/browser workflows remain open.
- Validation: 758 backend tests pass with freshly installed declared Python dependencies and an initially empty database/image cache; production TypeScript/Vite build and whitespace checks pass. Live database and the pre-existing coder plan were preserved. Browser and process-restart acceptance remain open.

- Archived the supplied two-stage Jev review and reconciled its older snapshot against `b4eba86`. Recorded partial draw/knowledge progress without closing cleanup, AI consumers or local/network release gates. No additional model calls or application fixes were performed for this reconciliation.

- Added reusable core handlers for Infect/Wither/Toxic, poison loss, Ninjutsu, Annihilator, Escape, Prototype and optional Dredge. Snapshot-safe mechanic choices resume multi-draw/nested effects and finish resolving spells once. Turn draws now use the shared replacement path; cycling/activated/loyalty abilities no longer emit spell-cast events.
- Retained combat participants until combat ends for post-damage Ninjutsu, persisted a once-only combat-damage guard, preserved mixed blocker damage sources and post-prevention lifelink amounts, and updated combat diagnostics accordingly. Complete keyword families and human UI integration remain open rather than being inferred from metadata coverage.
- Validation: 753 backend tests pass in a disposable copy with local image assets, frontend production build passes, and seeded Aggro/Dimir BO3 replay has zero timeouts or determinism failures. This does not close the tracked-only fallback-asset release gate.

- Added canonical all-Oracle card knowledge ingestion, exact-name/corpus/search ruling verification, and a coverage report. Bulk ingestion preserves faces, legalities, keywords, provenance and same-name variants without overwriting the gameplay cache or claiming rules support. Local bulk data is rebuildable and remains outside Git.
- Imported 38,690 unique Oracle records / 6,433 faces locally; repeat import changed zero records. Verified rulings for 87 canonical cards covering 88 corpus names, with no corpus metadata/rulings gaps. Added a reproducible mechanics inventory and committed evidence summaries; tactical AI consumption and all-card rules support remain unfinished.

- Replaced the historical finish-plan patch notes with three release gates and 16 ordered implementation steps based on the September application audit.
- Recorded the audit's clean-checkout failures, live-match integration gaps, pinned-environment results, and limits of the deterministic smoke evidence.
- Added `docs/audits/2026-09-27-app-audit.md` as the repository audit reference. This documentation milestone does not mark implementation tasks complete.

## 2026-07-21

- Spell timing and seeded match validation milestone:
  - Enforced default sorcery-speed timing for sorceries and non-flash permanents instead of only honoring explicit timing clauses.
  - Regression traces now distinguish main-phase actionable passes from legitimate instant-speed hold decisions and long games.
  - Mono Red Aggro vs Dimir Control completed best-of-3 and best-of-9 at the 1,800-tick cap with zero timeouts/determinism failures; best-of-9 was 5-4.
  - Full non-API backend validation passes `560` tests; full-corpus balance remains open.

- Saga/event and land-legality milestone:
  - Added generic Saga chapter II next-creature entry counters and chapter III transformed back-face resolution with snapshot-safe pending state.
  - Supported Delver, Sprite Dragon, and Soul-Scar Mage event patterns no longer emit false cast-parser fallback diagnostics.
  - Land drops are no longer offered while the stack is live, removing false missed-land-window reports.
  - Double-faced cards use front-face types until transformation.
  - Full non-API backend validation passes `558` tests; the corrected four-deck hydrated replay completed 6 games with zero hard errors, land anomalies, stalls, or unresolved Oracle families.

- Diagnostic metadata and X-cost fidelity milestone:
  - Verbose round-robin and deterministic replay now hydrate deck cards from the shared local cache/fallback boundary before constructing games.
  - X-value selection accounts for the selected spell's type/name when applying static taxes, preventing invalid retry loops for taxed X spells.
  - Combat analytics ignores tapped blockers when classifying attack quality.
  - Unknown/noncreature cards no longer receive fabricated 2/2 stats; missing characteristics remain unknown until card data supplies them.
  - Added regressions for hydration, honest characteristics, taxed X costs, and tapped blockers. The corrected four-deck replay had 0 timeouts, cost failures, invalid targets, or stall streaks, while exposing the next unresolved Oracle families for follow-up.

- Explicit effect timestamp milestone:
  - Battlefield permanents now receive a persisted monotonic `effect_timestamp`; older `static_order` metadata remains a compatibility fallback.
  - Continuous-layer traces and replacement candidate ordering use timestamps before deterministic tie-breakers.
  - Snapshot round-trip regression coverage verifies timestamp ordering survives restart.
  - Full backend validation passes `547` tests; frontend production build and deterministic replay smoke pass.

- Continuous layer ordering milestone:
  - Layer traces now rank supported keyword effects before base-P/T setters and modifiers, then apply timestamp and battlefield tie-breakers within a layer.
  - Regression coverage verifies the ordered trace without broadening unsupported Oracle interpretation.
  - Full backend validation remains `547` tests; frontend production build and deterministic replay smoke pass.

- Prevention override milestone:
  - Stack replacement discovery now receives source/combat context and suppresses impossible prevention choices when a supported “can't be prevented” effect applies.
  - The replacement-options API policy label now reports `latest_effect_timestamp`.
  - Full backend validation passes `548` tests; frontend production build and deterministic replay smoke pass.

- Static spell-tax milestone:
  - Added reusable Oracle-driven generic cost modifiers for supported spell-tax wording instead of card-name exceptions.
  - Move legality, AI feasibility, and payment now share the adjusted cost for creature/noncreature and opponent-scoped taxes.
  - Full backend validation passes `550` tests; frontend production build and deterministic replay smoke pass.

- Keyword override milestone:
  - Separated ordinary keyword removal from supported `can't have` overrides in the continuous-effect layer.
  - Override effects now apply after supported grants/removals regardless of timestamp order.
  - Full backend validation passes `551` tests; frontend production build and deterministic replay smoke pass.

- Transformed replacement-chain milestone:
  - Draw and life-gain replacement payloads now carry consumed source IDs across transformed events.
  - Automatic and human-selected chains no longer reapply the same source or loop between draw and life gain.
  - Full backend validation passes `552` tests; frontend production build and deterministic replay smoke pass.

- Persisted replay browser milestone:
  - Diagnostic runs now expose bounded ordinary game summaries and 80-line log excerpts through the API.
  - The Testing Simulator includes a game selector while avoiding full JSONL loads in memory.
  - Full backend validation passes `552` tests; frontend production build and deterministic replay smoke pass.

- Bounded run comparison milestone:
  - Added `/diagnostics/compare` and Testing Simulator controls for numeric deltas between persisted runs.
  - Comparison avoids raw log loading; full line-by-line replay diff remains separate.
  - Full backend validation passes `553` tests; frontend production build and deterministic replay smoke pass.

- Persisted replay diff milestone:
  - Added `/diagnostics/compare/replay` to compare selected persisted games and return the first normalized divergent line with root-cause classification and bounded context.
  - Added Testing Simulator controls for comparing game indexes from two diagnostic runs.
  - Full backend validation, frontend production build, and deterministic replay smoke remain release gates.

- Paginated replay playback milestone:
  - Added `/diagnostics/runs/{run_name}/games/{game_index}` with bounded line pages for selected persisted games.
  - Replay comparison metadata now strips raw log arrays so the API cannot accidentally return an entire game log.
  - Added Testing Simulator controls for paging through selected game logs.

- Effective-stat combat AI milestone:
  - Attack/block heuristics and bounded combat search now use resolved effective power/toughness rather than raw printed stats.
  - Blocker decisions derive the defending player from blocker control, not whichever player currently has priority.
  - Added anthem-buff and attacker-priority regressions; full backend validation passes `556` tests.

- Persisted diagnostics browser milestone:
  - Added bounded `/diagnostics/runs` and `/diagnostics/runs/{run_name}` API routes for stored summaries, anomaly clusters, and capped sample games.
  - Added API regression coverage for listing, missing runs, artifact metadata, and the 25-record sample bound.
  - Added Testing Simulator controls for refreshing persisted runs and opening compact root-cause snapshots without loading raw multi-megabyte logs.
  - Full backend validation passes `546` tests; frontend production build passes.

## 2026-07-19

- Adaptive Master+ search milestone:
  - Late developed boards now receive bounded three-ply strategic planning with a four-action beam.
  - Sparse and early-game states retain the existing cheaper horizons; the focused gate now passes 365 tests.

- Simultaneous SBA milestone:
  - Non-paused lethal creature deaths now move as a batch before leave/death trigger collection.
  - Supported `one or more` death triggers are deduplicated across the simultaneous event.
  - The focused rules/AI gate now passes 364 tests; legend-rule batching and mixed SBA classes remain open.

- Human chained replacement milestone:
  - Human damage replacement choices now reopen for each remaining applicable source after the event is modified.
  - Used source IDs persist through snapshots and cannot be reused for the same damage event.
  - The focused rules/AI gate now passes 363 tests; additional replacement families and simultaneous SBA batching remain open.

- Nested lethal replacement milestone:
  - State-based lethal deaths and combat cleanup now pause for human die-replacement choices before moving the card.
  - Continuations preserve ownership, exile/graveyard semantics, and subsequent death triggers; AI/replay remains deterministic.
  - Legend-rule duplicate permanents now use the same continuation path.
  - The focused rules/AI gate now passes 359 tests. Simultaneous SBA batching and chained combat prevention choices remain open.

- Chained prevention milestone:
  - Damage replacement events now re-evaluate remaining prevention sources and apply each source at most once per event.
  - The focused rules/AI gate now passes 360 tests; human follow-up prompts for multi-step replacement chains remain open.

- Layer override milestone:
  - Added common `can't have` continuous keyword removals to the layer-6 static-effect path.
  - The focused rules/AI gate now passes 361 tests; full dependency ordering and chained human replacement prompts remain open.

- Simultaneous trigger ordering milestone:
  - Human-controlled trigger groups can be ordered before they are placed on the stack, with APNAP controller grouping preserved.
  - Choices are exposed through legal API moves, snapshot-persisted, and rendered in the frontend; AI/replay retains deterministic fallback ordering.
  - The focused rules/AI gate now passes 356 tests. Nested combat/SBA replacement continuations and full layer dependencies remain open.

- Replacement pause/resume milestone:
  - Human-controlled top-level damage, life-gain, draw, and die-zone stack events now pause when multiple replacement effects apply.
  - The frontend renders source-specific replacement choices and blocks pass, step, and autoplay actions until the choice is resolved.
  - Pending choices and the original stack item survive snapshots; AI/replay retains deterministic timestamp selection.
  - The focused rules/AI gate now passes 355 tests, including explicit source selection for die-to-exile replacements. Nested combat/SBA prompts and simultaneous trigger ordering remain open.

- AI search-budget milestone:
  - Bounded Master/Master Plus deep-copy search by total battlefield size and legal-action count.
  - Dense token boards now retain deterministic heuristic/combat evaluation instead of allowing two-ply/rollout branches to monopolize simulator runs.
  - Tokens vs Ramp completed a three-game diagnostic at the 1,200-tick cap with 0 timeouts after the guard; its 3-0 result is diagnostic evidence only, not a balance conclusion.
  - Added regression coverage; the consolidated rules/AI gate now passes 341 tests.

- Tactical decision-quality milestone:
  - Verbose head-to-head traces now retain effective keywords, attacker/blocker assignments, X values, and legal-action counts.
  - Card-play analytics now reports evasion-aware attack quality, lethal attack opportunities/misses, profitable versus losing blocks, and resource-preservation signals.
  - Master blocker search now avoids non-lethal pure chump assignments that remove no attacker, with focused coverage for both safe-life chumps and lethal prevention.
  - Post-change Tokens vs Ramp diagnostic completed without timeouts, obvious bad attacks, or losing-block classifications.
  - The consolidated rules/AI gate now passes 344 tests.

- Replacement-choice contract milestone:
  - Added reusable timestamp-ordered replacement candidate discovery for player damage, permanent damage, life gain, card draw, and die-to-exile events.
  - Added `/matches/{match_id}/replacement-options` with source metadata and a stable selection contract.
  - Explicit `targets.replacement_source_id` choices now flow through AbilitySpec and effect payloads; AI/replay callers retain deterministic latest-source fallback.
  - Added replacement, ability-model, and API regression coverage; the consolidated gate now passes 353 tests.
  - Mid-resolution pause/resume and simultaneous trigger ordering choices remain the next fidelity slice.

- Rules corpus milestone:
  - Added conditional noncreature counterspell targets with explicit `unless` payment choices and deterministic automated resolution.
  - Added generic noncombat-damage replacement to `-1/-1` counters, power-based death-trigger damage, Hydroid Krasis-style self-cast X triggers, and X-counter entry handling.
  - Added Realmwalker-style chosen creature type persistence and top-library creature casting with snapshot support.
  - Broadened Expressive Iteration wording and plural number parsing, and separated structured event paths from true parser fallbacks in the corpus report.
  - The current corpus report classifies 3,441 copies as structured effects, 155 as structured events, 184 as static/no-op, and 0 as parser fallbacks or missing Oracle.
  - The consolidated rules/AI regression gate now passes 340 tests.

- Oracle corpus audit:
  - Added `backend/scripts/oracle_corpus_report.py`, which scans all built-in and expansion deck entries, uses cached metadata when available, and ranks unresolved Oracle behavior by weighted copies and reusable family.
  - The current corpus report covers 81 unique cards and 3,780 copies across 11 built-in and 52 expansion entries. It reports parser fallbacks separately from missing Oracle metadata so cache gaps are not replaced with guessed card text.
- Conditional target legality:
  - Added reusable target restriction metadata and filtering for common nonartifact, nonland, noncreature, creature-or-planeswalker, artifact-or-enchantment, and mana-value limits.
  - Dynamic limits based on controlled basic lands and a target controller's graveyard are evaluated from the current game state.
  - Human validation, AI target materialization, and structured effect payloads share the same restriction surface.
  - Added regression coverage; the consolidated rules/AI gate now passes 323 tests.
- Modal choice ordering:
  - Mode selection now occurs before target generation in AI materialization, and the engine rebuilds mode-specific target hints before validating a cast.
  - `Choose two` selections resolve through an ordered `effect_sequence` path with regression coverage; the consolidated gate now passes 325 tests.
- Replacement candidate selection:
  - Multiple mutually exclusive static damage-prevention effects no longer all apply to the same event.
  - Replacement candidates use latest deterministic timestamp ordering by default and accept an explicit source ID for API/replay callers across damage, draw, and life-gain paths.
  - Added regression coverage; the consolidated rules/AI gate now passes 328 tests. Human replacement-choice pause/resume remains planned.
- AI decision-quality diagnostics:
  - Verbose card-play analytics now reports pass-with-unused-mana and main-phase land-not-first counters separately from ordinary response-window passes and land availability windows.
  - Added regression coverage for the new metrics; attack/lethal/block quality and engine-protection metrics remain the next AI diagnostics slice.
## 2026-07-18

- Choice and search resolution:
  - Added a shared library-search matcher for type, subtype, basic-land, permanent, and mana-value restrictions.
  - Tutor and landcycling moves now expose candidate cards and a validated selection schema to callers.
  - Explicit search selections are carried onto the stack and revalidated when they resolve, while older AI/replay callers retain deterministic first-match behavior.
  - Added frontend multi-select controls for human tutor choices.
  - Added regression coverage for legal non-first selections and rejected nonmatching cards; the consolidated rules/AI gate passes 225 tests and the three-game replay smoke has zero determinism failures.
- Modern rules state:
  - Added persistent game-wide day/night state with the zero-spell and two-or-more-spell upkeep transitions.
  - Spell casts are counted at the point a spell is placed on the stack; the count and day/night state survive match snapshots.
  - Daybound and nightbound double-faced permanents transform through a reusable effect handler, and the current state is visible in the battlefield header.
  - Day/night transition triggers now enter and resolve from the normal stack/APNAP event path.
- Attachment rules:
  - Corrected case-insensitive Aura and Equipment detection.
  - Added reusable Aura restrictions for creature, artifact, enchantment, land, planeswalker, permanent, and player targets.
  - Human/AI cast hints now expose Aura candidates, and state-based actions recheck attachment legality before detaching Equipment or putting invalid Auras into their owner's graveyard.
- Control changes:
  - Added reusable Oracle inference and effect resolution for common “gain control of target ...” effects.
  - Temporary control changes move the permanent between battlefield controllers and return it at cleanup without changing ownership; duration state is persisted in match snapshots.
- Zone-change triggers:
  - Added a shared `leaves_battlefield` event for common destruction, exile, sacrifice, lethal combat, and state-based movement paths.
  - Added controller-scoped creature/permanent/artifact/enchantment leave-trigger matching through the normal APNAP stack path.
- AI combat planning:
  - Master and Master Plus now enumerate bounded legal blocker assignments on small boards and evaluate cloned combat resolutions for lethal prevention, trades, and post-combat value before falling back to heuristic blocking.
  - Added regression coverage for choosing a profitable lethal-prevention block.
- Replacement fidelity:
  - Nontoken/non-token death replacements now inspect the dying permanent's token status, preventing token creatures from being incorrectly exiled.
- AI diagnostics follow-up:
  - Fixed Master/Ramp tutor decisions that omitted required library-search card IDs after explicit search validation was enabled.
  - The reproduced Dimir Control vs Ramp trace no longer emits invalid-search errors; its remaining long-game timeout is classified as a legal closure/balance case.
  - Fixed graveyard-spell target discovery and AI materialization so recursion finishers are not filtered out as having no legal targets.
- Top-library choice resolution:
  - Added explicit hand/exile/ordered-bottom choices for Expressive Iteration-style effects.
  - Human choices are validated so every inspected card is placed exactly once; AI chooses a deterministic value-ranked order when no choice is supplied.
  - Added regression coverage; the focused gate passes 61 tests and the three-game replay smoke has zero determinism failures.
- Tempo and combat rules:
  - Added reusable ownership-correct battlefield bounce for common “return target nonland permanent to its owner's hand” and creature variants.
  - Bounce targets are exposed to human/AI choice validation, emit battlefield-leave events, and return stolen permanents to the owner's hand.
  - Master/Master Plus now search small-board attack subsets through legal blocker assignments and combat resolution, avoiding hopeless chip attacks while preserving lethal and mandatory attacks.
  - The consolidated rules/AI gate passes 246 tests; frontend build and three-game deterministic replay smoke pass with zero drift or determinism failures.
  - Attack-subset search is limited to late-game boards with at most three attackers and two blockers so it cannot monopolize long simulator matrices.
- Saga rules:
  - Added lore-counter progression at precombat main, chapter parsing, stack-backed chapter abilities, and final-chapter state-based sacrifice.
  - Added Fable of the Mirror-Breaker fallback metadata with Saga type information and chapter text.
  - Added regression coverage; the consolidated rules/AI gate now passes 248 tests and the three-game replay smoke has zero determinism failures.
- Vehicle rules:
  - Added explicit crew moves with candidate creature power, duplicate/untapped validation, and temporary Vehicle creature status.
  - Crew taps the selected creatures, lets the Vehicle attack or block during the turn, and reverts the type at cleanup; AI materializes the smallest high-power legal crew group.
  - Added regression coverage; the consolidated rules/AI gate now passes 250 tests and the three-game replay smoke has zero determinism failures.
- Target legality:
  - Shared target validation now rejects stale or cross-zone IDs for restricted target categories while preserving unrestricted “any target” protection/hexproof checks.
  - The consolidated rules/AI gate now passes 263 tests.
- Mass exile rules:
  - Added a reusable ownership-correct `exile_all_creatures` effect for Farewell-style Oracle text.
  - Mass exile emits battlefield-leave events and moves each creature to its owner's exile zone instead of using destroy/death semantics.
  - Mass creature destruction now emits the same battlefield-leave event before moving cards to graveyards, keeping leave-trigger ordering consistent across mass zone changes.
  - Simultaneous mass leave/death events now batch trigger collection and deduplicate `one or more` abilities without collapsing ordinary per-object triggers.
  - Modal choice extraction now supports Scryfall bullet-formatted modes and `Choose two` schemas while preserving readable labels for frontend and AI choices.
  - Battlefield topdeck tutors now expose validated candidate selections to humans and AI, and Collected Company-style deployment honors explicit selected cards.
  - Stack countering now honors source-level `can't be countered`/`cannot be countered` text and uses spell ownership for the countered card's graveyard.
  - Spell-created “this turn” restrictions now persist through the active turn, survive snapshots, block later life gain or damage prevention, and expire at cleanup.
  - Legend-rule state actions now use ownership-correct death replacement and emit leave/death events when the duplicate actually dies.
  - Combat now handles generic Bushido, Rampage, and Flanking modifiers at blocker declaration with temporary stat cleanup and lethal-damage coverage.
  - The consolidated rules/AI gate now passes 319 tests and the replay smoke remains deterministic.

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
## 2026-07-19 - Stable Card Cache Resolution

- Fixed cwd-dependent SQLite selection in `backend/persistence/db.py`; the API, card sync, and diagnostics now resolve the canonical `backend/mtg_lab.db` file from the module path.
- Added a regression test covering launches from arbitrary working directories.
- Re-ran the Oracle corpus audit against the corrected cache: 81 unique cards, 3,780 copies, 3,441 structured-effect copies, 155 structured-event copies, and 184 static/no-op classifications. The prior missing-Oracle count was caused by reading a stale root-level database and is no longer used.
