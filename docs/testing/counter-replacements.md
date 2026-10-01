# Counter-effect replacement order

## Implemented

Registered `add_counters` and `add_player_counters` effects now resolve supported
scalar replacement clauses in application code. Canonical fixtures include
Doubling Season, Vorinclex, Winding Constrictor, Lae'zel, Hardened Scales,
Corpsejack Menace, Branching Evolution, Primal Vigor and Kami of Whispered Hopes.
There is no card-name dispatch or alteration of printed data.

- Effect controller is the placer. Recipient is separately the player receiving
  counters or the current controller of the affected permanent. Controller/type
  scope is checked against the actual event; land animation after placement
  cannot retroactively make a creature-only modifier apply.
- Each applicable printed ability has its own source-instance/line identifier
  and may modify an event only once. Multiple abilities on one card are not
  conflated merely because their card IDs match.
- Two or more competing abilities pause for the affected player's order choice.
  Used-ability state, modified amount, original effect and remaining instructions
  persist in existing replacement choices/snapshots. No counters are placed
  until the event's replacement chain is finished.
- Halving uses integer floor. Zero counters stop the chain; a later plus-one
  effect cannot resurrect an event that now puts no counters. Supported "can't"
  restrictions suppress modifiers and placement.
- Shared effect sequences and multi-creature counter effects resume without
  skipping/repeating instructions. Separate land animation waits for the choice.
  Real experience triggers finish exactly once through the existing stack.
- Shared AI uses public counter amounts, minimizes poison/-1/-1/stun and otherwise
  maximizes amount. It evaluates all order outcomes up to 24 applicable modifiers
  using cached operation counts; larger sets use a deterministic immediate-amount
  heuristic. This is an amount preference, not general counter-resource strategy
  or expert-level outcome optimization. Individual card/counter exceptions need
  further tactical/knowledge work.

Human controls reuse the actual legal `choose_replacement` actions and correct
acting seat. Chromium exercises a real Minthara end-step trigger with seat-two
Winding Constrictor/Vorinclex ordering, four experience counters and effective
power updated to six through HTTP and UI.

## Verification

Release results and source fingerprints are recorded in `counter-replacements.json`.
The final suite passes **2,308 backend tests**, including **44 new regressions**,
with 292 existing deprecation warnings (231.91 seconds). **257 focused counter/AI
checks pass**. Frontend lint, TypeScript/Vite build, unit contracts and the full
Chromium harness pass, including the new seat-two order choice and natural AI,
human-vs-AI and human-vs-human BO3 flows.

A separate isolated HTTP probe confirms autoplay resolves the real seat-two
counter trigger in one tick, places four experience counters and clears the
pending choice/stack. Eight seeded seat-paired smoke games repeat complete
reported results/logs across sixteen executions without timeout or detected
cast/target/cost rejection; this is repeatability evidence, not AI/balance proof.
Tests and browser jobs run in separate disposable tracked-source/database copies.
Canonical fixtures were exported using a read-only query of the existing cache.
Negative parser/core-operation fixtures are labeled, not invented playable cards.

The first complete suite caught 37 AI test-double failures from an overly strict
new field access. All had the same missing optional pending-choice field; the
agent now uses its existing optional-field convention. Original assertions were
not weakened. Final verification supersedes that failed run.

An abstract 24-option amount-policy benchmark, not an invented game/card, completed
in 0.465 seconds with 6.06 MiB peak allocation under `tracemalloc` on this host.
This is one measured case, not a guaranteed per-decision time/memory ceiling.

## Known Limitations and Next Upgrades

- The shared physical placement helper still handles prohibitions alone for
  Saga advancement, token/spell entries, opening counters
  and loyalty costs. **Scalar replacements in those routes remain incomplete.**
  Existing player/route-fidelity warnings deliberately remain visible.
- Supported damage consequences are now routed through scalar events in the
  [damage increment](damage-counter-replacements.md). Its narrower combat and
  continuation evidence does not certify general simultaneous damage/prevention.
- Extend the event model through pre-entry characteristics, source attribution,
  entry/activation costs, simultaneous combat/batches and multi-kind events.
  Resumption must not announce entry triggers or run SBA before placement finishes.
- Unknown replacement clauses warn; caps, moving/spending counters, proliferation,
  arbitrary counter-added triggers and full suppression/layer dependencies remain
  open. Do not infer whole-card support from recognized clauses or green tests.
- Amount-based AI can miss a strategic reason to prefer fewer normally beneficial
  counters, or more normally harmful ones. Broader counter-resource valuation,
  tournament-quality AI and matchup/balance certification remain separate goals.

References: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules)
and [Phyrexia: All Will Be One release notes](https://magic.wizards.com/en/news/feature/phyrexia-all-will-be-one-release-notes).
