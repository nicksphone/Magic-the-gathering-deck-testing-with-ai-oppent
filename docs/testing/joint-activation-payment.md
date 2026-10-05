# Joint Activation Mana and Resource Planning

## Reproduced Failure and Shared Repair

Trading Post with two Lotus Petals can pay its draw ability by consuming one
Petal for mana and sacrificing the selected other Petal. The previous planner
consumed the first resource without respecting the declared sacrifice, then
rejected that valid activation. Both seats reproduce: two failures/six passes.
These are unchanged canonical fixtures, not invented or balanced card data.

Shared mana APIs now carry reserved card IDs through free/paid source planning,
snow mana, speculative activation, ability selection and actual payment. Nested
activation costs cannot consume reserved resources. Tapping a selected Mind Stone
before sacrificing it is allowed; no blanket mana-source exclusion is applied.
Phyrexian Tower may sacrifice a different eligible creature while preserving a
reserved one. Availability queries remain read-only.

Automatic activation cost selection lazily tries resource combinations, retaining
legacy default ordering when payable. Explicit selections are never substituted.
AI tests its low-retention/loss selection for joint feasibility, falling back to
a feasible lower-loss combination; ranking reflects that feasible resource cost.
This is heuristic resource planning, not expert strategy or a complete cost solver.

## Evidence

- Initial engine repair: 276 overlapping selected checks pass.
- Engine/AI selection: 483 overlapping checks pass, including feasible payment
  materialization in both seats and four deck-style labels.
- Latest rules/API selection: 228 checks pass, including four new HTTP cases,
  atomic failed double-spend, pre-payment SQLite restore and paid-stack restore.
- Eight focused browser cases pass: two new selected-resource/mana/reload cases
  and the six existing deliberate discard/creature/artifact cases.
- Test invocation errors selecting nonexistent filenames ran zero tests and are
  retained, not counted. An initial HTTP fixture held a stale state reference
  after rollback; corrected to use the authoritative restored state, not patched
  around in production code.
- Full backend and complete browser qualification of this candidate is pending.

New Lotus Petal and Phyrexian Tower fixtures retain raw Scryfall responses with
URLs, retrieval times and SHA-256 provenance. Trading Post and Mind Stone use
existing canonical fixtures. Crafted positions are not natural-match evidence.

## Remaining Limits

Compound cost grammar, deliberate mana-ability/cycling/ward payment controls,
joint life budgets across nested mana production, arbitrary instructions and
richer sacrifice-trigger/impending-loss strategy remain open. Combination search
is lazy but may be expensive in resource-heavy boards; full regression and
real-game timing/decision traces must measure that risk. Independent source
choices whose effects alter later mana or resource eligibility require wider
golden coverage. No optimal-play, balance or arbitrary-card claim is made.

Evidence is kept on verified NFS under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/life-conversion/20261005-candidate/`.
