# Changelog

## 2026-10-02 - Temporary ability loss, base stats and split second

- Added bounded temporary all-ability loss and base-stat setters with shared resolution timestamps, original-object binding, cleanup/zone expiry and detached durable snapshots. Static and resolution base setters share timestamp order; canonical stats and physical counters are not rewritten.
- Preserved recognized ETB tap-then-loss instructions through both-seat human target choices and restart. Split second now gates casts and supported nonmana activations across actual spells/copies without blocking mana, priority or triggers. The AI's bounded public-board target projection includes recognized temporary loss/base-stat effects.
- Verified 2,761 isolated backend tests (297 deprecation warnings), 100 focused checks, frontend lint/unit/build and the final-engine full Chromium harness. Twelve logical seat-balanced smoke games each repeat twice with no reported drift, timeouts or anomaly labels. Tests caught standalone split-second parsing, dropped trigger continuation and an opaque stack-fixture adapter regression; failed/superseded checks are preserved alongside final evidence on RCHFiles under `diagnostics/temporary-ability-loss/20261002T050905Z/`.
- Updated README, finish plan, scope docs and AST graph; clarified already implemented basic proliferation/entry routes versus remaining variants. Arbitrary effects, complete dependencies/provenance, broader AI quality and operational release gates remain unfinished. Alpha UI redesign remains deferred.

## 2026-10-02 - Static/replacement source suppression and layer-query cost

- Connected supported ability loss to continuous bonuses/keyword sources, counter/token/life replacements, counter prohibitions, draw limits, land/library permissions, recognized cost modifiers and timing/mana readers. Suppressed printed recurring rewards no longer inflate AI board value; physical shield counters remain functional.
- Preserved the supported combined loss/base-stat effect across layers without reviving independent abilities on its source. Corrected equivalent counter-replacement recipient wording generically. Canonical fixtures and both-seat golden states validate outcomes, restoration and unchanged printed metadata; a stale proliferation assertion now explicitly tests prohibition suppression and restoration.
- Removed redundant timestamp sorting from boolean loss queries and prepares loss sources once per pure layer query, without a persistent mutable-state cache or reduced search depth. A retained 50-creature fixture microbenchmark is about 4.4–4.6x faster than the published helper; this is not whole-game/worst-case AI latency certification.
- Verified 2,739 isolated backend tests (295 deprecation warnings), 281 focused checks, frontend lint/unit/build and the final-engine full Chromium harness. Twelve logical seat-balanced smoke games repeat twice without reported determinism failures, timeouts or anomaly labels. Failed and deliberately cancelled superseded validations are labeled separately and retained with final evidence on RCHFiles under `diagnostics/static-ability-suppression/20261002T042530Z/`.
- Updated README, finish plan and AST graph. Arbitrary/conditional/temporary losses, gained non-keyword abilities, full type/color/dependency layers, pre-entry/simultaneous replacement fidelity, broader AI quality and operational release gates remain unfinished. Alpha UI redesign remains deferred.

## 2026-10-02 - Printed activation and trigger suppression

- Connected supported battlefield all-ability loss to shared mana capacity/payment, activated/loyalty/equip/crew move generation and checked activation writes. New keyword grants do not restore printed Oracle abilities; unaffected basic lands retain intrinsic mana abilities.
- Applied suppression to printed trigger collection and persisted pre-departure suppression in last-known information for supported self-death triggers. Already-stacked triggers/activations remain independent. Canonical Humility, Dress Down, mana, activation, entry and death fixtures cover both seats; HTTP/SQLite tests reject illegal writes without state changes.
- Verified 2,716 isolated backend tests (295 deprecation warnings), 173 focused checks, frontend lint/unit/build and the full final-source Chromium harness. Twelve logical seat-balanced smoke games repeat twice with no reported determinism failures, timeouts or anomaly labels. Focused testing found and fixed an optional card-identity adapter regression; failed and final checks are retained with canonical fixtures on RCHFiles under `diagnostics/printed-ability-suppression/20261002T040613Z/`.
- Updated README, finish plan and AST graph. Static/replacement/prevention/permission Oracle readers, arbitrary gained abilities, full dependencies and simultaneous departure/reentry LKI remain unfinished; the full suppression gate stays open. Broad AI strength and operational gates are not certified. Alpha UI redesign remains deferred.

## 2026-10-02 - Resolution-created keyword timestamps and target projection

- Replaced metadata-only resolved grants with durable object-bound effect records carrying creation timestamps, duration, operation and available source provenance. Supported grants/removals interleave with static/attached effects and keyword counters, survive restart and expire independently of physical counters. Legacy snapshot timing is explicitly inferred, not invented.
- Added bounded targeted/self keyword gain/loss clauses and preserved later draw instructions. Shared AI projects only recognized public-board keyword changes when choosing targets, without drawing or mutating authoritative state. Canonical Jump, Leap, Canopy Claws, Act of Treason and Twiddle fixtures retain provenance.
- Fixed lexical tap/untap confusion and missing standalone untap clauses; real control-change sequences now verify control, untap and haste. Land-animation's integrated untap remains once-only. Optional tap/untap choices are reported as unsupported instead of guessed.
- Verified 2,698 isolated backend tests (293 deprecation warnings), 271 focused checks, frontend lint/unit/build and the full final-source Chromium harness. Twelve logical seat-balanced smoke games repeat twice without reported drift, timeouts or anomaly labels. Earlier failed/superseded runs are preserved with final evidence on RCHFiles under `diagnostics/keyword-effect-timestamps/20261002T035328Z/`.
- Updated feature scopes, finish plan and AST graph. Full dependencies, non-keyword suppression, generalized durations/replacements, broad AI strength and operational release gates remain open. No UI redesign was performed.

## 2026-10-02 - Source-specific hexproof and object-bound grants

- Corrected Scryfall variant-family metadata so supported printed color/type hexproof does not become unrestricted immunity. Source-aware checks now feed cast/ability/loyalty hints, modal/divided targets, trigger choices and resolution rechecks; loyalty proxies retain source identity.
- Separated resolved battlefield keyword grants from printed metadata and physical counters. Grants preserve instances across snapshots, default safely in legacy snapshots and clear on zone reset. Hexproof family removal/cannot-have overrides include variants; supported departed trigger sources retain last-known colors/types.
- Verified 2,668 isolated backend tests (291 deprecation warnings), 239 focused checks, frontend lint/unit/build and the final-source full Chromium harness. Twelve logical seat-balanced games repeat twice without reported drift/timeouts. Full-suite testing caught an optional-Oracle adapter regression, fixed before this final run; superseded failures are retained with evidence.
- Updated the finish plan, current feature scope and AST graph, and archived verified evidence on RCHFiles. Arbitrary quality/as-though/player variants, complete layer ordering, broad AI quality and operational release gates remain unfinished. Alpha UI redesign remains deferred.

## 2026-10-02 - Combat keyword instances and delayed sacrifice

- Implemented Exalted/Decayed intrinsic stack triggers, supported non-redundant instance counts and effective Decayed blocking restrictions. Delayed sacrifice survives snapshots/SQLite restart, fires once and retains the original object/controller; both stages can be countered.
- Exposed validated keyword instance counts alongside existing unique keyword labels. Master small-board search includes attack/block triggers and end-of-combat consequences, rejecting unknown choices or hidden-zone changes instead of ranking them.
- Verified 2,641 isolated backend tests (289 deprecation warnings), 131 focused pre-HTTP checks and 27 final keyword checks, frontend lint/unit/build and the full Chromium harness. Twelve logical seat-balanced smoke games repeat twice without reported drift or timeout; this does not establish broad balance, expert AI, clean install or visual quality.
- Reconciled current feature scopes/finish plan, refreshed the AST graph and retained evidence on RCHFiles. Arbitrary grant composition, keyword variants, full ability suppression, simultaneous replacements and operational gates remain open. Alpha UI redesign remains deferred.

## 2026-10-02 - Shield effects and shared destruction protection

- Implemented shield-counter damage prevention and effect-destruction replacement across supported targeted/bulk destruction and combat paths. Indestructible does not spend a shield; unpreventable damage still spends one without preventing damage. Simultaneous multi-block combat shares one shield event, while first-strike/regular steps remain separate.
- Added bounded affected-controller scalar damage ordering with virtual counter-effect IDs, once-only replacement chaining and HTTP/SQLite restore. Canonical creature-only damage reduction remains distinct from prevention; automatic resolution/AI prefers free reduction before spending counters.
- Fixed source-controller creature-scoped combat prevention prohibitions, amount-based planeswalker combat prevention and shared noncombat deathtouch results. Full combat/protection/conversion ordering, regeneration and removal watchers remain open and explicitly reported.
- Verified 2,614 isolated backend tests (285 deprecation warnings), 274 focused checks, frontend lint/unit/build, 104 Chromium scenario assertions and 12 logical seat-balanced games repeated twice, with zero reported drift or timeouts. Reused installed dependencies; not a broad strength/balance or visual certification. Updated the plan, feature scope and Graphify, with evidence archived on RCHFiles. UI redesign remains deferred.

## 2026-10-02 - Named counter timestamps, stun and fixed-number scry

- Added durable per-kind counter timestamps and layer-six keyword contributions, including timestamp-aware proliferation valuation and existing cannot-have overrides. Counter placement does not change permanent incarnation; legacy snapshots remain readable.
- Routed turn-step and supported spell untaps through one stun-counter operation. Added bounded unconditional named-counter parsing and fixed-number private scry with atomic bottom/top ordering, snapshot continuation and both-seat existing choice controls.
- Removed name-only fabricated spell effects. Missing instant/sorcery Oracle text fails canonical admission rather than manufacturing damage, draws or counters.
- Verified 2,578 isolated backend tests (283 deprecation warnings), 341 focused checks, frontend lint/unit/build, 104 Chromium scenario assertions and 12 logical seat-balanced smoke games (24 repeatability executions) without reported drift, timeouts or classified anomalies. Installed dependencies were reused; browser assertions do not certify pointer ergonomics or visual quality.
- Shield replacements, Decayed/Exalted triggers, keyword variants, complete ability suppression and broader layers remain unfinished. UI redesign remains deferred. See `docs/testing/named-counters.md` for scope and evidence.

## 2026-10-02 - Local-only canonical match admission

- Removed synchronous card/image/ruling sync and database cache materialization from match hydration. Live games and diagnostics read canonical local bulk records, cache metadata and the shipped seed; structured missing-data errors point to explicit sync and readiness endpoints.
- Added bounded completeness queries and local readiness/source/art status in the existing deck data report. Unknown stats/faces and unresolved legacy split colors fail admission; recognized stale metadata is repaired in memory while preserving cached face artwork.
- Added front/back knowledge aliases without whole-corpus row loading, exact-name precedence and escaped wildcard matching. Preserved printed loyalty through canonical normalization, nullable cache migration and serialization; verified a live SQLite backup on RCHFiles before migration.
- Added explicit force refresh to single/bulk sync; existing art cannot short-circuit incomplete metadata. Sync remains synchronous and outage fallback requires a readiness recheck. No broad rules or AI certification is implied.
- Verified 2,526 backend tests in an isolated fresh checkout/database, 139 focused checks, frontend lint/unit/build, 103 Chromium scenario assertions and 12 logical seat-balanced smoke games (24 repeatability executions) with zero reported drift, timeouts or classified anomalies. Reused installed dependencies; no fresh installation or visual/pointer certification. Archived failures, source/provenance and final evidence on RCHFiles; alpha UI redesign remains deferred.

## 2026-10-02 - Proliferation and atomic multi-kind counter events

- Added non-targeting any-number proliferation selections for permanents and players, with every existing counter kind mandatory for selected recipients and authoritative poison/loyalty/lore storage.
- Added per-ability multi-kind replacement preparation, APNAP decisions, atomic placement, stale-recipient protection and snapshot/spell continuations. Canonical fixtures cover actual spell order, landfall/cast/combat triggers and proliferation watchers.
- Connected both-seat existing choice controls and shared public-counter AI policies. Counter-resource strategy, conditional paid instructions and proliferation-event replacements remain unfinished and explicitly scoped in the feature documentation.
- Isolated dropped-response browser recovery from cold Scryfall sync by priming its canonical fixture cache. Added response-phase diagnostics and an exclusive harness lock for fixed test ports. Production cold-cache match-start latency remains an explicit backend task.
- Verified 2,490 isolated backend tests, 183 focused counter/proliferation checks, frontend lint/unit/build, the full sequential Chromium harness and 12 logical seat-balanced replay smoke games without reported drift/timeout. Evidence, including superseded failures, is retained on RCHFiles; UI redesign and broader rules/AI completion remain open.

## 2026-10-01 - Shared opening-entry counter preparation

