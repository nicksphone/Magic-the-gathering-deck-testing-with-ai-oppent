# AI Status Checklist

Updated: 2026-11-05. Live gameplay source: `15aa3c77`.

**Status: working heuristic AI with implemented improvements; playing strength
and AI release acceptance are NOT complete. No reliable percentage estimate.**

Checked items below mean the named implementation exists and has evidence in
its stated scope. They do not mean optimal decisions or bug-free play across
all cards. This is the AI checklist, not the whole application's RC checklist.

## Implemented And Verified In Bounded Checks

- [x] Engine-driven play: opening choices, land/spell play, targeting, payment,
  combat and supported pending choices use actual engine actions.
- [x] Archetype and matchup-profile infrastructure, rather than one identical
  set of play priorities for every deck. Broad strategic quality remains open.
- [x] Actor-visible decision inputs and strict complete-action validation.
  Private future cards are not legitimate AI observations.
- [x] Coherent retained opening-hand selection (`7fd7c17e`).
- [x] Guards against uncompensated destruction of useful friendly material,
  including complete supported compound removal outcomes (`ac56e51c`, `199b5842`).
- [x] Better legendary-permanent retention and avoidance of paid duplicate
  legends with no public payoff (`310c74d5`, `402e19b0`).
- [x] Symmetric material valuation when retaining early blockers (`87b17594`).
- [x] Strong reuses a blocker freed by retention when a checked block against
  an uncovered attacker improves the outcome. The coupled 38 whole modules
  passed 1,230 tests plus six subtests; bounded projections, hidden-input
  controls and weak/large-board fallbacks remain covered. See
  [the recorded defect and correction](docs/testing/ai-unused-blocker-refill.md).
- [x] Master/MasterPlus share a deterministic combat-expansion allowance across
  nested planning, rather than multiplying independent local search limits.
  The two affected cohorts passed 649 tests plus six subtests and 114 tests.
  The retained 102.60-second decision chose the same checked attack in 11.31
  seconds. This component is live on `15aa3c77`; overall practical performance
  remains open. See [the measured scope](docs/testing/master-combat-budget.md).
- [x] **Stop discarded search work:** after a denied combat expansion, private
  strategic searches stop instead of continuing work the root will discard.
  Previously checked candidates and ordinary legal fallback remain usable;
  difficulty and allowances are unchanged. Affected cohorts passed 682 tests
  plus six subtests and 114 HTTP tests. The retained decision took 6.75 seconds;
  this follow-up is live on `15aa3c77`. See [scope and limits](docs/testing/post-denial-speculation.md).
- [x] **Retain selected block plans:** ranking keeps its selected allocation
  after shared-budget denial rather than selecting again. Generic empty-descriptor
  behavior is preserved, losing partial searches retain fallback, and draws are
  not defeats. Final affected qualification passed 933 tests plus six subtests
  across 34 whole pure modules in three process shards, and 114 tests in two
  whole HTTP modules. Two final-code decisions retain the evaluated plan with
  root/RNG and hidden-view controls. This candidate is not yet live and does not
  establish overall playing strength; see [scope and retained failures](docs/testing/retained-block-intents.md).
- [x] Spell-curve classification no longer diluted by the land count (`fffcca07`).
- [x] Ordinary targeted draw spells compare actual legal recipients instead of
  defaulting to the opponent (`ecda33bd`). The affected eight whole modules
  passed 354 tests; the unchanged 14-case paid-spell check passed. This does not
  close every multi-mode targeting route.
- [x] A checked terminal targeted-draw win now takes priority over the ordinary
  counter-mode heuristic (`7bfbfad4`). Both-seat paid Archmage's Charm outcomes,
  explicit choices and private-draw safeguards are covered. Independent nine
  whole modules passed 378 tests; multi-select modes remain separate.
  See [the modal-win scope](docs/testing/ai-modal-draw-win.md).
- [x] Explicit one-mode scalar/list declarations retain per-mode draw recipients
  and selected stack targets instead of crashing or countering an unselected top
  spell. Nullable unused selectors remain valid. Independent 18 whole modules
  passed 844 tests; see [scope and controls](docs/testing/modal-selected-targets.md).
