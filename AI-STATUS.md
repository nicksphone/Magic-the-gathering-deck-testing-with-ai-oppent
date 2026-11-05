# AI Status Checklist

Updated: 2026-11-05. Gameplay source: `ecda33bd`.

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
- [x] Spell-curve classification no longer diluted by the land count (`fffcca07`).
- [x] Ordinary targeted draw spells compare actual legal recipients instead of
  defaulting to the opponent (`ecda33bd`). The affected eight whole modules
  passed 354 tests; the unchanged 14-case paid-spell check passed. This does not
  close the separate multi-mode targeting route.
- [x] Source-bound trajectory collection, exact action/frame replay, training
  and checkpoint evaluation infrastructure. Infrastructure is not a strong model.
- [x] Paired preference batches and state-contrast checks that expose a model
  choosing the same answer in situations needing different decisions (`6c4ad5bf`).
- [x] Failed experimental checkpoints are rejected rather than installed.

## Not Done

- [ ] **Resource-aware trained decisions:** both latest fits failed the resource
  contrast checks. Neither was deployed. More training steps alone are not a fix.
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
  a CPU timeout is not a completed game or a draw.
- [ ] **BO3 strategy:** sideboarding and matchup-prior code exist, but current
  measured series quality and a completed comparison matrix remain unfinished.
- [ ] **No-regression comparison:** complete matched, source-pinned old/new games
  and compare decision quality as well as outcomes. Self-play wins alone prove little.
- [ ] **Live delivery:** deploy and check the latest verified fix. The running
  preview is still the older `fffcca07` build; experimental weights are not live.
- [ ] **AI RC acceptance:** complete the broader evidence above, plus current
  application integration. Isolated test counts cannot close this item.

## Actual Game Coverage Snapshot

| Matchup | Evidence | What It Does Not Prove |
| --- | --- | --- |
| Burn / White Weenie | Two fresh `ecda33bd` games finished naturally, with the deck seats reversed; 251 and 477 accepted moves | All Burn/WW decisions are good, or either strategy is finished |
| Blue Control / Midrange | One fresh `ecda33bd` game finished naturally in 352 accepted moves; the reverse pairing hit its 300-second CPU limit and remains incomplete | Whole-pair quality or performance acceptance |
| Tribal / Tempo | Two earlier `fffcca07` games finished naturally in 204 and 323 moves | Current-source acceptance or strategic superiority |
| Ramp and other complex strategies | Not current-qualified by the evidence above | Completion inferred from shared engine support |

Every accepted action and actor-visible hand is recorded. One new Burn/WW game
has already replayed exactly through all 251 decision frames. Its wider quality
review is not closed; no zero-error gameplay claim is inferred from completion.
Synthetic game traces stay protected and are not public Git fixtures.

## Foundation Evaluation

- [x] Forge and XMage both contain definitions for our 155 shipped cards and
  the 32 harder canonical reference cards. Presence alone is not an execution pass.
- [x] Both passed the four-card, both-seat native compatibility checks: 8 each.
- [x] Selected upstream native tests passed: Forge 125 and XMage 8. The different
  test counts are not a head-to-head AI ranking.
- [x] Forge's additional in-process human-controller callback check passed.
- [x] README/source attribution and original license texts are retained.
- [x] One isolated native Forge BO3 completed naturally: Dimir Control beat Ramp
  2-0, with actual Ramp sideboarding and conserved deck inventories. Default
  heuristic, open deck lists, constructed diagnostic sideboards; not a strategy
  quality or application-integration certificate.
- [ ] Prototype the recommended Forge integration without changing the live app;
  prove user choices, privacy, full matches/BO3 and saved-state behavior.
- [ ] Make a production adoption decision, including distribution/license review.

See [the comparison and limits](docs/testing/external-engine-card-knowledge.md).
Neither engine is integrated into the application yet. Raw Forge views are not
safe browser payloads; an actor-authorized projection remains required. Further
bespoke training is not the immediate priority while this shortcut is evaluated.

## Next Work, In Order

1. Prove or reject the external-engine integration shortcut in an isolated
   prototype; keep the existing app and saved data as the fallback.
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