- Routed supported opening-hand battlefield actions through the shared counter-entry pipeline. Competing replacements retain the real card in hand until ordering completes; the commit checks its object incarnation and preserves mandatory follow-up hand exile.
- Allowed authoritative replacement choices during the opening-action window without prematurely starting the turn or applying state-based actions during a paused entry. Added both-seat ordering, prohibition, AI, snapshot and HTTP/SQLite restore regressions using canonical card fixtures.
- Added a persisted sequence to the shared zone-move helper so a hand/exile/hand round trip cannot reuse a stale opening-entry packet. Older snapshots default the sequence to zero; battlefield incarnation checks remain separate.
- Deferred UI redesign and archived the unfinished layout patch/browser evidence on RCHFiles; the published UI source is unchanged. Backend and broader release work remains open.
- Verified 2,453 isolated backend tests, 111 focused checks and the final-source full Chromium harness. Existing Python deprecation warnings remain; this does not certify arbitrary-card semantics or professional AI strength.

## 2026-10-01 - Compact history previews

- Limited saved matches and persisted diagnostic runs to three visible entries initially, with incremental Show more and Show fewer controls. Expanded lists have bounded scrolling so long histories do not dominate the page.
- Added isolated browser history fixtures and UI regressions for both lists; no saved matches or diagnostic reports are deleted by the preview controls.
- Verified frontend lint/unit/TypeScript build and the full Chromium suite, including preview expansion/collapse, saved-game recovery, simulator recovery, sideboarding and natural BO3 flows. Updated README/plan and Graphify; evidence is retained on RCHFiles.

## 2026-10-01 - Projected transformed entries and loyalty preservation

- Prepared supported exile-return-transformed operations against serialized back-face characteristics while the actual card remains exiled. Added snapshot continuation, incarnation rechecks, projected land-choice inspection and once-only exile/commit.
- Preserved physical loyalty counters through in-place transformations, including nonplaneswalker faces, rather than replacing them with printed starting loyalty. Retained front-face restoration metadata; faces without printed loyalty enter with zero and undergo the normal SBA check.
- Added twelve primitive/card-face regressions using canonical Scryfall Jace, Arlinn and Garruk fixtures, plus a seat-two UI/API projected-entry scenario. Verified 2,435 isolated backend tests, 68 focused tests, frontend lint/unit/build, full Chromium and eight seat-paired games across sixteen identical replay executions without timeout. This does not implement every Oracle clause on the fixture cards or establish expert AI. [Scope and remaining work](docs/testing/transformed-entry.md).

## 2026-10-01 - Owner-aware linked exile entries

- Routed supported linked-exile returns through shared pre-entry counter/chapter preparation and owner-aware land-entry choices. Mixed-owner batches remain off battlefield through all choices, survive snapshots, conserve exile incarnations and commit prepared counters before grouped entry events. Hand returns do not receive battlefield counters.
- Preserved recipient and completion controllers separately; paused SBA when a linked return creates a mechanic/replacement choice. Extended browser startup allowance from 15 to 60 seconds for empty-cache bootstrap.
- Added nine canonical/core-packet regressions and a real mixed-seat UI/API scenario. Verified 2,423 isolated backend tests, frontend lint/unit/build, the full Chromium suite and five seat-balanced replay games (ten repeated executions), without determinism failures. These replay decks are existing expansion archetype templates, not tournament lists or AI-strength evidence. Updated README/plan/scope and Graphify; completed evidence is on RCHFiles. [Remaining entry work](docs/testing/linked-entry-counters.md).

## 2026-10-01 - Shared entry routes and resolution staging

- Extended durable counter/chapter preparation to supported token batches, permanent-spell copies, graveyard returns, library selections and green-creature hand placement. Candidates/off-zone cards remain uncommitted during choices; creature returns now emit entry triggers. Non-cast entries no longer consume cast records or inherit the source effect's X/escape/life choices; spell copies retain copied X but were not cast.
- Added bounded commuting token-creation doublers, separate from entry counters and never applied to resolving permanent-spell copies. Staged common stack resolution until later effects and SBA finish; preserved original continuation ownership across affected-player choices.
- Added eighteen route checks and canonical fixtures. Updated seven earlier completion-time/token-count assertions; strengthened divided-damage coverage to inspect the first SBA boundary. Verified 2,414 isolated backend tests, 72 focused checks, frontend lint/unit/build, full Chromium including seat-two token batches, and sixteen deterministic replay executions without timeout. Updated docs/plan and Graphify; evidence is on RCHFiles. [Scope and remaining work](docs/testing/entry-routes.md).

## 2026-10-01 - Entry reduction ordering and counter commit

- Made compleated loyalty reductions orderable against supported scalar modifiers, using announced life-payment counts, affected-player choices, per-ability usage and durable off-battlefield continuations. Shared AI now compares operand-bearing reductions without card-name branches.
- Fixed prepared entry counters being retroactively blocked by newly active incoming global bans. Existing battlefield and applicable self-only bans still apply before entry; ordinary post-entry placements continue to check bans.
- Added fourteen cases and two canonical fixtures. Seven new cases fail against the preceding revision and pass after the fixes. Verified all 2,396 isolated backend tests, 173 focused checks, frontend lint/unit/build, full Chromium including seat-two ordering, and sixteen deterministic replay executions without timeout. Updated docs/plan and Graphify; evidence lives on RCHFiles. [Scope and limitations](docs/testing/entry-replacement-order.md).

## 2026-10-01 - Permanent-spell entry counters and Read Ahead

- Added resumable off-battlefield counter preparation for normal permanent spells: initial loyalty/lore, supported X/escape/one-shot creature counters and scalar replacement/prohibition choices. Entry commits once after choices complete. Human seats can choose Read Ahead chapters; its entry-turn exact-lore restriction follows current rules, including doubled-counter overshoot and later same-turn placements.
- Fixed modal planeswalker entry to use active-face loyalty without corrupting the stored original identity. Added 22 entry checks and two canonical card fixtures; expanded the leave-play face regression and honest phasing diagnostics. AI defaults to chapter one; deeper chapter planning and other entry routes remain unfinished.
- Verified 2,382 isolated backend tests, 146 focused counter checks, 44 entry/face checks, frontend lint/unit/build, full Chromium and sixteen deterministic seat-paired replay executions. Updated README/plan, refreshed Graphify, and retained evidence on RCHFiles. [Scope and limitations](docs/testing/permanent-spell-entry.md).

## 2026-10-01 - Saga counter events and trigger dependencies

- Connected supported turn-based and registered-effect lore to shared scalar replacements and crossed-threshold chapter events. Grouped symbols, chapter targeting/ordering, ward, staged/pending chapter lifetime and snapshot recovery use shared engine paths; copied or unrelated abilities no longer delay final sacrifice. Existing legacy chapter labels remain recognized with an explicit provenance limitation.
- Exposed lore in public card views and both battlefield lanes. Fixed generic temporary subtype buffs without a keyword suffix. Added a bounded card-name-free AI dependency policy for entirely friendly token/team-buff trigger groups, preserving human and unknown/mixed orders.
- Added 24 checks and two canonical fixtures. All 2,360 backend tests, 199 focused checks, frontend lint/unit/build and full Chromium pass. The new seat-two browser scenario verifies human chapter order, lore display, token buff and delayed sacrifice. Fixed the harness callback/type gaps exposed by those checks. [Scope and evidence](docs/testing/saga-counter-events.md). Entry and arbitrary chapter rules remain open.

## 2026-10-01 - Loyalty counter costs

- Positive loyalty costs now use shared scalar replacements, with cost-versus-effect provenance, resumable order choices and once-only activation. Announced abilities remain on the stack while cost choices are pending; ward triggers wait for completion. Negative costs remain counter removal.
- Added 12 canonical-fixture checks, including seat-two Ugin, staged ward and snapshot recovery. All 2,336 backend tests, 116 focused checks, frontend lint/unit/build and full existing Chromium harness pass. HTTP/SQLite recovery and a six-game seat-balanced replay also pass their bounded checks. See [scope and evidence](docs/testing/loyalty-counter-costs.md). Entry counters and broader counter costs remain open.

## 2026-10-01 — Damage counter replacement routing

- Routed supported infect/wither/toxic and noncombat damage-to-counter results through shared scalar replacements with source-controller attribution and effect-only provenance. Aggregated supported simultaneous combat contributions and retained queued choices, lifelink credit and SBA ordering through snapshot recovery. Moved amount-order preferences into the AI layer.
- Added 16 regressions and a seat-two browser scenario. Full backend (2,324), focused (176), frontend lint/build/unit, human/AI HTTP probes and full Chromium pass. Eight seat-paired games reproduce complete results/logs across sixteen executions without timeout or detected cost/target/action rejection. Fixed cross-suite simulator-fixture storage leakage before the successful browser rerun. [Scope and evidence](docs/testing/damage-counter-replacements.md). No printed card data or balance changed.
- Recovered disk capacity by removing 730 inactive scratch directories after preserving evidence; live databases/uncommitted work and active checkouts were protected. Archived diagnostics now live on RCHFiles with compatible local symlinks. Successful browser runs clean up their generated source copies and profiles; failures retain diagnostic paths. Backend recovered on `0.0.0.0:9999`.

## 2026-10-01 — Resumable counter-effect replacement order

- Added bounded printed doubling, halving and plus-one modifiers to registered permanent/player counter effects, with independent placer/recipient scope and per-ability usage. Affected players choose competing order; used abilities, amounts, stack resolution and sequence/batch continuations survive snapshots. Zero terminates the chain and supported prohibitions override placement. Separate land animation waits for placement.
- Connected shared AI amount-order evaluation and existing human controls. Nine canonical fixture rows cover controlled/global scope, typed/kind restrictions and pronoun variants; route-fidelity warnings remain because entry, damage and costs are not yet connected. No card rules, stats or deck balance were invented/changed.
- Final verification: 2,308 isolated backend tests, 257 focused checks, 44 new regressions, frontend lint/build/unit and full Chromium. A real seat-two Minthara order choice updates four experience counters and effective stats through UI/API; a separate HTTP autoplay probe resolves that trigger in one tick. Eight seat-paired smoke games repeat complete results/logs across sixteen executions without timeout or detected cast/target/cost rejection. Fixed an optional-field access exposed by 37 pre-existing AI test doubles before rerunning all gates. [Scope and evidence](docs/testing/counter-replacements.md).

## 2026-10-01 — Shared counter prohibitions

- Enforced bounded unconditional player, permanent-type and self counter bans through one application-code placement helper. Effects, infect/wither/toxic, supported damage-to-counter replacement, token/Incubate entries, supported spell entries, opening counters and Saga lore now use it. Existing counters, ordinary damage/lifelink, internal markers and separate animation instructions are preserved.
- Kept poison, Saga lore and planeswalker loyalty storage authoritative without confusing loyalty/lore counters on ordinary creatures. Blocked positive loyalty costs are rejected/filtered; unsupported conditional and turn-limited bans now warn explicitly. Scalar replacements, ordering, full entry/cost coverage and proliferation remain open; no printed card/deck data or balance was changed.
- Verified 2,264 isolated backend tests, 118 focused checks and 44 new regressions, plus frontend lint/build/unit and full Chromium (including natural AI and both human BO3 flows). Eight seat-paired smoke games repeat identical complete reported results/logs across sixteen executions without timeout or detected cast/target/cost rejection. Actual parent/current probes demonstrate five corrected placement paths under Solemnity. [Scope and evidence](docs/testing/counter-prohibitions.md).

## Unreleased

- Added persisted named player counters with poison compatibility, typed public views, both-seat display and shared gain effects/events. Supported Oracle cast/entry/death/end-step gain clauses produce stack triggers; departure facts survive source entry/restart and reset at the turn boundary. Added current-controller self/global/CDA P/T scaling and source-attributed traces, correcting the zero-counter flat anthem inference.
- Implemented ward X defined by named player counters at resolution, using the triggered ability's controller. Human controls show its computed cost; existing shared AI handles the payment without live-state mutation. Unsupported counter replacements and compound/dependent clauses still warn rather than gaining whole-card certification. See [scope and evidence](docs/testing/player-counters.md).
- Counter milestone verification: 2,220 isolated backend tests, 181 focused checks, frontend lint/build/unit and full Chromium pass, including real experience gain/effective stats and seat-two resolved-X HTTP/UI payment. Fourteen canonical rows and 68 new regressions cover the boundary, including actual casts/land plays, poison loss and labeled negative parser inputs. Eight seat-paired games repeat their reported results/logs across sixteen executions with no timeout or cast/target rejection; optional Spell Pierce nonpayment is normal. A read-only inventory records nineteen cached experience payloads, eight recognized gain clauses and fifteen known-gap payloads without claiming whole-card support.

- Fixed printed comma-separated ward keywords and supported named self-grants, including explicit tapped/untapped conditions. Existing stack/payment handling now receives these instances; loss of the grant after triggering does not delete the trigger. Preserved Oracle capitalization after a browser test caught a label regression. Unsupported-cost diagnostics now include inline/granted forms and faces. Eight canonical fixture rows and nineteen new regressions cover the bounded increment; see [scope](docs/testing/ward-forms.md).
- Ward-form verification: 2,152 isolated backend tests, 53 focused ward checks, frontend lint/build/unit and full Chromium pass. Eight seeded seat-paired games repeat identical results/logs across sixteen executions without timeout or cast/target rejection; one ordinary Spell Pierce optional payment fails normally. Dynamic/player-counter and arbitrary conditional semantics remain unfinished.