- [x] Source-bound trajectory collection, exact action/frame replay, training
  and checkpoint evaluation infrastructure. Infrastructure is not a strong model.
  The exporter now reuses one actor view per decision-frame capture; all four
  whole compatibility modules passed 151 tests including real CLI resume/refusal.
  See [measured scope and provenance](docs/testing/training-decision-view-reuse.md).
- [x] Paired preference batches and state-contrast checks that expose a model
  choosing the same answer in situations needing different decisions (`6c4ad5bf`).
- [x] Explicit opt-in state/action interaction fixes a reproduced synthetic
  context-learning failure, with strict old-checkpoint compatibility and no
  default change. Independent 15 whole modules passed 272 tests and 27 subtests.
  This is not accepted card strategy or an activated model; see
  [the conditioning evidence and limits](docs/testing/qv-state-action-conditioning.md).
- [x] Failed experimental checkpoints are rejected rather than installed.
- [x] **Current complex core BO3 completion:** default Master on `15aa3c77`
  finished both Drain/Tribal deck orders naturally: five games and 2,257 checked
  committed actions. The reverse needed a separately declared longer operator
  limit; its original capped comparison remains incomplete. This is not
  sideboarding, UI or strategy-strength acceptance. See [actual outcomes](docs/testing/current-master-complex-bo3.md).

## Not Done

- [ ] **Resource-aware trained decisions:** the previous fits failed resource
  contrast checks and were not deployed. Fresh `029a3174` comparisons also fail:
  old/new heads reach 8/16 and 10/16 development decisions, with 0/2 complete
  resource contrast groups. Fixed-encoder controls do not solve it either.
  All four new checkpoints remain rejected; more steps alone are not assumed
  to fix this. A subsequent readout prototype fits TRAIN but fails development
  too. See [the actual evidence](docs/testing/current-resource-conditioning-029a.md).
- [ ] **Broad full-game quality:** demonstrate competent play on a fixed current
  source across Aggro/Burn, Control, Midrange, Tempo, Ramp and Tribal, then the
  supported more complex deck families. Historical games are not current acceptance.
- [ ] **Decision review:** turn recorded passes, attacks, blocks, targets and
  sequencing into verified findings. A pass with playable cards is a review
  candidate, not automatically a mistake.
- [ ] **Multi-card planning and complex targeting:** validate whole-hand lines,
  modal targets and supported synergies beyond the individual fixed regressions.
- [ ] **Useful learned policy:** demonstrate generalization to unseen situations
  and meaningful comparison against the fixed baseline. Learning from the current
  heuristic does not make its choices expert labels.
- [ ] **Practical decision time:** close slow decisions and resource-capped games;
  a CPU timeout is not a completed game or a draw. The new combat allowance
  removes the reproduced minute-long expansion on a retained position, but one
  mirrored Master series still reached the original CPU limit in game three at
  1-1. A separate 64-unit development override also reached that limit and was
  not promoted. Stopping work after sticky denial is now implemented and tested,
  but the same-budget reversed-seat series still reached its limit. A distinct
  longer-limit outcome check does not replace that incomplete comparison.
- [ ] **BO3 strategy:** sideboarding and matchup-prior code exist, but current
  measured series quality and a completed comparison matrix remain unfinished.
- [ ] **No-regression comparison:** complete matched, source-pinned old/new games
  and compare decision quality as well as outcomes. Self-play wins alone prove little.
