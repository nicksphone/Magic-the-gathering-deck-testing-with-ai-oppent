# Selected mana parent composition

This is isolated integration evidence, not a live deployment or general Magic
rules/AI certification. The source base is `d88dbf0`.

## Dependencies

- Produced-type/mandatory-base predecessor: `combined.patch`, SHA256
  `08510478b442d43bfd0246ea7fe84d929736784e752fb2091d142f54eded68d1`.
- Final executor, including the explicit-null guard: `executor-final.patch`,
  SHA256 `536dd9f888f35c492d1cd92f11d540290bee4c78dae594098554cc6dd5495537`.
- Parent subtype-sacrifice parser: `costs-only.patch`, SHA256
  `77996ffb20cefa95ceaffc775d8aa46514ca5450d2e70c561414d6ad90e181a0`.
- Final caller: `selected-mana-caller-final.patch`, SHA256
  `a8c5f8ce94ba32861a0c6cea5db7600524e9e6ccd56be99b00d8f97c22a99105`.
- Parent fixed-count spell payment reservations: `engine-spell-reservation.patch`,
  SHA256 `732707f6b014f4f8890bdf1690cdb3a45030412a699d4f4185cab9a6d3c42925`.
- Separate guarded no-priority untap transition and regression fixtures.

The original caller patch `33685c7975f936e019391bdee3e2efdcbeb32ecc8489e0d215df542c01d3760f`
remains immutable. Apply either the final cumulative caller or the staged caller
plus its final incremental delta, never both. The parent candidate's three mana
source files were byte-checked against the frozen executor final-source manifest.

## Observed checks

- Selected training actions, checked HTTP, null resources and base-vector atomic
  execution: **141 passed**, 12 warnings, 56.30 seconds; no excluded or expected
  failures. All 12 HTTP cases ran, including both seats, mixed vectors, invalid
  choices, complete state/database preservation and snapshot recovery.
- Actual AI Deadly Dispute/Tower and Goblin Grenade/Prospector casts preserve their
  declared additional-cost victim and use a distinct mana-payment resource.
- Parent updated capability regressions: **66 passed**, 107.47 seconds. These
  replace obsolete unsupported-resource expectations with positive execution
  while retaining missing/invalid-choice rejection and root purity checks.
- Combined final source: **348 passed**, 22 warnings, 185.55 seconds across 12
  modules, including the above selected actions/capabilities, actual AI spell
  payment, guarded untap progression and enabled production Suspend hooks.
  No skips, deselections or expected failures.
- Larger 61-module neighbor gate: **2,533 passed**, two classified pre-existing
  Song of the Dryads type-layer expected failures, 89 warnings, 582.06 seconds.
  No ordinary failures. This source predates the public choice-hint increment.
- Public choice-hint composition: **145 passed**, 12 warnings, 76.04 seconds.
  This validates typed API actions and declared spell reservations, not every
  consumer of whole legal-move presentation hints.
- Added parent subtype parser fixtures on the public-hint source: **21 passed**,
  1.10 seconds.
- Earlier spell/casting-resource neighbor gate: **550 passed**, 22 warnings,
  38.08 seconds. This predates the final caller composition; it is not a claim
  that those modules ran on the later source.
- Guarded untap/Suspend composition: 196 passed plus 12 separately enabled
  production AI hook checks. These predate final caller composition as well.

Overlapping counts are not a single aggregate suite. Initial incorrectly shared
scratch-database runs and a missing isolation-environment setup failure remain
archived; authoritative reruns serialize database-writing tests and explicitly
declare their disposable local source root. The live database was not used.

## Payment semantics

Fixed-count additional discard/sacrifice selections are retained before automatic
mana payment and supplied as reserved card IDs. The same selections are paid
after mana activation. A selected permanent may still provide tap mana when
legal; it must not be sacrificed to a mana ability and then spent again.
Exhaustive discard-all/sacrifice-all costs retain their post-mana selection behavior.

Explicit output vectors identify complete offered **base** production, before
replacements and triggered additions. An explicit color must be a positive base
anchor. Bare ambiguous filterland colors reject; omitted vectors retain the
qualified legacy final-color behavior. No X-production support is asserted.

## Remaining release checks

- Preserve the two classified type-layer limitations as open work; do not label
  the entire rules engine complete from this passing bounded gate.
- Whole public legal-move training intents currently reject `required_choices`,
  a new presentation field missing from the adapter allowlist. Both-seat probes
  preserve the root state. A separate consumer correction is still pending.
- Public actor-only resource/hybrid hints and actual human UI choices for both
  seats; opponent-private candidate IDs must never leak.
- Full-hand source-free mana performance, including the stopped Prospector
  reproduction. Tactical runtime does not certify full-hand performance.
- Existing broader type-layer limitations, other-creature tap costs and secondary
  triggered-mana choices remain outside this qualified increment.
- Current-source browser/build/lint gates, consistent backup, then deliberate
  promotion. No live promotion has occurred at the time of these checks.

Cold evidence lives under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/spell-reservations-d88dbf0/`.