- Reduced shared planning-copy dispatch for flat card containers while preserving aliases, cycles and nested metadata isolation. Added bounded immutable static-instruction caches keyed by normalized Oracle text, not cards or effective game state. Expanded paired benchmark modes to isolate card-field copying and the combined hot paths without changing search limits.
- Fixed supported composed keyword prohibitions so "lose ... and can't have or gain ..." overrides newer grants. Canonical fixtures and independent parent probes cover all five Archetypes; control, zone, counter and attachment updates still recompute from current state. See [scope and evidence](docs/testing/ai-hotpaths.md).
- Hot-path verification: 2,133 independent standard backend tests, 259 focused checks, frontend lint/build/unit and full Chromium pass. Sixteen smoke executions reproduce eight actual-parent games/logs. A five-pair decision ablation measures 0.567 s versus 0.835 s with equal decisions/reasoning; timings are local samples. An optional timed-dump run's native crash is retained as unresolved despite passing standard and isolated/GDB reruns.

- Replaced upfront ward casting taxes with triggered stack objects and resumable mana, fixed/dynamic-power life, discard and qualified sacrifice payments. Covered actual activated/entry-triggered abilities and spell copies; Stifle can counter ward while the original remains on the stack. Human controls expose pay/decline and deliberate card selection for either seat. Shared AI projects immediate payment versus losing the referenced stack object without mutating the live match. See [scope and verification](docs/testing/ward-resolution.md).
- Ward verification: 2,096 independent final-source backend tests, 246 focused checks, frontend lint/build/unit and full Chromium pass. Eight seeded seat-paired games repeat across sixteen executions without timeout or cast/target rejection. Thirty canonical fixture rows and actual HTTP/UI controls cover the supported boundary, not universal rules or professional AI strength.

- Added supported global and target-aware Aura reductions to the shared legal-option/payment path. Payable Aura targets carry compatible cost-option IDs into human controls and AI actions; permitted exile and escape casts preserve source flags/additional costs. AI evaluates beneficial and harmful attachments with immediate heroic triggers. Shared enchant constraints prevent later ability words from widening or mis-owning cast targets; unknown restrictions receive preflight warnings. See [scope](docs/testing/aura-costs.md).
- Aura-cost verification: 2,062 isolated final-source backend tests, 178 focused checks, frontend lint/build/unit and complete final Chromium pass. Eight seeded seat-paired games repeat unchanged reported results/logs across sixteen executions without timeout or cast/target rejection. Parent probes reproduce missing discounted casts and incorrect enchant targets; the small matrix is not a strength or balance certificate.

- Added target-aware ordinary equip payment/legality for supported self-target, attached-target, global generic and effective-power reductions. Shared AI planning emits concrete improving equip targets and no longer crashes on list-valued target metadata. Attached base stats no longer affect unrelated creatures. Reattachment timestamps preserve durable battlefield identity, counters and pending ability guards. Reconfigure, fortify and full ability suppression now have explicit preflight warnings; this is not whole-card certification. See [scope](docs/testing/equip-context.md).
- Equipment-context verification: 2,020 isolated backend tests, 157 focused checks, frontend lint/build/unit and full Chromium pass, including a real seat-two target-discounted equip with no mana. Parent probes independently reproduce the base-stat, missing legal equip and AI crash defects.

- Added supported attached prefix/suffix conditions, false-versus-unknown otherwise selection, domain/target-color/attachment counts, subtype predicates and public graveyard/source-counter thresholds. Packaged the official offline creature-subtype registry; retained explicit warnings for unimplemented clauses on partially supported cards. See [scope](docs/testing/attached-predicates.md).
- Attached-predicate verification: 1,999 isolated backend tests, 102 focused checks, frontend lint/build/unit and the full final-code Chromium harness pass. Eight seeded seat-paired games repeat unchanged reported results/logs across sixteen executions with no timeout or cast/target rejection. These remain regression evidence, not professional-AI/balance certification.

- Replaced prefix-only attached bonus inference with supported full-clause battlefield and source-counter scaling, complete keyword lists and explicit unknown-clause diagnostics. Public views and both-seat UI expose warnings; canonical fixtures cover control changes, union counting, restoration, views and AI valuation. See [scope](docs/testing/attached-scaling.md).
- Attached-scaling verification: 1,974 isolated backend tests, 77 final focused checks, frontend lint/build/unit and full Chromium pass. Eight seeded seat-paired games repeat unchanged reported results/logs across sixteen executions with no timeout or cast/target rejection; these are regression checks, not expert-AI or balance certification.

- Added durable type-restricted mana provenance and shared ready-source/floated-pool eligibility. Casting, activation, cycling, equipment, snow and partial payment respect supported restrictions; unknown clauses are not unrestricted. Human pools display purposes, and typed runtime contracts validate quantities/snow overlap. AI's actual-cost reservation can preserve supported restricted sources for payable postcombat hand spells.
- Fixed checked equip target admission, changed ordinary equip to a respondable stack ability with resolution/incarnation revalidation, and connected supported attached fixed buffs/keywords to continuous characteristics and layer traces. Canonical fixtures cover counters/removal/control changes, source departure and attachment/controller separation. See [scope and acceptance](docs/testing/restricted-mana-equipment.md).
- Verification: 1,943 isolated backend tests, 196 focused checks, frontend lint/build/unit and full final-code Chromium pass, including real seat-two restricted-mana/equipment UI/API flow. Initial fixture/protocol errors were corrected before passing gates; broad source restrictions, equipment variants, layer fidelity and expert strategy remain open.

- Fixed supported scaling nonland mana quantities in the shared payment/resource evaluator: own/all battlefield selectors, source counters and effective power now determine actual output instead of the number of printed symbols. Zero quantities do not mint mana; unrecognized quantities are not approximated as one. Real manual/automatic payment, views and AI reservation share the result across styles. See [scope and evidence](docs/testing/variable-mana.md).
- Added canonical offline basic-land cache fixtures for browser sideboarding. A real HTTP swap now makes zero network-sync calls, while parent setup attempted Forest/Island; production hydration is unchanged. Initial browser timeout and other historical diagnostic failures are not declared universally fixed.
- Variable-mana verification: 1,897 isolated backend tests, frontend lint/build/unit and the complete final-code Chromium rerun pass. Eight seed/seat-paired games repeat identical reported results/logs across sixteen executions without timeout or rejected cast/target; two changed Tribal/Burn traces exercise real two-to-seven-green Archdruid payments. Canonical fixture decisions improve specific cases, not proof of expert strategy or balance.

- Added shared postcombat mana reservation for unblocked attacks, using actual hand costs, readiness, color alternatives and taxes instead of attacking every source. Preserved vigilance, redundant attackers and the existing lethal-pressure heuristic; late-game progress cannot undo reservation. Forty canonical-fixture regressions also fix qualified continuous subjects, noncreature protection and activated/triggered text incorrectly acting as static layers. See [bounded scope](docs/testing/ai-postcombat-mana.md).
- Verification: 1,875 isolated backend tests, frontend lint/build/unit and full Chromium gameplay/recovery/simulator/BO3 checks pass. Six continuous regressions fail on the parent revision and pass here. Eight seed/seat-paired games repeat with identical reported game traces across sixteen executions, without timeout or rejected cast/target. One optional Spell Pierce payment fails normally; all eight traces match the parent smoke. Timing/internal-state completeness and expert-play claims are excluded; broader rules, strategy and intermittent diagnostic investigations remain open.

- Mana-resource verification: 1,835 isolated backend tests, frontend lint/build/unit and the full final-code Chromium harness pass. Eight seed/seat-paired games repeat with identical complete results across sixteen executions, zero timeout and zero logged cost/target rejection. Three traces differ from the preceding milestone, not proof of optimality. Both LAN services respond; broad resource planning and previously noted intermittent diagnostics remain open.

- Added shared printed tap-only mana-capacity analysis separately from payment availability. AI board/sacrifice scoring now retains supported creature and artifact resources; creature cast/threat scoring shares the public land-count heuristic. Flexible colors use maximum output rather than summing alternatives. Paid/additional-cost, restricted and non-untapping sources are excluded from this bonus. Thirteen canonical cached fixtures cover multiple colors and output sizes without modifying built-in decks. See [scope](docs/testing/ai-mana-resources.md).

- Recurring-payoff verification: 1,811 isolated backend tests, frontend lint/build/unit and the full Chromium rerun pass. Eight seed/seat-paired games have identical complete results across sixteen executions without timeout or logged cost/target rejection. The initial browser sideboard operation timed out and passed unchanged on retry; its cause remains unverified. This bounded evidence does not certify AI strength, balance or arbitrary mechanics.

- Shared recurring drain/draw/token payoff valuation now reaches creature board, cast and threat scoring as well as sacrifice retention. Supported death-trigger eligibility follows the engine's public-board matching and pure replacement query. It does not borrow spent entry rewards or mistake a draw condition for card advantage.
- AI holds supported fixed-cost mass-destruction casts that an unanswered engine projection proves would lose to an opposing death payoff. Canonical Meathook Massacre/Naturalize/Damnation fixtures verify remove-payoff-then-wipe sequencing across eight styles, full snapshot purity and resume; unresolved opposing choices remain unknown. No card definitions or built-in decks were invented or changed. See [scope and validation](docs/testing/ai-recurring-payoffs.md).