- [x] **Live delivery of the current draw/block and search-limit fixes:** the
  preview now runs `15aa3c77` (2026-11-05). Earlier draw/block qualification passed
  1,230 tests plus six subtests; the current search-limit/post-denial cohorts
  passed 682 plus six subtests and 114 HTTP tests before their code-only switch;
  all 1,254 saved matches remain listed, two historical matches restored and
  sampled cached images retained identical bytes. No experimental weights
  were activated. See [current delivery scope](docs/testing/master-combat-budget.md#live-component-delivery).
- [ ] **AI RC acceptance:** complete the broader evidence above, plus current
  application integration. Isolated test counts cannot close this item.

## Actual Game Coverage Snapshot

| Matchup | Evidence | What It Does Not Prove |
| --- | --- | --- |
| Burn / White Weenie | Two fresh `ecda33bd` games finished naturally, with the deck seats reversed; 251 and 477 accepted moves | All Burn/WW decisions are good, or either strategy is finished |
| Blue Control / Midrange | A fresh `812c91bc` Midrange/Control game finished naturally in 695 accepted moves; all 695 frames/actions replayed exactly. An earlier reverse `ecda33bd` game finished in 352 moves | A current matched pair, whole-strategy acceptance or a controlled speedup claim |
| Tribal / Tempo | Two fresh `812c91bc` games finished naturally in 302 and 298 moves with deck seats reversed; all frames/actions replayed exactly | Held-out strategic superiority or BO3 acceptance |
| Ramp | Four frozen `070b4da1` games replayed all 2,358 actions; four same-deck/seed/budget `97f9c309` games replayed all 2,403 actions | Ramp lost all eight; this small diagnostic is not a win-rate estimate, BO3 or strategic acceptance |
| Drain / Tribal core BO3 | Current `15aa3c77` Master finished five natural games across both deck orders: Tribal 2-0 and 2-1, with 2,257 checked actions. The reverse used a separate longer-limit qualification; the original capped result is preserved | Same-budget performance acceptance, sideboarding/API persistence, or expert play |

Every accepted action and actor-visible hand is recorded. One new Burn/WW game
has already replayed exactly through all 251 decision frames. Its wider quality
review is not closed; no zero-error gameplay claim is inferred from completion.
Synthetic game traces stay protected and are not public Git fixtures.

The historical incomplete Midrange/Blue Control prefix replayed through all 584
recorded actor frames. At that frontier the next choice took 0.1104 seconds,
not a demonstrated stall. The new 695-action run preserves that input/action
prefix and finishes with a larger declared budget; the original censored run is
not relabeled as completed. See [current gameplay review](docs/testing/current-ai-gameplay-812.md).

The three current games' available decision screens raised no flags. One Control
block producer returned an uncertain result, so that metric remains unavailable,
not a certified zero. These heuristic screens do not establish optimal play.

The four Ramp reviews produced three unused-mana and two bad-block flags.
Context checks do not establish those passes or one chump block as mistakes.
One block has a checked local improvement: after retaining Stomper from a losing
block, use it against the unblocked Elves. A recorded pass-only continuation
preserves Stomper, removes Elves and saves one life with the same Grazer loss.
The shared blocking correction passed its coupled 38-module qualification;
no alternate-game win or measured strategy-strength gain is claimed.
One Ramp removal metric remains unavailable.

The four corrected-code games finish naturally with the same winners. Three
action/frame streams are unchanged; the affected Ramp/Midrange game first
changes at block 383 and continues for 571 rather than 526 actions. Its remaining bad-block
screen still counts Grazer dying at that block; it does not establish that the
corrected whole plan is a mistake. These are checked local outcomes, not
evidence that Ramp strategy is finished.

## Foundation Evaluation

- [x] Forge and XMage both contain definitions for our 155 shipped cards and
  the 32 harder canonical reference cards. Presence alone is not an execution pass.
- [x] Both passed the four-card, both-seat native compatibility checks: 8 each.
- [x] Selected upstream native tests passed: Forge 125 and XMage 8. The different
  test counts are not a head-to-head AI ranking.
- [x] Forge's additional in-process human-controller callback check passed.
- [x] README/source attribution and original license texts are retained.
- [x] Existing native Forge search ran on unchanged Burn/White Weenie mains:
  four completed matched BO3s, 10 natural games, 51 search decisions and 33
  decisions made by rollouts. Eight whole native classes passed 183 tests.
  Both players changed policy together; the two development pairs do not prove
  strength improvement. See [the actual search results](docs/testing/forge-practical-search.md).
- [x] One isolated native Forge BO3 completed naturally: Dimir Control beat Ramp
  2-0, with actual Ramp sideboarding and conserved deck inventories. Default
  heuristic, open deck lists, constructed diagnostic sideboards; not a strategy
  quality or application-integration certificate.
- [x] Isolated actor projection and one-use choice prototype: 26 boundary checks
  plus two actual human-controller land plays, both seats, passed with the
  selected unchanged upstream cases (154 total). Review found and closed a
  virtual-count leak and request-lifetime gap. No browser/HTTP bridge is live.
- [x] Native process bridge: real human-controller choices crossed JSON-lines
  stdin/stdout with either seat; two complete natural games and two explicit
  disconnect aborts passed. The selected nine-class cohort passed 209 checks.
  This is not browser integration, durable resume or AI-strength acceptance.
  See [the process contract and actual evidence](docs/testing/forge-native-human-worker.md).
- [ ] Prototype the recommended Forge integration without changing the live app;
  prove user choices, privacy, full matches/BO3 and saved-state behavior.
- [ ] Make a production adoption decision, including distribution/license review.
- [ ] **Native durable resume:** a six-process Forge compatibility check restored
  selected settled life/card-placement controls, but lost a genuinely paid spell
  on the stack in both seats (stack 1 to 0; caster inventory 60 to 59). Raw
  observer comparisons remain failed; mana contents, RNG, pending dialogs and
  BO3 resume are not qualified. Do not switch live saved matches to this loader.
  See [the executed compatibility diagnostic](docs/testing/forge-native-save-compatibility.md).
- [x] **Bounded native action replay:** replaying a genuine accepted paid Bolt
  in a fresh JVM recreates the pending stack and resolution for both seats.
  Independent verification checked 3,574 pins and ten unequal-observation
  controls. This is a trusted canonical pose using native AI payment, not
  human-choice replay, arbitrary-game resume or a repaired GameState loader.
- [ ] Verify native AI information fairness: the shuffle guard does not fence
  all heuristics. Source review found opponent-library reads in some naming
  routes; those were not demonstrated in the initial BO3. Client privacy and
  fair AI observations are distinct requirements.
- [x] Reproduced blind-name private-state dependence in paid native spells and
  verified a scoped public-information correction: seven whole classes, 181
  passes. Other native heuristics remain unqualified.
- [x] Four paired native BO3s finished naturally: 11 games, 5,729 actor-priority
  observations, nine actual naming choices. Outcomes were mixed, including a
  corrected-policy loss where baseline won. No overall strength gain claimed.

See [the comparison and limits](docs/testing/external-engine-card-knowledge.md).
Neither engine is integrated into the application yet. Raw Forge views are not
safe browser payloads; the tested projection must still be integrated with real
API authentication, complete choices and saved-state handling. The bounded
prototype demonstrates useful rules reuse, not an approved live cutover.

See [native naming and complete-series evidence](docs/testing/forge-public-naming.md).
Practical native search and a human-controller process bridge have now been
exercised. The save audit found a real pending-spell compatibility gap. Keep the
existing app and saved matches; further native integration is not a reason to
delay verified Python AI fixes or practical decision-quality work.

## Next Work, In Order

1. Keep the existing app and saved data while using the bounded native-engine
   findings as a reference; do not start an open-ended persistence rewrite.
2. Fix the highest-impact observed decision/performance problems and deliver
   verified fixes to the running app.
3. Expand current completed-game coverage beyond Burn/WW, with fixed budgets
   and honest accounting of incomplete games.
4. Train only against a diagnosed learning gap, with separate development and
   untouched evaluation evidence; reject checkpoints that do not improve.
5. Complete the matched full-game and BO3 acceptance evidence before calling
   the AI ready for RC.

Burn and White Weenie remain regression controls, not a substitute for this list.
Update this file when an item changes status; do not mark an entire strategy done
because one fixture or one game passed.

See [the full finish plan](plan.md),
[opening-hand scope](docs/ai-opening-retained-hand.md) and
[friendly-material scope](docs/ai-friendly-material-conservation.md).
