# Deliberate Nonmana Activated Payments

## Qualified Scope

Ordinary `activate_ability` legal moves expose required discard/sacrifice counts,
eligible actor resources and mandatory source IDs. Typed `payment_choices` may
select those resources; omitted groups retain legacy automatic selection.
Checked actions reject wrong counts, duplicate IDs, foreign resources and
substitution for mandatory sources without changing authoritative state.
Selection is revalidated after mana payment rather than silently substituted.

Both human seats can select actual card IDs using activation controls. Required
source choices are locked; incomplete resource selections disable activation.
AI materialization selects mandatory sources plus lower-retention/loss resources,
and activation ranking accounts for resource/life cost. These are heuristics,
not an optimal planning or seasoned-player claim.

## Observed Evidence

- Initial 24-case pre-fix probe: 20 failures and four passes.
- Latest direct/API boundary selection: 80 passed, including six HTTP/SQLite
  reject/pay/restart cases. Earlier overlapping selections pass 237, 462 and
  255 tests; counts overlap and are not additive.
- Six focused browser cases pass: discard, creature sacrifice and artifact
  sacrifice in both seats, actual selected payment and paid-stack reload.
- Latest frontend unit/contract tests, lint and TypeScript/Vite build pass.
- Mandatory Mind Stone source costs, borrowed-permanent ownership and
  land-preserving discard materialization in ten archetype labels have direct
  tests. Crafted states are not competitive matchup evidence.
- Exact runtime `7bfaaa6bdeb4b839569a25ab46b8d05e16bec45d`: 8,133 backend
  tests pass across all 328 recursive files; 639 source/fixture hashes match
  in every shard. Complete browser harness passes, including all three natural
  BO3 controller modes. Initial test-copy databases were absent.

Existing unchanged canonical fixtures supply Mind Stone, Viscera Seer, Dismember
and Sacred Foundry. New Rummaging Goblin and Trading Post files are unchanged
Scryfall responses with retrieval URLs, timestamps and SHA-256 provenance.

## Remaining Acceptance

Deliberate payments for mana abilities, cycling, ward and other action families
are not part of this batch. More complex compound cost syntax remains outside
the supported parser. An explicit resource consumed by automatic mana planning
is rejected atomically. The separately qualified
[joint planner](joint-activation-payment.md) repairs the reproduced Lotus Petal/
Trading Post selected-resource ordering gap. The separately qualified
[life-budget planner](nested-mana-life-budget.md) repairs nested life reservations.
Sacrifice/death rewards, impending losses and richer strategic resource value
need deeper planning and actual-game evidence. This batch does not establish
arbitrary-card rules fidelity, expert AI, accessibility or network release safety.

Evidence is retained under the verified NFS diagnostics archive at
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/life-conversion/20261005-candidate/`.