- Oracle-grounded AI milestone: removed name-fragment role bonuses across ranking, rollout, opening-hand, closure, X timing, burn estimates and threat/board valuation. Actual costs drive counter color demand; nonblue typed counters are recognized. Fixed player-damage clauses replace the old card-name table, including Lightning Strike and Boros Charm's printed four-damage mode.
- Deck identity now uses role density, curve and typed tribal support, not named packages/creature guesses. Flat hydrated and nested face metadata share analysis, land-only faces are excluded from acceleration packages, and missing type data produces an explicit zero-confidence fallback. Names remain for display, canonical lookup, stable ties and recorded historical priors. Twelve real canonical fixtures were added; no invented gameplay cards or deck edits.
- Oracle-AI verification: 1,787 isolated backend tests and frontend lint/build/unit checks pass. Eight seat-paired seeded games repeat with identical complete results across sixteen executions, no timeout and no logged cost/target rejection. Final browser evidence is recorded in [the scope report](docs/testing/ai-oracle-semantics.md). Early loop/test-hydration and face/classification gaps were fixed before final gates. Classification/strategy remains heuristic; this is not optimal-play or balance evidence, and the diagnostic interpreter crash remains open.
- Planning-copy follow-up: exact card instances reuse immutable scalars while every mutable field remains independently deep-copied; shared aliases, cycles, dynamic attributes, faces and counters are retained. Five captured slow Control/Ramp decisions show 17.3–34.2% shorter paired medians with identical full decisions and unchanged source states, without reducing search limits. Local timing does not establish a worst-case or HTTP-response guarantee.
- Added offline `profile_ai_match.py` percentile/target telemetry without card identities or hands, and copy-only benchmark ablation with opponent-archetype provenance. Target exceedance is diagnostic, never a gameplay cutoff. Eight seeded archetype results and two profiled Control/Ramp hashes retain complete baseline equality. Verification: 1,765 isolated backend tests, frontend lint/build/unit and full Chromium pass. Graphify data/HTML are refreshed; the independent diagnostic interpreter crash remains unresolved. See [scope and evidence](docs/testing/ai-card-copy-latency.md).
- AI performance/replay milestone: immutable root announced-stack projections are reused within one decision; agent planning clones retain gameplay/RNG/choices but omit historical logs. A seven-iteration dense removal ablation reduced median time from 0.249900s to 0.176077s with identical full decisions/reasoning and unchanged authoritative snapshots. This is local fixture performance, not broader AI-strength evidence.
- Validation exposed a pre-existing seeded token/block tie drift from random gameplay UUIDs. Tokens, stack/copy objects and triggered/delayed abilities now share a persisted per-game ID sequence independent of shuffle RNG. Replay normalization retains those IDs instead of hiding target/block identity changes. Legacy random-ID snapshots remain readable but cannot reconstruct old random tie order.
- Verification: 1,757 isolated backend tests, frontend lint/build/unit and full Chromium pass. Eight seed/seat-paired BO1 games have identical complete optimized/ablation traces and no timeout or logged cost/target rejection; three Ramp/Tokens repeats match. Initial test-collection/copy-fixture and browser-launch-path errors were corrected before final passing gates. The separate diagnostic interpreter crash remains open. See [evidence and limitations](docs/testing/ai-projection-performance.md).
- Conditional-entry verification: 1,737 isolated backend tests, frontend lint/build/unit contracts, full Chromium and a six-series/13-game seat-balanced replay pass. Canonical fixtures and names-only cache/HTTP tests cover the feature; the matrix is only a regression smoke. An instrumented run segfaulted during a timeout stack dump; two fresh uninstrumented suites passed, and its root cause remains open. Initial counter-reset ordering and raw bulk-tap rejection gaps were fixed and retested. Graphify now refreshes both graph data and the interactive HTML.
- Conditional opening-hand follow-up: printed nonstarting-player entry with a named counter and mandatory hand exile now has resumable human/AI choices, including the empty-follow-up-hand boundary (the exile instruction is not a cost). State-aware counter-dependent land outputs now drive payment, manual validation/tapping, AI battlefield estimates and public views. UI piles separate differing outputs and offer color choices; duplicate dead mana estimators were removed. Other conditions/entry choices/reveal/mulligan-time actions and deeper entry/exile strategy remain open. See [coverage](docs/testing/opening-hand-actions.md).
- Opening-hand verification: 1,725 isolated backend tests pass; frontend lint/build/unit contracts and the full Chromium harness pass. The final cache test also asserts zero sync attempts. A six-series/13-game seat-balanced BO3 replay completes with no reported timeout/anomaly/drift. The full suite takes about 4m25s and emits existing deprecation warnings; a timeout diagnostic identified CPU-heavy Control/Ramp simulation that ultimately passed. These are bounded regression checks, not broad pregame, balance or expert-AI certification.
- Opening-hand milestone: supported unconditional printed battlefield-entry permissions now use a durable starting-player-first queue after all keeps. Human and AI choices can enter multiple cards or decline, retain normal static timestamps/events, and survive HTTP/SQLite restoration. Cached canonical data and second-seat browser controls are covered. Conditional costs/counters, entry choices, reveal and mulligan-time abilities, broader pregame trigger certification and strategic evaluation of symmetric effects remain open. See [scope and evidence](docs/testing/opening-hand-actions.md).
- Mandatory ordered bottom choices now follow every mulligan redraw before the next declaration round. Shared queued choices persist both players through snapshots, AI resolves them before evaluating the remaining hand, Keep cannot bottom twice, and legacy unresolved selections are retained. UI choice types/count validation, AI-owned choice stepping and authoritative pregame autoplay fix integration gaps. Opening-hand/mulligan-time effects remain open.
- Bottom-choice verification: 1,708 isolated backend tests and frontend lint/build/contracts pass; browser human BO3s exercise the new choice, and a six-series/13-game seat-balanced replay reports no timeout/anomaly/drift. An initial typecheck and browser attempt found integration gaps that were fixed and retested; this remains bounded pregame/playability evidence, not expert-AI certification.
- Mulligan declarations now follow starting-player order across live matches, batch simulation and diagnostics. Shared durable round state waits for all declarations before paired redraws, skips players who kept, rejects out-of-order/repeated actions and survives snapshot/HTTP restoration. UI guidance reflects the acting seat. Mandatory bottom-selection timing still uses legacy Keep behavior and is explicitly next work, not claimed fixed.
- Declaration-round verification: 1,699 isolated backend tests, frontend lint/build/unit, full Chromium harness and a six-series/15-game seat-balanced BO3 replay pass with zero reported timeout/anomaly/drift. This does not certify full mulligan semantics or expert AI.
- Live and diagnostic series share a storage-independent chooser/seed policy. Replay gives the prior loser the next starting-player choice (currently always choosing play), retains the chooser after a draw, records per-game starters, and stops after an unresolved timeout rather than inventing a next game. Real-engine regressions verify Player B's first-turn draw skip; sideboarding parity, strategic play/draw choice and simultaneous mulligan rounds remain open.
- Series-policy verification: 1,693 isolated backend tests, frontend lint/build/unit and full Chromium harness pass. A six-series/15-game seat-balanced Aggro/Control/Tempo BO3 smoke reports no timeout/anomaly/drift and records four Player B starts. Draw-chooser and timeout boundaries have focused fixtures; the smoke does not establish strategic quality.
- Replay matrices now run paired seeds in both seat orders by default, map outcomes back to consistent deck identities, retain anomalous traces and per-game seeds, exclude unresolved series from completed win rates, and compare complete repeated results. `--single-seat` retains legacy smoke mode; nonpositive workloads are rejected. This is regression accounting, not statistical balance or expert-AI certification.
- Replay-protocol verification: 1,685 isolated backend tests, frontend lint/build/unit, full Chromium harness, final-code two-seat BO1 smoke and a six-series/13-game seat-balanced BO3 smoke pass with zero reported replay anomalies. The plan now correctly marks the already-implemented single-process match-lock/revision coordinator complete without implying distributed locking or network authorization. These small archetype-template samples do not establish strategic quality or balance.
- AI can now commit supported unanswered winning friendly-target destruction lines using actual costs, triggers, replacements and stack resolution. Own choices use a separate configured AI instance; undeclared opposing choices and hidden-zone changes remain unknown. The ordinary conservative guard and human legality are preserved. Sacrifice retention now values recurring payoff clauses separately from spent entry rewards. Canonical spell, activation-cost and loyalty fixtures cover the [bounded behavior](docs/testing/ai-self-removal.md).
- Self-removal verification: 1,675 isolated backend tests, frontend lint/build/unit, full Chromium harness and a three-game replay with zero determinism failures or drift labels. Eight seat-swapped traced games complete without timeout or logged cast-time target/cost rejection but do not exercise the new self-removal line; feature evidence comes from canonical fixtures and a full-state baseline comparison, not matchup win rates.

- AI now conserves supported pure destruction against indestructible and friendly permanents, including selected single modes, activated sacrifice abilities and loyalty abilities. Materialized modes validate remaining target candidates instead of stale available-mode metadata. Human targeting is unchanged; canonical Slice in Twain still draws after a legal indestructible target survives. See [fixtures, comparison and limits](docs/testing/ai-destruction-targets.md).
- Destruction-target verification: 1,650 isolated backend tests, frontend lint/build/unit, full Chromium harness and a three-game replay with zero determinism failures or drift labels. Eight seat-swapped Midrange/Drain and Tokens/Ramp games finish without timeout or logged cast-time target/cost rejection; complex metric gaps remain explicitly unavailable. These smoke samples are not a balance or expert-AI certification.

- AI now conserves simple removal against permanents already covered by announced stack effects, redirects to uncovered threats and retains backup against known counter/pump responses. Shared rules fixes make targeted destruction respect indestructible and interpret pure signed numeric targeted P/T changes until end of turn. Decision traces now include saved stack-source characteristics and announced targets; a sixth metric detects redundant removal without converting legacy or unresolved-choice evidence to zero. Baseline Dimir/Tempo seed 711 reproduces three redundant casts; updated play records zero. See [scope, evidence and remaining limits](docs/testing/ai-pending-removal.md).
- Verification for pending-removal awareness: 1,629 isolated backend tests, frontend lint/build/unit, full Chromium harness, eight seat-swapped traced matches with no timeout or cast-time target/cost rejection, and a three-game replay with zero determinism failures or drift labels. The original baseline game still wins despite its resource waste; these results do not establish balance or expert-level play.

- AI counter targeting now prefers counterable opposing stack objects and conserves supported pure counters against protected spells, including tax counters and preselected targets. Modal scoring can choose useful non-counter effects; compound counter/draw actions and legal ability targets remain available. Seventeen canonical regressions and four full-state before/after decision fixtures cover this [bounded repair](docs/testing/ai-counterability.md). Verification: 1,610 isolated backend tests, frontend lint/build/unit, full Chromium harness, three deterministic replay games with zero drift, and eight seat-swapped verbose games without timeout or cast-time target/cost rejection. Manual review found redundant removal at Dimir/Tempo seed 711 despite zero quality-proxy warnings; that next fix is recorded in the plan. This is not a balance or expert-play certificate. Protection-removal planning and arbitrary secondary-effect valuation remain open.
- Counterability now distinguishes intrinsic spell protection from standalone battlefield protection. Supported color/type scopes are checked at resolution for ordinary/taxed counters, using a copy's saved characteristics and controller. Source spell text no longer incorrectly protects activated abilities from Stifle, and Destiny Spinner's battlefield-only protection no longer protects Spinner while it is being cast. Canonical fixtures cover legal targeting, source removal, copies, snapshots and human Stifle controls. Verification: 1,593 isolated backend tests, frontend lint/build/unit, full Chromium harness, and three seeded BO3 replay games with zero determinism failures, drift or anomaly labels. Conditional/granted protection and ability-removal layers remain open; see [scope and acceptance](docs/testing/counterability-scope.md).
- Surviving spell copies now share a saved-characteristics view for legal target generation, ordinary/taxed counter resolution, stack resolution and AI threat scoring. Countering an original Adventure or modal spell no longer makes its surviving copy inherit the restored physical card's type or mana cost. General exact/minimum mana-value target filters support the tested Spell Snare and Disdainful Stroke wording; snapshot, immutable-card, AI and human target-control regressions use canonical card fixtures. Verification: 1,568 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a seeded BO3 replay with zero determinism failures or drift labels. Conditional counter clauses and Fuse remain open.
- Aftermath halves can now be cast from the graveyard with their own printed cost and timing. Shared stack-departure handling exiles them on resolution, countering or failed targets, preserves pending draw choices and snapshots, and restores combined split identity. Copies leave the physical original alone. Countered ordinary split halves now also restore their combined graveyard identity. Canonical Spring // Mind and Refuse // Cooperate fixtures cover the rules boundary; arbitrary Aftermath effects still require verification.
- Split cards now expose combined off-stack colors and the selected half's colors on the stack. Scryfall face normalization preserves missing color metadata rather than converting it to colorless, and live hydration refreshes affected legacy split cache rows from canonical data. Ice/Protection from red and cache-idempotency regressions cover this correction.
- Verification for this increment: 1,558 isolated backend tests, frontend lint/build/unit, full Chromium action/recovery/BO3 harness, and three seeded replay games with zero determinism failures or drift labels. This verifies the covered rules and flows, not arbitrary Oracle effects or matchup strength.

- Split cards with canonical face data now cast one selected half with its own timing, cost, targets and stack characteristics, then restore their combined identity off-stack. Fire // Ice and Incubation // Incongruity fixtures cover the bounded engine, AI, UI and cache-backfill paths. Fire's printed one-or-two-target allocation is capped at two. Fuse and Aftermath remain unsupported and are now flagged by simulator preflight; an Aftermath half is blocked outside the graveyard. Other split effects still require Oracle verification.

- Clause-derived spell copies can now offer a separate, snapshot-persistent retarget choice for each independently targeted effect. A canonical Meager Meal copy can redirect its creature and player targets without changing the original; partial target failure still resolves only legal effects, and the copy grants no Adventure creature-cast permission. AI uses the same choice path and prefers friendly recipients for beneficial clauses. Verification: 1,528 isolated backend tests, frontend lint/build/unit, full Chromium harness, and three-game BO3 replay with zero determinism failures or anomaly labels. Ambiguous compound clauses and copy-zone presentation remain open.

- Simple clause-derived multi-target spell effects now recheck their announced targets independently at resolution. The Scryfall-backed Gollum / Meager Meal Adventure fixture covers all-target failure to graveyard, partial resolution to exile with permission, player hexproof, optional creature-target omission, snapshot restore, and a human UI/API dual-target cast. The shared life-gain parser now recognizes "target player gains" as well as "gain". Verification: 1,524 isolated backend tests, frontend lint/build/unit, full Chromium browser harness, and a three-game BO3 replay with zero determinism failures or anomaly labels. Compound two-target effects and other Adventure grammars remain open.

- Counterspell conservation now screens a sole low-threat creature spell and avoids casting a redundant second counter while the AI's first counter is on top of the stack. Distinct uncovered stack spells remain targetable; it can still counter a high-impact planeswalker or respond when the opponent counters its pending counter. A seeded Blue Control/Ramp trace changed from countering Arboreal Grazer and double-countering Go for the Throat to distinct counter targets. Verification: 1,519 isolated backend tests, frontend lint/build/unit, a three-game BO3 replay with zero drift or anomaly labels, and a full Chromium rerun. The first Chromium attempt intermittently lost a fetch in match-start recovery; the unchanged-code rerun passed. This is a bounded tactical fix, not evidence of general control mastery.

- Variable-X all-creature debuffs now choose the cheapest X with worthwhile creature impact instead of spending all available mana by default. AI keeps them in hand when affordable X cannot remove an opposing creature, including through anti-stall conversion. Regression fixtures cover an opposing spell tax, a six-toughness threat, a positive cast at X=6, and repeated pass decisions. Verification: 1,517 isolated backend tests, frontend lint/build/unit, full Chromium harness, a three-game BO3 determinism replay with zero drift, and a seeded Blue Control/Ramp trace that delayed the cast until an opposing creature was present. This does not imply matchup balance or expert play.

- Added an offline, idempotent `--backfill-tags` mode to the existing bulk-knowledge CLI. It derives tactical tags from stored canonical payloads, preserves rulings/provenance/scores, skips missing payloads, uses its own summary path, and rejects nonexistent database paths. Verification: 1,515 isolated backend tests, frontend lint/build/unit, a full-database rehearsal, and a backed-up live migration of all 38,690 rows. The live repeat updated zero rows; all 87 verified-rulings flags, 112 cached gameplay cards, and SQLite integrity checks were preserved.

