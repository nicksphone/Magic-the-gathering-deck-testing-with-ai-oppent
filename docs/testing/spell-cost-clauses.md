# Shared spell additional-cost grammar

## Contract

Read only the printed `As an additional cost to cast ...` sentence, after
reminder-text removal. Later effect words do not add payment requirements or
change sacrifice types. Supported clauses comprise fixed numeric/word-count
discards, fixed or X life payment, and fixed-count sacrifices of recognized
card types. Two-type unions and conjunctions of supported components share
the existing selected-resource cost operations. Separate supported alternative
branches receive distinct stable IDs and one parent cost group.

The parser has no card-name dispatch. Its optional name argument only recognizes
a spell referring to its own printed name rather than `this spell`. An
unrecognized additional-cost clause yields no casting option and a coverage
warning, including effect-authorized casts. Do not silently grant a free cast.
Branch combinations are bounded to 32. Missing/ambiguous grammar is not guessed.

Existing branch IDs such as `base_discard` and `base_sacrifice` remain usable.
Method readers preserve bestow, escape, flashback and prototype identity when
additional-cost suffixes are present; the chosen branch does not become a new
casting method. Legal views expose parent groups and eligible payment cards.
Both-seat controls already support selecting the required number of cards.

Actual AI materialization compares resource-loss estimates within one parent
group. Fixed life payments receive a simple low-life penalty; a known lethal
life branch is not selected over an available nonlethal sacrifice branch.
This is not general racing analysis, optimal payment sequencing, or expert AI.

## Canonical evidence

`backend/tests/fixtures/spell_additional_costs.json` retains Scryfall/Oracle IDs
and source URLs for Cathartic Reunion, Tormenting Voice, Raze, Deadly Dispute,
Ruthless Disposal, Final Payment and Goblin Grenade. The last is deliberately
unsupported because a Goblin subtype requirement must not become a generic
creature sacrifice. These fixtures are not additions to competitive decks.

`backend/tests/test_spell_cost_clauses.py` checks both seats, normal/free counted
payments, target-bearing land/life casts, mixed resource costs, grammar rejection,
AI choices, stable method identity and HTTP/database rejection atomicity.
Grammar-only syntax tests do not invent playable cards. They do not certify every
effect of every canonical fixture, particularly conditional or dynamic payoffs.

`frontend/tests/browser-cast-payments.mjs` adds six real App/API cases: both seats,
ordinary/free two-card discards and land sacrifice. It verifies button gating,
selected payment, mana behavior and refresh, in addition to the prior eight
Bone Shards scenarios. Runtime contracts check the parent-group shape.

## Known Limitations and Next Upgrades

Validation on 2026-10-03: 3,801 isolated full-suite tests passed (297 warnings,
621.71 seconds), plus the later final 214-case focused run (six warnings,
6.69 seconds), which includes three additional tests and corrected fixture mana
shape added after the full run started. Production application files are
byte-identical across those runs; tests and browser fixtures were extended.
This used the installed venv, not a fresh dependency install. Frontend lint,
unit/contract tests, build and final full Chromium pass, including all six new
cases and existing eight payment cases, natural BO3, refresh and process restart.

The Master four-template, twelve-logical-sample matrix ran each sample twice
(213.973 seconds) with no timeout, anomaly, drift or determinism failure. Eight
additional seeded Tempo/Dimir and Tokens/Ramp games in both seat orders finished
in 13-53 turns without invalid cost/target log lines. Available quality counters
are zero; some blocking/removal measurements remain null/unavailable, not passed.
The samples are too small to measure balance or seasoned-player competence.

Evidence, canonical API snapshots, superseded failed test runs and source are
preserved under RCHFiles at
`diagnostics/spell-cost-clauses/20261003T100446Z/`. The new browser fixture initially
omitted zero mana colors and failed the snow-pool contract; it was corrected
without relaxing validation. A new AI test initially reversed helper arguments,
and one test command referenced a nonexistent test filename. Those are recorded
test-harness errors, not hidden application failures.

- Fixed subtype and color-qualified sacrifices now have
  [canonical acceptance](qualified-spell-costs.md). General qualified intersections,
  type/color-changing layers, exile/reveal/return/tap costs, variable discard or
  sacrifice counts, and different-type mandatory sacrifice components need a
  richer resource model; the clauses exercised here are rejected explicitly.
- Alternate X-life branches, arbitrary optional additional costs and interrupted
  payment continuations remain unsupported.
- Kicker price options alone do not implement kicker conditional resolution;
  implement payment and effect semantics together, including free-cast behavior.
- Fixed execution ordering and legacy automatic resource selections remain as
  documented in the payment-selection milestone. Activated-cost selection and
  arbitrary additional-cost wording are separate work.
- Small seeded tests cannot establish unrestricted Magic correctness, tournament
  strength or matchup balance. Null quality measurements are not passed gates.
