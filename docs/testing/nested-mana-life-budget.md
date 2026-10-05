# Nested Mana Life Budgets

## Canonical Failure and Shared Repair

Two Mana Confluences can pay Erebos's mana cost by spending two life. With only
three life available, the remaining two-life activation cost cannot also be paid.
The previous availability query counted only the outer cost, and execution
accepted the activation after an unchecked life-payment failure. Both seats
reproduce: four failures, two correctly funded controls.

Shared mana planning now accounts for printed numeric life cost per selected
source, carries protected life across nested mana activation/funding, and keeps
outer Phyrexian and explicit life costs reserved. Ordinary and snow branches
track cumulative expenditure; generic/color branch symmetry includes life price.
Painless alternatives are preferred/searchable instead of rejecting all choices.
Availability queries remain read-only; impossible tested payments reject before
authoritative mutation. Actual activation life payment must succeed.

Protected outer life is distinct from the current operation's own reserved life,
so a nested mana ability does not misattribute an outer cost to its payment
context. Query, planning, preferred ability selection and execution use the
same protection. Paying exactly the available life is still legal where allowed;
this is not a new rule that life must stay above zero.

## Observed Evidence

- Initial six canonical cases: four failures/two passes before the repair.
- Initial repair selection: 321 overlapping checks pass.
- Extended first invocation: 214 passed/two failed because the new explicit
  Phyrexian test omitted its required base cost choice; corrected test payload,
  not production validation. Latest selection: 505 checks pass.
- Latest selection covers alternate Swamps, generic costs, Phyrexian costs,
  snow costs, nested Cabal Coffers funding, existing cost/life/resource tests,
  and nonlethal AI materialization in both seats/ten archetype labels.
- Four new HTTP tests verify underfunded rejection before/after SQLite restore,
  actual funded payment, and exact paid-stack restore.
- Six focused browser cases pass: four new low/funded life cases in both seats
  and the two preceding deliberate joint-resource scenarios.
- Exact frozen runtime `e02adbe765037e2956549a566123212c215f55a0` passes
  8,209 tests across all 332 recursive files. Each file ran once; all four
  isolated sources match 649 backend/fixture hashes and started without a DB.
- Complete browser qualification passes, including natural AI, human-vs-AI
  and human-vs-human BO3. Frontend test/lint/build gates pass. `c56c50f` only
  removes executable file modes; runtime/test bytes remain unchanged.
- A paired-seed Drain/Tribal replay is still running; it is not evidence of
  completed broader decision-quality analysis or expert-level play.

Mana Confluence and Snow-Covered Swamp fixtures retain unchanged raw Scryfall
responses, URLs, retrieval times and SHA-256 provenance. Erebos, Dismember,
Viscera Seer, Swamp and Cabal Coffers use existing canonical fixtures. States
are crafted acceptance positions, not competitive decks or balance samples.

## Remaining Limits

The source-output model still exposes the largest output per color, so wider
tradeoffs between different output amounts/costs on one source require explicit
coverage. Mana effects that alter subsequent cost restrictions, ability grants
or resource availability need broader dynamic projection tests. Other complex
cost grammar, deliberate mana/cycling/ward payments, strategic life valuation
and real-game decision-quality/performance evidence remain open. No arbitrary
MTG or expert-AI certification is implied by these fixtures or test counts.

Evidence is stored on verified NFS under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/life-conversion/20261005-candidate/`.