- AI spell-role tags now come from a shared Oracle/type derivation rather than card-name guesses. Canonical live and bulk ingestion store the same deterministic tags, including separate card-face tags; verified cached rows missing tags are backfilled without another network request. Real Bolt, Cultivate, Llanowar Elves, Nissa, Memory Deluge, Supreme Verdict and Brutal Cathar regressions cover the bounded behavior. Verification: 1,513 isolated backend tests, frontend lint/build/unit, full Chromium harness, two seeded Blue Control/Ramp games with no timeout or invalid-action log, and a three-game deterministic BO3 with no drift. An isolated import of the local Scryfall bulk file populated tags for 38,690 rows and a second import left all 38,690 unchanged; bulk rulings remain pending. Persisted tactical score consumption and measured strategic improvement remain open.

- Library searches that put multiple selected cards directly onto the battlefield now collect their entry events after all selected cards enter. Grouped entry triggers fire once while per-entrant triggers still fire for each qualifying card; split battlefield/hand searches retain their single-entry behavior. A focused search regression reproduces the old duplicate trigger and passes after the fix. Verification: 1,510 isolated backend tests, frontend lint/build/unit, the full Chromium harness including the library-search UI path and natural BO3 flows, and a seeded two-game replay with no timeout or determinism drift passed.

- Batched simultaneous battlefield entries for multi-token effects and supported topdeck creature/permanent placement. Grouped "one or more" triggers fire once; per-entrant triggers still fire individually. Human attacking-token defender choices now finish before the token group enters. Focused tests cover token placement, both topdeck handlers, separate defenders and snapshot resume. Verification: 1,509 isolated backend tests, frontend lint/build/unit, full Chromium harness including natural AI/human BO3 flows, and a seeded two-game replay with no timeout or determinism drift passed.

- Supported once-per-turn grouped creature-subtype entry triggers and subtype-filtered temporary team buffs without card-name exceptions. Irrelevant entries no longer consume trigger allowances; created creature tokens retain their subtype lines, and static subtype anthems use the same singularization. Elvish Warmaster and Zombie fixtures cover controller filtering, countered triggers, snapshots, new battlefield incarnations, activation payment and later entrants. Verification: 1,505 isolated backend tests, frontend lint/build/unit, full Chromium harness, six seeded Tribal games without timeout or logged rule errors, and a two-game deterministic replay without drift. An intermediate full run exposed an overbroad parser match against all-creature buffs; the guard and rerun pass.

- Added a live-route regression for Wedding Announcement from the bundled canonical corpus: names-only match start, legal attack action, SQLite restore, end-step priority passes, and serialized invitation counter/draw result. A fresh isolated backend suite passes 1,497 tests; frontend and browser checks were already green for the unchanged UI.

- Supported counter/attack-count/token-or-draw/transform end-step clauses through reusable effect handlers. Declared attackers are tracked per turn through snapshots; creatures leaving combat still count, while creatures put onto the battlefield attacking do not. Wedding Announcement regressions cover trigger order, three-counter transform, re-entry and turn reset. Verification: 1,496 isolated backend tests, frontend lint/build/unit, full Chromium harness, one seeded White Weenie/Blue Control game with a Wedding draw, and a two-game replay with no drift. Other conditional end-step patterns remain unverified.

- Tapped-and-attacking token creation now offers a resolution-time choice between the defending player and their planeswalkers. Multiple tokens can choose different defenders; invalid or stale selections are rejected, AI handles the choice, and it survives snapshot restore. A real Adeline browser fixture covers the human control. Verification: 1,490 isolated backend tests, frontend lint/build/unit, full browser harness, one seeded White Weenie/Blue Control AI game, and a two-game replay with no determinism drift.

- The browser lost-response recovery fixture now warms its action URL's CORS preflight with a rejected, non-mutating request before response interception. This avoids an intermittent preflight-only failure in the current Chromium harness; the full rerun passed.

- Attack-group triggers no longer duplicate for each declared attacker. Adeline now has creature-count power and creates one Human token tapped and attacking, which joins combat without generating a new declared-attack event. Verification: 1,485 isolated backend tests, frontend lint/build/unit, full browser harness and seeded BO3 replay. Planeswalker attack-target selection for that token remains open.

- Browser recovery fixtures now resume intercepted responses with `Fetch.continueResponse`. The previous command prevented the preflight from reaching its action POST under the current Chromium build; the corrected full browser harness passes.

- Training now triggers once when a creature attacks alongside a greater-power creature, then adds its counter on stack resolution without rechecking the companion's power. Snapshot and leave/re-entry regressions use Hopeful Initiate. Verification: 1,482 isolated backend tests, frontend lint/build/unit, full browser harness and a seeded two-game replay with no determinism drift. Broader attack-trigger interpretation remains open.

- Combat legality now applies Brazen Borrower's flying-only block restriction and Topiary Stomper's seven-land attack/block threshold through reusable text clauses. Strict player actions, AI's shared blocker filter, and snapshot behavior use the same legality path. Other conditional combat wordings remain open.

- Batch simulation starts now accept an `Idempotency-Key` (32 lowercase hex characters) and return the existing job for a retry with identical parameters, including after a restart. The UI retries once after an ambiguous response and recovers its pending request on refresh. A worker-start failure records a failed job rather than an indefinite queued row. HTTP, SQLite and browser regressions cover conflict detection and a server-accepted start with two lost replies.

- Testing Simulator now remembers the active background job ID and resumes polling after page refresh or tab remount. A browser regression checks that restore does not create a duplicate job and that cancellation clears the saved ID. The subsequent idempotent-start change above also recovers an accepted start whose response was lost.

- Added cooperative cancellation for background Testing Simulator jobs. The UI now requests worker cancellation rather than merely stopping polling; canceled jobs retain progress without reporting incomplete win-rate metrics. Backend worker/slot tests, a response-contract test, and a browser UI fixture cover the behavior. Queueing, durable retention and multiworker execution remain out of scope.

- Speculative AI search and ranking rollouts now request strict engine rejection for cloned actions. A real unpayable Counterspell regression previously scored a no-op as a valid line and now rejects it. Verification: 1,467 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded two-game replay with no reported drift. Other silent no-op paths remain to be audited.

- Bounded AI search and ranking rollouts now shortlist replies with shallow move scores instead of taking the first six/eight lexically sorted moves. Regressions cover a threatening cast after many ability moves and prove shallow ranking avoids nested rollouts. Verification: 1,466 isolated backend tests, frontend lint/build/unit, full solo Chromium harness, and seeded two-game replay with no reported drift. A paired Blue Control/Ramp API BO3 took 139 seconds on this revision versus 135 seconds on the prior revision; this single run is not a throughput guarantee. Ranking remains heuristic and capped.

- AI ranking rollouts now materialize targeted candidate and opponent-reply actions before simulation. Deterministic regressions show previously skipped target-dependent moves contribute to both candidate value and opponent-response penalty. Verification: 1,463 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay with no reported drift. The eight-reply cap and hidden-information model remain open.

- Corrected bounded AI search to choose the opponent reply that is worst for us, rather than the best, and to materialize targets on simulated replies. Deterministic best/worst and targeted-reply regressions pass. Verification: 1,461 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay with no reported drift. Beam coverage and opponent policy remain heuristic.

- Supported sacrifice-triggered "a player sacrifices another permanent, put a +1/+1 counter on each creature you control" with a reusable team-counter handler. Real Mazirek fixtures cover either player sacrificing, self-exclusion, simultaneous departures, snapshot restore and resolution-time board changes. Verification: 1,458 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay with no reported drift. Broader team-counter clauses remain open.

- Supported sacrifice-triggered "target opponent loses N life and you gain M life" now applies both changes through one targeted sequence. Human choices offer only legal opponents; hexproof/shroud is checked at stack entry and resolution, so an illegal target stops both changes. Real Popular Egotist fixtures cover ordinary and self-sacrifice, snapshot recovery and target-loss timing. Verification: 1,453 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and a seeded BO3 replay with no reported drift. Broader sacrifice clauses remain open.

- Sacrifice triggers now look back at departing watchers' last battlefield state, including a source sacrificed itself or alongside another permanent. Mayhem Devil triggers after graveyard movement or Rest in Peace replacement exile, retains a human target choice through snapshot restore, and sees each simultaneous Annihilator sacrifice. Verification: 1,448 isolated backend tests, frontend lint/build/unit, full solo Chromium harness and seeded BO3 replay without reported drift. A concurrent browser/full-suite run timed out during match creation recovery; the solo rerun passed. Wider sacrifice wording, replacement interactions and load behavior remain open.

- Simultaneously dying creatures' triggered abilities now use the shared last-known-source scan, so a departing watcher sees other eligible deaths from the same wipe or lethal state-based batch without doubling its own trigger. "Another creature" and "another nontoken creature" wording exclude self, and the latter excludes tokens; APNAP ordering and graveyard-exile replacement remain intact. Real Blood Artist, Pitiless Plunderer, Harvester of Souls and Rest in Peace regressions cover two-watcher wipes, state-based lethality, snapshot restore and actual destinations. Verification: 1,444 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded BO3 replay without reported drift. Broader leave/sacrifice look-back and replacement interactions remain open.

- Supported death triggers naming their own source in "[name] or another creature dies" now fire for the source or a separate creature. Printed "target player loses N life and you gain M life" resolves as one targeted sequence: humans choose a legal player, AI prefers a legal opponent, hexproof/shroud filters options, and an illegal target at resolution prevents both life changes. Blood Artist, Llanowar Elves and Leyline of Sanctity regressions cover these boundaries. Verification: 1,437 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded BO3 replay without reported drift. Simultaneous departing watchers and other named-reference wording remain open.

- Activated sacrifice costs now produce staged leave, sacrifice and actual-graveyard death events instead of sacrifice events alone. The resulting triggers go above the paid-for ability; replacement exile suppresses death triggers but retains sacrifice triggers. Supported creature-death drain wording now makes the opponent lose life as well as granting life. Real Fanatical Firebrand, Mayhem Devil, Bastion of Remembrance and Rest in Peace fixtures cover stack order, human ordering, life totals and snapshot restore. Verification: 1,432 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded BO3 replay without reported drift. Broader cost-selection and replacement interactions remain open.

- Departed permanent damage abilities now carry a serialized last-battlefield snapshot of effective keywords, colors and controller. Damage and single-target activated-ability rechecks use that snapshot for lifelink, infect, wither and protection even when the source card returns as a different object; live sources still use their current characteristics. Self-sacrifice costs capture the source before removal. Real Prodigal Pyromancer, Fanatical Firebrand and Crypt Rats regressions cover departure, return, snapshot restore and batch damage. Verification: 1,429 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded BO3 replay with zero determinism failures or drift labels. Broader source-dependent replacement/prevention effects and sacrifice-trigger ordering remain open.

- Divided-target damage now uses the shared simultaneous-damage batch path rather than resolving each target as a separate sourced-less hit. Original allocations stay fixed when targets become illegal; source attribution, post-prevention lifelink, deferred lethal checks and snapshot-resumable human replacement choices apply to each share. Real Pyrotechnics fixtures cover these boundaries. Verification: 1,421 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded BO3 replay with zero determinism failures or drift labels. Broader damage-event ordering and source last-known information remain open.

- Noncombat damage now credits a lifelink source for damage actually dealt after prevention. Crypt Rats-style all-creature/player damage aggregates one life-gain event across recipients, preserving the total through human damage-replacement choices and snapshots; life-gain replacements resolve before lethal state-based actions. Real-card regression fixtures cover prevention, one gain trigger, self-lethal survival and gain-replacement continuation. Verification: 1,418 isolated backend tests, frontend lint/build/unit, full Chromium harness, and one seeded BO3 replay with zero determinism failures or drift labels. Distributed-damage and arbitrary all-recipient effects remain uncertified.

- Printed "spend only [color] mana on X" activated costs now constrain the X portion in the shared legality and payment planner; fixed generic mana remains unrestricted. Crypt Rats' X damage to each creature and each player is applied as one recipient snapshot before lethal state-based actions, with resumable human damage-replacement choices. AI materialization uses the payable color and rejects self-lethal or nonpositive nonlethal activations. Engine, HTTP, snapshot, protection and mana-source regressions cover this bounded wording. Verification: 1,413 isolated backend tests, frontend lint/build/unit, the full Chromium harness, and a three-match/six-game seeded replay with no timeout or determinism failure. Other multi-recipient clauses, noncombat lifelink interactions and arbitrary replacement combinations remain uncertified.

- Unrestricted activated {X} costs now use one announced value for legality, mana payment, stack payload and UI input instead of being globally disabled. Supported linked-exile copy wording chooses an eligible exiled creature at resolution and copies its front-face printed characteristics until the source leaves; stacked activations, stale links, snapshot restore and AI X selection have regressions using real Valki/Elvish Mystic data. A production-control browser scenario covers human X input and copy choice. Printed color-restricted X payments are withheld and preflight-flagged rather than paid illegally, as checked with Crypt Rats. Unsupported activated effects are not offered or charged, and self +1/+1 counter clauses resolve instead of being mistaken for no-ops; legal-move preflight does not append match logs. Verification: 1,406 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift. Full copy-layer fidelity remains uncertified.

- Linked exile now retains the previous zone, allowing supported reveal-and-exile-from-hand ETB wording to return the chosen creature card to its owner's hand rather than the battlefield. The shared revealed-hand chooser handles the human/AI selection; source-leaves-before-resolution still reveals but does not exile. Real Valki front-face, snapshot, old-incarnation, AI and HTTP regressions cover this bounded clause. Simulator preflight warns that the separate exiled-card copy activation remains unsupported. Verification: 1,399 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift or anomalies.

- Unified front-face printed card-type parsing for modal face selection, distinct-type reveal, and the corpus auditor. The audit now recognizes Battle and Kindred rather than scanning type-line substrings, and back-face types cannot leak into front-face classification. Real Scryfall Kindred Sorcery and Sorcery // Land type lines have regression assertions; the empty-cache corpus audit remains at 112 names with zero fallback/missing classifications. Verification: 1,392 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift or anomalies.

- Temporary Lockdown-style ETB exile now records source and exiled-object identities in snapshots and returns eligible nontokens under their owners when that source leaves. A source leaving before resolution exiles nothing; destruction, bounce/reentry, state-based death, simultaneous sources, and between-clause return have focused regressions. The distinct-card-type reveal matcher now recognizes Kindred as a separate current card type. An empty-cache shipped-corpus audit reports 112 names and zero parser fallbacks or missing Oracle records. Verification: 1,391 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a two-game seeded replay with zero reported drift or timeout. This is bounded printed-wording support, not a general linked-exile or arbitrary-card rules certificate.

- Atraxa-style top-library reveal now offers a resumable human/AI choice of cards assignable to distinct printed card types. A multi-type card counts for one type; invalid assignments are rejected before mutation, and zero-card choice still performs the mandatory reveal and random-bottom placement. AI ranks the full reveal before selecting the best assignable cards for hand, rather than truncating first or scoring them as free battlefield entries. The human legal-choice list now includes type lines. Abbreviated legendary self-entry references match the same source, and optional per-card selection no longer skips the entire trigger. Shared action validation rejects malformed card-ID lists before hashing them. Real shipped Oracle text, snapshot restoration, AI choice and HTTP accept/reject behavior have regressions. The empty-cache parser report now leaves only Temporary Lockdown (two copies) as a fallback; parser classification does not certify other effects. Verification: 1,381 isolated backend tests, frontend lint/build/unit, the full solo Chromium harness and a two-game seeded replay with zero reported determinism failures.

- Cartographer's Survey-style Oracle text now compiles to the shared resolution-time topdeck permanent chooser with a land-only candidate filter and forced tapped entry. Human and AI choice regressions cover snapshot continuation, nonland exclusion, selected lands and unchosen library cards. The empty-cache corpus report now flags five fallback copies across Atraxa and Temporary Lockdown; this is parser classification, not general card correctness. Verification: 1,376 isolated backend tests, frontend lint/build/unit, the full Chromium harness and a two-game seeded replay with zero reported determinism failures.

- Added a generic controller-only temporary team-buff effect for supported Oracle ETB wording, including a granted keyword. Static anthem scanning no longer double-applies the same triggered, until-end-of-turn clause. Shipped Imodane's Recruiter Oracle data now drives a snapshot/trigger/cleanup regression covering friendly and opposing creatures and creatures entering after resolution. The empty-cache report has six remaining fallback copies across Atraxa, Temporary Lockdown and Cartographer's Survey; broader conditional and duration wording remains open. Verification: 1,374 isolated backend tests, frontend lint/build/unit, the full Chromium harness, and a two-game seeded replay with zero reported determinism failures.

- Expanded the reproducible offline Oracle seed from 95 to 119 Scryfall-ID-backed cards, covering every unique name in the 11 built-in and 52 expansion decklists plus extras. The read-only exporter now sources uncached shipped cards from validated local Scryfall bulk records and preserves Adventure faces. An empty-cache corpus report has zero missing Oracle records across 112 shipped names; four cards still have parser fallbacks, so this is metadata coverage rather than rules certification. A browser run caught and corrected an omitted prior extra, Sacred Foundry, before release. Verification: regenerated seed reproduced byte-for-byte from local canonical data; 1,372 isolated backend tests, frontend lint/build/unit, full Chromium harness and a two-game replay with zero reported drift pass.

- Fixed the shared Oracle trigger path for X-based ETB sweeps: it now accepts printed “each creature gets -X/-X,” isolates the entering ability from other printed abilities, and evaluates “you control” versus “opponent controls” creature-death clauses independently. A seeded real-card Meathook cast for X=2 now reduces toughness, kills small creatures and puts the resulting life triggers on the stack. Snapshot and two-controller life-change tests cover the sequence. Verification: 1,371 isolated backend tests, frontend lint/build/unit, full Chromium harness, a two-game deterministic replay with zero reported drift, and four seeded Tokens/Ramp games without timeout or obvious target/cost errors. Tokens won all four; this is rules repair, not matchup balancing.

- Untap no longer offers player priority: normal and post-mulligan turn transitions proceed directly to upkeep. Pending replacement and trigger choices remain answerable. Master AI now waits until its own main phase to cycle on an empty stack instead of spending mana before it can play a land or cast a sorcery. In a repeated Tokens/Ramp seed, Ramp stopped cycling Migration Path during untap and cast The Meathook Massacre for X=2 in the turn-eight window it previously missed. Verification: 1,370 isolated backend tests, frontend lint/build/unit, full Chromium harness, a two-game deterministic replay without reported drift, and four seeded Tokens/Ramp games from both seat orders without timeout or obvious cost/target errors. Tokens won all four, so this is decision evidence, not balance or expert-AI certification.

- AI counter selection no longer falls back to its own spell when no opposing stack target exists. The shared target chooser and ordinary/modal cast materialization reject that line unless the printed clause expressly targets a spell or ability its controller controls. A real-card Spell Pierce/Counterspell regression preserves countering an opponent's stack spell. In two fixed-seed Tempo/Blue Control games, the two observed self-countered Lightning Bolts fell to zero; both games still completed without timeout. Verification: 1,367 isolated backend tests, frontend lint/build/unit and the full isolated Chromium harness pass. This is decision evidence, not a win-rate or expert-AI claim.

- Added a live HTTP/SQLite-restore regression for Fable of the Mirror-Breaker's final chapter. It covers two-face deck hydration, a persisted pending chapter, priority-pass resolution and the serialized back-face name, types and stats. Verification: 1,366 isolated backend tests, frontend lint/build/unit and the full isolated Chromium harness pass. The browser harness does not specifically play Fable; arbitrary Saga semantics remain uncertified.

- Transforming Saga chapters with the supported "Exile this Saga, then return it to the battlefield transformed under your control" wording now use a separate exile-and-return effect instead of an in-place transform. Fable of the Mirror-Breaker regressions cover cleared counters, re-entry state, enter-transformed triggers, snapshots and a Saga controlled by a nonowner. Verification: 1,365 isolated backend tests and frontend lint/build/unit pass; browser play and matchup replay were not rerun. Other re-entry replacement effects and broader Saga wordings remain open.

- Upkeep start now stages the day/night change, affected permanent transformations and ordinary upkeep triggers as one order window. Every face changes before transform triggers inspect the battlefield; triggers are grouped for APNAP and human ordering rather than being pushed one permanent at a time. Two-seat Corruption of Towashi, Brutal Cathar copies and Phyrexian Arena cover final-face visibility, ordering and snapshot continuation. Verification: 1,364 isolated backend tests and frontend lint/build/unit pass; browser play and matchup replay were not rerun. Other simultaneous transform causes and broader trigger semantics remain open.

- Corruption of Towashi's optional transform/enter-transformed draw now uses the shared trigger and human optional-choice window. Declining leaves a later transform eligible; accepting records the once-per-turn choice until the turn reset. Transforming double-faced permanents entering back-face-up count, modal back-face land plays do not, and Corruption's own Incubate ETB is compiled separately from its draw trigger. Verification: 1,363 isolated backend tests and frontend lint/build/unit pass; the final accepted-choice snapshot assertion passed separately. Browser play and matchup replay were not rerun. Simultaneous-transform ordering and other optional trigger wordings remain open.

- Battlefield transforms now emit a shared rules event. A permanent you control transforming into the creature subtype named by a supported counter trigger puts that trigger on the stack; Norn's Inquisitor and Incubator snapshot/leave-zone regressions cover controller, resulting subtype and response timing. Counter effects no longer modify permanents that have left the battlefield. Verification: 1,361 isolated backend tests and frontend lint/build/unit pass; the strengthened real-Oracle sequence passes separately. Browser play and matchup replay were not rerun. Optional once-per-turn transform draws and entering transformed remain open.

- Added bounded Incubate rules: Incubator transforming double-faced tokens enter with +1/+1 counters, expose their `{2}` ability through normal priority/stack play, and retain faces/counters across snapshots. Sunfall incubates for creatures actually exiled; Chrome Host Seedshark incubates for a noncreature spell's printed mana value including announced X. Fixed-number Incubate ETB triggers and land-count "incubate X twice" use the same handler; unknown X sources are not silently interpreted as zero. Permanents now age out of summoning sickness even if they were noncreatures until transforming or animating, and newly animated lands cannot tap for mana without haste. Other Incubate forms and transform triggers remain exploratory. Verification: 1,358 isolated backend tests plus frontend lint/build/unit checks pass; Chromium was not rerun for this backend-only increment.

- Applied the supported "This spell costs {N} less ... for each basic land type" Domain wording through the shared cost modifier. It uses controlled land subtypes, not land names, and affects move legality, AI affordability, spell-tax-adjusted payment and actual casting without changing printed mana value. Verification: 1,350 isolated backend tests, frontend lint/build/unit checks and the full Chromium browser harness pass.

- Implemented the bounded Domain token-creation wording used by Herd Migration: count distinct basic land subtypes among controlled lands, including nonbasic dual/triple lands, when the effect resolves. Zero types create zero tokens. Sorcery/instant cast parsing now ignores separate activated-ability lines, so Herd Migration's discard/search ability no longer replaces its cast effect. The generic name fallback remains disabled for cards with printed Oracle text. Other Domain uses, such as Leyline Binding's discount, remain unsupported and preflight still warns. Verification: 1,347 isolated backend tests, frontend lint/build/unit tests and the full Chromium browser harness pass.

- Extended simulator rules-coverage preflight to flag kicker, multikicker, Domain and Incubate from Oracle root/face text. A read-only scan of the sourced OTJ list now flags five cards that previously passed silently. This is an honest warning, not an implementation of their gameplay rules. Verification: 1,343 isolated backend tests, frontend lint/build/unit tests and the full Chromium browser harness pass.

- Expansion catalog single/all import now updates the newest saved row for each stable expansion source instead of creating another row on every click. Existing user decks and historical duplicate IDs remain untouched. The UI calls this a catalog sync. SQLite regressions cover repeated imports and the newest legacy duplicate. Verification: 1,342 isolated backend tests, frontend lint/build/unit tests, and the full Chromium browser harness pass. Concurrent multiworker uniqueness and legacy duplicate cleanup remain open.

- Reclassified the 51 expansion-label archetype copies as templates instead of claiming tournament status. OTJ now contains Yoshihiko Ikawa's historical 2024 Pro Tour Thunder Junction Domain Ramp 60+15 list, with source/event provenance exposed in API and UI. App-managed expansion decks refresh by stable code so an existing OTJ row keeps its ID on rename; user decks are untouched. Deck import now resolves front-face names to canonical multi-face cards (including Adventure cards) rather than relying on fuzzy matching. The OTJ list parses against local card knowledge with zero errors or suggestions. This does not certify current Standard legality or complete engine support for the new cards. Sources: [decklist](https://mtgdecks.net/Standard/domain-ramp-decklist-by-yoshihiko-ikawa-2021543), [event winner](https://magic.wizards.com/en/news/mtg-arena/mtg-arena-announcements-april-29-2024).

- Added a rules-coverage preflight for the Testing Simulator. The API returns the same known-unsupported-card summary used by completed results without starting a job; the UI pauses for explicit review before running a deck with a known gap. Ordinary matchups proceed on the first click, and batch `Master+` now matches the existing AI option. Verification: 1,335 isolated backend tests, an expanded invalid-input retest, frontend lint/build/unit and the full Chromium harness pass. Absence of a warning is not rules certification.

- Card completeness and name suggestions now include canonical bulk-only cards without mutating the gameplay cache. Completeness counts valid empty Oracle text on vanilla cards and absent mana costs on lands correctly, distinguishes uncached data from unavailable metadata, and accepts a verified empty rulings list. The `/cards/completeness` route now reads repeated `names` query parameters as the frontend sends them; the deck panel labels metadata availability separately from rules coverage. Verification: 1,333 isolated backend tests, a focused repeated-query HTTP retest, frontend lint/build/unit and the full Chromium harness pass.

- Local Scryfall bulk knowledge now supplies exact-name deck parsing, import analysis and live-match card metadata offline. Previously uncached requested cards are lazily materialized into the gameplay cache, including double-faced metadata and front-face colors; existing cached printings remain intact. Manual provenance is not treated as canonical, and missing rulings are not labeled verified. Verification: 1,330 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game BO3 replay pass without reported timeout or drift. This is data integration, not universal rules or image coverage.

- Modal spell copies now convert unambiguous shared target announcements into independent per-mode targets on the copy only. This covers distinct stack/permanent targets and two modes initially aimed at the same permanent, without changing the original spell or its chosen modes. Cryptic Command regressions cover snapshot, HTTP choice and AI counter/bounce retargeting; Kolaghan's Command covers duplicate target occurrences. The match-start recovery browser test now allows both configured 30-second request attempts before timing out. Verification: 1,326 backend tests in an isolated checkout, frontend lint/build/unit and full Chromium harness pass; one seeded three-game BO3 replay resolved without timeout, anomaly or determinism drift. Ambiguous or multi-target-per-mode clauses remain unsupported.

- Supported copies of explicit per-mode modal spells now offer an independent optional target choice for each selected mode with one target and one effect. Changing a mode updates only the copied spell's announced target and effect payload; its original and selected modes remain unchanged. Kolaghan's Command and Cryptic Command regressions cover permanent, player and stack targets, snapshot continuation, illegal original targets and AI avoidance of self-destruction. Verification: 1,321 backend tests in an isolated checkout plus the final stack-target focused test, frontend lint/build/unit and full Chromium harness pass; one seeded three-game BO3 replay resolved without timeout, anomaly or determinism drift. Shared-target modal forms and nested/multiple targets within a mode remain open.

- Supported divided-damage spell copies now offer one optional target choice per announced recipient. Retargeting preserves each recipient's assigned damage and the number of targets, rejects duplicates and newly illegal targets, and can keep an original target that has become illegal. Choices survive snapshots and pause the copying spell until all are answered. Focused Pyrotechnics/Twincast tests and a two-step Chromium choice cover the path. Verification: 1,318 backend tests in an isolated checkout, frontend lint/build/unit and full Chromium harness pass; one seeded three-game BO3 replay resolved without timeout, anomaly or determinism drift. Modal and other multi-target copy semantics remain open.

- "Copy target permanent spell you control" now uses the shared stack-target restriction path, admitting controlled Artifact, Battle, Creature, Enchantment and Planeswalker spells while rejecting instants, sorceries and opposing spells. A real Lithoform Engine activation test copies a Grizzly Bears spell, produces a token at resolution and leaves the original on the stack. Verification: 1,313 backend tests in an isolated checkout, frontend lint/build/unit and full Chromium harness pass; one seeded three-game BO3 replay resolved without timeout, anomaly or determinism drift. Battle token entry and other complex permanent-copy interactions remain unverified.

- Single-target activated and triggered ability copies now use the same optional target-choice window as spell copies. The activated-ability stack payload preserves its announced target and ability text for resolution-time legality checks; supported targeted triggers retain their trigger-clause checks. Lithoform's "activated or triggered ability you control" wording now selects only controlled stack abilities, and an illegal opposing-ability activation is rejected without mutation. Focused tests cover real Lithoform activation, copied Pyromancer and Arsonist abilities, snapshot continuation and a target that leaves play. Verification: 1,311 backend tests in an isolated checkout, frontend lint/build/unit and full Chromium harness pass; one seeded three-game BO3 replay resolved without timeout or drift. Multi-target and linked-ability semantics remain open.

- The isolated Chromium action harness now selects a new target for a copied Lightning Bolt through the rendered human Controls, resolves the copy against Player A and then the original against Player B. This closes the bounded UI path for single-target spell-copy retargeting; more complex copy choices remain open.

- Twincast-style single-target spell copies now offer a legal new-target choice during the copying spell's resolution. The original target remains unchanged, the choice survives snapshots, invalid selections are rejected, and AI can answer it. Focused tests cover HTTP choice, AI damage targeting, snapshot resolution, creature target restrictions and counterspell self-target exclusion. Verification: 1,305 backend tests in an isolated checkout; frontend lint/build/unit and the full isolated Chromium harness pass. One seeded three-game BO3 replay resolved without timeout, reported anomaly or determinism drift; this is not balance evidence. Multi-target, divided, modal and ability-copy retargeting remain open.

- Spell and ability copies now create independent stack objects instead of resolving at creation. Copied targets, modes and announced X persist through snapshots; countering a copy leaves the original source alone, and a copied permanent spell enters as a token when it resolves. Mana *spent to cast* is zero on copies, including Memory Deluge and Search for Glory. The shared parser now recognizes Twincast's printed "instant or sorcery spell" target restriction. Focused priority, HTTP action, counter, target-fizzle, Magecraft and copy-of-copy tests cover this bounded path. Verification at that milestone: 1,299 backend tests, frontend lint/build/unit, the full isolated Chromium harness and a seeded two-game replay with no reported anomaly or determinism drift. Optional new-target selection was added in a later increment; complex copy/entry interactions remain open.

- Supported fixed-output snow-mana payments now record the number and colors of snow-produced mana spent on a spell, including generic and colored portions. Automatic payment preserves ordinary sources for generic costs before tapping snow sources; copied spells count zero. Search for Glory now resolves its snow-permanent/legendary/Saga search followed by life gain from the recorded payment. Fixing the shared library-choice continuation path also preserves later effects after one or more human searches, including across a snapshot. Cast actions can no longer override printed library-search filters, counts or mana limits. Verification: 1,287 backend tests, frontend lint/build/unit, the full isolated Chromium harness, and a seeded two-game replay with no reported anomaly or determinism drift. This is narrow Oracle support, not certification of all snow-dependent spells or dynamic snow-source rules. Copied spells still resolve immediately rather than becoming stack objects; that timing gap is documented separately.

- Snow mana now retains source provenance within each colored/colorless pool and across snapshots. Supported `{S}` costs reserve actual mana produced by snow sources before colored or generic allocation; manual and automatic taps, pool clearing, and fixed-output snow creatures share the same model. The UI marks the eligible subset, and an Icehide Golem browser fixture rejects an ordinary Forest while accepting Snow-Covered Forest. Verification: 1,278 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded two-game replay without reported anomaly or determinism drift. Snow-spend-dependent effects and changing snow supertypes remain open.

- Compleated planeswalkers now carry the announced Phyrexian life-payment count through the stack and snapshots. On entry, each such symbol paid with life reduces starting loyalty by two; mana payment leaves loyalty unchanged. A Tamiyo, Compleated Sage regression covers both branches, countering, and restoration of printed loyalty after leaving play. The full Chromium harness now casts both branches through the live API and checks rendered loyalty; its launcher uses the project backend venv instead of assuming `python` is on `PATH`. Verification: 1,273 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded two-game replay without reported anomaly or determinism drift. Other loyalty-entry replacement interactions remain unverified.

- Human activated abilities now expose supported hybrid and Phyrexian payment branches. Pestilent Souleater's printed `{B/P}` ability can be paid with black mana or two life; an unaffordable announced branch is rejected before state mutation. A reusable self-keyword effect now grants a single printed keyword until cleanup, survives snapshots and does not affect a source that left play; the browser fixture checks infect after resolution. The UI resets ability drafts on a new match. Verification: 1,272 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game replay without reported anomaly or determinism drift. Cycling remains automatic because no printed Phyrexian cycling example was added to the supported corpus.

- Supported Phyrexian mana symbols now offer their printed colored-mana or two-life branches in the shared payment planner, including hybrid Phyrexian symbols. Human cast controls can choose the life branch; automatic payment prefers payable mana branches. Combined additional-life costs are checked before payment, and life-paid triggers from casting are staged above the spell. AI opening-hand color checks no longer require a color that may be paid with life. A browser regression also caught and fixed stale target selections carried into a new match. Verification: 1,271 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game replay without reported anomaly or drift. Focused checks cover Mutagenic Growth, triggered life payment, low-life rejection, activated-cost reservation, cycling trigger order and a human browser cast. Compleated loyalty changes, human Phyrexian selection for cycling/activated abilities and snow-mana provenance remain open.

- Cast-option serialization is now shared across hand, graveyard, exile and top-library moves, so supported hybrid payment branches are visible in every permitted cast zone. Spectral Procession and Figure of Destiny zone regressions cover the previously missing exile and library payloads; the payment and UI implementation is unchanged. Verification: 1,268 isolated backend tests, frontend build, full Chromium harness and a seeded three-game replay without reported anomaly or drift.

- Human cast controls now expose per-symbol payment branches for supported two-part hybrid mana costs. The API validates the chosen cost option, branch count, printed alternatives and affordability before mutation; leaving all selectors on Auto preserves AI and older-client behavior. Focused Spectral Procession and `{W/U}` regressions cover explicit payment and unchanged state after rejected choices. Verification: 1,267 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game replay without reported anomaly or drift. Payment source selection remains automatic, and Phyrexian/snow payments remain unsupported.

- AI opening-hand and land-demand heuristics now distinguish mandatory colored pips from supported two-part hybrid choices. A hybrid-heavy hand with Islands no longer triggers a false missing-white mulligan; fixed-white spells still do, and unsupported `{B/P}` retains the existing black requirement. Land-demand scoring splits a `{W/U}` preference across its two colors. Verification: 1,265 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game replay without reported timeout, anomaly or drift. This is not a full payment-choice or deck-strategy optimizer.

- Supported two-part hybrid mana costs now offer either printed payment branch in both legal-move generation and automatic payment. Spectral Procession can use three white or six generic mana; two-color hybrid symbols accept either color, and hybrid mana value uses the largest component. Generic taxes preserve hybrid symbols, while reductions apply after choosing a payment branch. The backend chooses the first payable branch; a human branch selector, Phyrexian life payment and snow-cost restrictions remain open. Verification: 1,263 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game replay without reported timeout, anomaly or drift.

- Replaced separate greedy mana affordability/payment paths with one deterministic source-allocation search for supported fixed-output sources. Hallowed Fountain plus Marble Diamond now correctly offers and pays a `{W}{U}` spell, and Gilded Lotus surplus pays generic cost without double-spending the source. Sparse mana-pool fixtures exposed and fixed an initial regression. Verification: 1,260 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game replay without reported timeout, anomaly or drift. Hybrid/Phyrexian choices, mixed/variable-output abilities and mana-trigger ordering remain outside this bounded planner.

- Public opposing card types seen on the battlefield, in graveyard, face-up exile or on the stack are now remembered across match actions, autoplay batches and SQLite restore for AI sideboarding. A card returning to hidden hand does not erase a legitimate prior observation, while a card seen only in hidden hand is still excluded. Focused restore/privacy regression, 1,258 isolated backend tests, frontend lint/build/unit, full Chromium harness and one seeded three-game replay pass without reported timeout, anomaly or drift. The memory records types, not complete card identities or strategic sequences.

- AI-controlled seats with supplied sideboards now make bounded, color-source-checked swaps before the next game. Human opponents' hidden hands and internal archetype labels are excluded; public opposing card types drive the decision, while AI-vs-AI testing may use its known matchup label. Sideboard cards are hydrated at match start, and swaps persist through SQLite restore. Focused HTTP/autoplay/privacy checks, 1,257 isolated backend tests, frontend lint/build/unit, the full Chromium harness and one seeded three-game replay pass without reported timeout, anomaly or drift. This is a conservative heuristic, not general tournament sideboard planning.

- AI no longer treats exact each-player draw spells as unconditional one-sided card advantage. A shared pre-decision filter rejects clearly bad hand refills and self-decking while retaining an opponent-decking cast. Before/after tests reproduce the original Master AI mistake, then verify behavior across Control, Tempo, Aggro, Ramp and Tokens and an X-cost draw spell. Verification: 1,251 isolated backend tests, the full Chromium harness and a seeded three-game replay (60 turns, no timeout or drift) pass. Broader symmetric-resource strategy remains open.

- Exact each-player draw clauses now resolve in active-player order instead of being treated as unsupported Oracle text. Vision Skeins and Prosperity regressions cover both seats drawing, X, human dredge-choice continuation after a snapshot, stack resolution, one-player deck-out and a two-player drawn game. Verification: 1,243 isolated backend tests, frontend lint/build/unit, the full Chromium harness, and a seeded three-game replay (60 turns, no timeout or drift) pass. This does not imply support for every compound/optional draw wording.

- Empty-library draw failures now wait for the next state-based-action check, allowing two simultaneous failed draws to produce a game draw. The pending failures survive snapshots; multi-card draw effects stop after the first failed attempt and log only successful draws. Added focused state, snapshot and effect regressions. Verification: 1,238 isolated backend tests, the full Chromium harness and a seeded three-game replay pass without timeout or drift. Broader simultaneous multi-player draw wording is still unverified.

- Simultaneous life/poison losses now produce a drawn game rather than awarding the last-processed player a win. Live BO3 records no point for a draw and retains the prior play/draw chooser after restore; UI autoplay and between-game controls recognize a draw as a finished game. Diagnostic BO3 replay permits extra drawn games up to a declared cap without extending timeout games. Added engine, snapshot, HTTP, replay and Chromium regressions. Verification: 1,235 isolated backend tests, frontend lint/build/unit and the full loopback Chromium harness pass; a seeded three-game BO3 replay finished in 60 turns with no timeout or drift. Other simultaneous-loss paths and AI sideboarding remain open.

- Public match views now expose face-up exiled cards in an inspectable tray for both seats, with snapshot-persisted per-card face-down redaction and total exile counts retained. The API boundary validates visible exile views; engine, HTTP, contract and browser tests check hidden identities stay out of public responses and Appetite's exiled card can be previewed. Supported land/spell plays clear stale exile visibility through the shared zone transition. Verification: 1,231 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). This adds a visibility model, not mechanics for effects that exile cards face down.

- Extended the reusable revealed-hand choice to an exile destination and a mana-value minimum. Appetite for Brains now reveals the full targeted hand, offers only cards meeting its printed threshold, and exiles the selected card without firing discard behavior. The choice survives snapshots; no-eligible-card and target-illegal cases, AI selection and human browser controls have regressions, including a positive-control discard trigger. Verification: 1,229 isolated backend tests, frontend lint/build/unit, full Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). The UI records the exiled card in the log but does not yet browse the exile zone.

- Added reusable revealed-hand discard eligibility for a nonland card with mana value N or less and for a creature-or-planeswalker card. Canonical Inquisition of Kozilek and Despise fixtures cover targeting, choices, invalid selection, snapshot continuation and public reveal; browser controls cover both. Verification: 1,225 isolated backend tests, frontend lint/build/unit, the full Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly label or determinism failure). This does not implement other mana-value comparisons or general hand-inspection effects.

- Extended revealed-hand discard to printed type restrictions and later effects. Thoughtseize offers only nonland cards and loses 2 life after its discard choice, including when there is no eligible card; Duress offers only noncreature, nonland cards. The full hand is recorded in the public reveal log even when some cards cannot be chosen. A sole target made illegal before resolution suppresses Thoughtseize's discard and life loss. Live, restored, batch and diagnostic AI now receive both archetypes, and verbose head-to-head tests enable AI mechanic choices. Engine/snapshot, AI, HTTP and browser regressions cover selective options and continuation. Verification: 1,223 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness, a seeded three-game replay (60 turns, no timeout/anomaly/drift), and one Midrange vs Dimir Control diagnostic without timeout. Broader reveal/choose clauses remain open.

- Added a revealed-hand discard choice for supported "target opponent reveals their hand; you choose a card; that player discards it" wording. Coercion now requires a legal opponent target, then lets the caster select the discarded card at resolution; AI chooses from the revealed options. Engine, snapshot, HTTP privacy and browser checks cover this path. The player-target dropdown gained an accessible label. Verification: 1,216 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). Other chooser/reveal wordings and multiuser hand authorization remain open.

- Added simultaneous two-player discard for supported "each player discards N cards" wording. Active player chooses first; selections stay in hand and are not exposed in pending-choice payloads until both seats have chosen, then one discard event batch is emitted. Delirium Skeins engine/snapshot and two-seat browser tests cover the flow; AI reuses hand-retention scoring, and random variants use seeded sampling without choice windows. Verification: 1,213 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). Broader discard grammar, chooser overrides and competing replacement ordering remain open.

- Supported spell discard now pauses for the affected seat's card choice instead of automatically discarding the first hand entry. The pending choice is validated and snapshot-safe; later modes of the same spell resume afterward. AI discard uses its hand-retention scorer, while explicit random discard uses seeded RNG. Real Kolaghan's Command and Izzet Charm fixtures cover opponent choice and draw-then-discard timing. HTTP/browser tests verify AI hand secrecy and the opponent-seat UI flow. Verification: 1,210 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). Broader discard Oracle grammar and trigger/replacement ordering remain open.

- Public match responses now carry both players' graveyard card views alongside counts, without revealing AI hands. The battlefield offers an expandable, bounded-height graveyard list for each seat using the existing card preview. Runtime contract tests reject missing or count-mismatched zones, and HTTP/browser regressions cover public visibility. Verification: 1,205 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness, and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). Exile is still count-only because face-down visibility is not modeled.

- Added a loopback browser acceptance case for Kolaghan's Command's printed graveyard-return plus artifact-destruction pair. The human UI offers only creatures in the caster's graveyard, submits the selected card ID, and shows that creature in hand after resolution. The opposing graveyard candidate is excluded. This is a UI/API boundary test; it does not prove general graveyard-zone browsing.

- `Choose two` casts now support independent per-mode target IDs even when both modes target permanents. Real Kolaghan's Command destroy/damage and graveyard-return tests cover AI selection, human cast controls, own-graveyard restrictions, snapshot restore and partial resolution after one target leaves. The graveyard return handler now honors an announced card ID rather than selecting a different card. Verification: 1,203 isolated backend tests, a further 33-test focused modal run, frontend lint/build/unit, full loopback Chromium harness, and a seeded three-game BO3 replay (60 turns, no timeout, anomaly or drift). This does not certify repeated modes or multiple targets in a single mode.

- Added independent resolution-time target rechecks for selected modal effects with distinct stack and permanent targets. Cryptic Command counter/return now compiles the generic return-permanent clause, resolves surviving targets, and fails when both targets become illegal; shroud and snapshot regressions cover the boundary. Generic permanent targeting is available to AI and the human cast UI, with a loopback browser cast. Verification: 1,195 isolated backend tests, frontend lint/build/unit, the full Chromium harness, and a seeded three-game BO3 replay without timeout, anomaly or drift. Same-kind multi-target choices and general modal Oracle semantics remain open.

- Compile selected textual spell modes independently in printed order, so early-return effects such as countering a spell do not suppress later draw effects. Real Cryptic Command counter/draw cast-and-resolution and only-target-illegal fizzle regressions cover the shared parser path. Verification: 1,189 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness, and one seeded three-game BO3 replay without timeout, anomaly or determinism drift. This does not add general multi-target modal support.

- Textual `Choose one`/`Choose two` casts now keep targetless modes available when targeted modes lack legal recipients, reject unavailable mode selections, use the same legal-mode list in AI and UI, and resolve selected modes in printed order. Removed the broad "deals" player-target inference while retaining divided any-number-of-targets player choices; a Pyrotechnics regression also prevents a cast with no legal recipient. Added generic tap-all-opponent-creatures resolution and corrected untargeted imperative discard to affect its controller. Real Cryptic Command, Izzet Charm and Drown in the Loch fixtures cover the modal path. Verification: 1,187 isolated backend tests, frontend lint/build/unit, full loopback Chromium harness and a resolved three-game seeded replay without timeout or drift. Repeated-mode and general multi-target modal support remain open.

- AI spell materialization now respects filtered player-target candidates, and pure single-target damage spells are held when only friendly recipients remain. Battlefield target hints now omit hexproof, shroud and protection-from-source candidates using shared legality checks. Explicit invalid targets retain their specific rejection reason. Wording-based Shock and Lightning Bolt regressions verify this is not a card-name exception; a killable opposing creature remains targetable behind player hexproof. The frontend now exposes its existing unit suite through `npm test`. Verification: 1,183 isolated backend tests, frontend lint/build/unit, the full loopback Chromium harness and a resolved three-game seeded replay without timeout or drift. Broader self-damage synergies, modal effects and strategic response planning remain open.

- Static player hexproof/shroud from unconditional battlefield Oracle clauses now affects spell hints, cast validation, trigger choices, divided-damage recipients and resolution-time rechecks. Leyline of Sanctity, Ivory Mask and Aegis of the Gods fixtures cover opponent versus self targeting, illegal-after-announcement fizzle, and untargeted damage. Single-target GUI selectors now clear a prior player/permanent choice instead of submitting both, using the selected modal face's text. Verification: 1,176 isolated backend tests plus a later focused 31-test targeting rerun, frontend lint/build/unit, full Chromium harness, and a resolved three-game seeded replay without timeout or drift. Conditional/temporary grants and player protection remain open.

- Unattended sacrifice-damage triggers now choose from legal targets with a reusable AI heuristic rather than always targeting the opponent's life total. The policy prioritizes a lethal player hit, then profitable one-damage kills, and falls back to opponent damage; real Mayhem Devil and Havoc Jester Oracle fixtures cover the shared path. Verification: 1,171 isolated backend tests plus a later focused 20-test target-interaction rerun, full Chromium harness, and a resolved three-game seeded replay without timeout or drift. This does not add paid optional triggers or broad trigger-mode strategy.

- Supported sacrifice-damage triggers with printed "any target" wording now offer player, creature and planeswalker choices when put on the stack. Target choice survives snapshots, rejects wrong-seat/illegal requests and fizzles if a chosen permanent leaves before resolution. The browser fixture proves both creature and player choices through UI/API; the browser runner now overlays working-tree backend edits in its isolated copy. Verification: 1,167 isolated backend tests plus a later focused 18-test target-interaction rerun, frontend lint/build/unit, full Chromium harness, and a resolved three-game seeded replay without timeout or drift. Battles and broader trigger modes remain unsupported.

- Supported triggers from one sacrifice now share a staging and human/APNAP order choice, including a graveyard trigger and Merchant of Venom's printed untargeted sacrifice trigger. Outer staging is preserved; exile replacement still emits sacrifice but not death. Canonical Merchant/Marionette tests cover choice, snapshot restore, resolution and opponent sacrifice. Verification: 1,163 isolated backend tests, frontend lint/build/unit, full Chromium harness and a resolved three-game seeded replay without timeout, anomaly or drift. Target-dependent Mayhem Devil wording remains unsupported until a target-choice path exists.

- Sacrifices that reach the graveyard now emit the shared permanent-death event. The printed artifact-to-graveyard/target-opponent-life-loss clause resolves from effective source power, including a trigger source that dies in the same batch; only current-batch departed sources are eligible. Real Marionette Master, Everflowing Chalice, Memnite and Rest in Peace fixtures cover destroy, sacrifice, simultaneous wipe, opponent control, replacement-to-exile and stale-source cases. Verification: 1,159 isolated backend tests, frontend lint/build/unit, full Chromium harness, and a resolved three-game replay without timeout, anomaly or drift. Other artifact-death effects and cross-event trigger ordering remain open.

- Supported death triggers now use pre-exit effective power and transformed-face Oracle characteristics, including simultaneous wipes where a buff source also dies. Last-known battlefield data survives snapshots and clears when the card re-enters as a new permanent. Real Heartfire Hero, Cacophony Scamp/Goblin Chieftain and Fragment of Konda regressions cover these paths. Verification: 1,152 isolated backend tests, frontend lint/build/unit, the full Chromium harness and a resolved three-game seeded replay without timeout, anomaly or drift. The final focused rerun used exact cached Oracle fixture text. Broader last-known-information consumers, copied-object semantics and complete zone-change fidelity remain open.

- Graveyard zone transitions now clear old counters and combat markers after supported single and batch death events collect their triggers; Skullbriar-style printed persistence retains real counters. Stack-to-graveyard and sacrifice-only paths also reset the new object. Two legacy prevention tests now use surviving 2/3 creatures, so they test prevention rather than stale marked damage on a dead 2/2. Verification: 1,148 isolated backend tests, the standalone full Chromium harness and a resolved three-game replay without drift pass. Generic last-known-information snapshots, transformed death characteristics and complete zone-change fidelity remain open.

- Exile transitions now clear old counters, damage and temporary P/T markers after leave triggers can inspect the old permanent. Printed counter-persistence wording keeps real counters where allowed; direct, batch and Rest in Peace replacement regressions cover the supported path. Lethal spell damage now emits the same leave event used by other exits, so temporary-control and attachment cleanup cannot be skipped. Verification: 1,144 isolated backend tests, the standalone full Chromium harness and a resolved three-game replay without drift pass. Graveyard death-state cleanup and general last-known-information snapshots remain open.

- Temporary control changes now end when the controlled permanent leaves the battlefield, rather than following the reused card ID onto a reanimated permanent. A Threaten-style destroy/reanimate/snapshot regression reproduces the incorrect cleanup reversion and guards the shared leave path. Verification: 1,141 isolated backend tests, the standalone full Chromium harness and a resolved three-game replay with no drift pass. Broader control-layer ordering remains open.

- Battlefield-exit events now reset transformed double-faced cards to their printed front face after leave triggers are collected. They also detach Equipment/Auras and their departing targets, preventing old same-ID attachments from surviving bounce and recast. Delver of Secrets and Short Sword snapshot/action regressions cover these identity transitions. Verification: 1,140 isolated backend tests, the standalone full Chromium harness and a three-game deterministic replay pass. Broader copy and zone-object semantics remain open.

- New battlefield objects no longer inherit +1/+1 counters or marked damage from the prior permanent. The shared entry reset runs before supported Escape/entry counters; Grizzly Bears bounce and Ox of Agonas Escape snapshot regressions guard both paths. A generic printed counter-persistence clause retains real counters through graveyard return but not hand/library movement, verified with Skullbriar's local Scryfall Oracle text. Verification: 1,138 isolated backend tests, the standalone full Chromium harness and a three-game deterministic replay pass. Other zone-change object fields remain an open audit.

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
