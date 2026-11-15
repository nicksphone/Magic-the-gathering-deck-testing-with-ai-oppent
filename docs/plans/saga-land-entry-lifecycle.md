# Land-Saga Entry Slice

Unapplied increment over Git `199b5842f89c0c5fc541190c61910adbd8bfefc0`.
The local source began as the exact 281-file immutable capture, verified against
both its manifest and Git. No moving shared source was edited.

## Product Boundary

The existing `play_land` preflight still validates source permission, timing,
selected face, quota, and the announced entry choice. Recognized Land Sagas now
prepare entry counters while off-board through `prepare_counter_entries` and
its existing typed pending/batch machinery. A private `land_play_entry`
continuation revalidates the retained object, face, timing, permission, quota,
and choice before committing the land and prepared counters. Physical lore
placement and chapter events remain owned by `commit_entry_counters` and the
existing counter/event code. No synthetic lore, event, or stack frame is used.

Ordinary land commit code is preserved byte-for-byte after dedenting its new
`else` branch. All previous entry-counter bodies and all previous registry
branches, including the LDA path, are unchanged. No schema, Oracle/parser,
chapter grant, token P/T, search, or AI changes are included.

## Observed Gates

- New entry RED: 4 FAIL / 12 PASS, after correcting only a test's Read Ahead
  action field to the actual `choice_id` ABI. The earlier harness/log-path and
  action-field failures are retained separately.
- New portable controls: 32 PASS, both seats. These cover real Land-Saga entry,
  both counter replacement orders, off-board pending state and snapshot/resume,
  Solemnity, ordinary shock-land payment, modal land face, native extra-land
  quota, graveyard/exile permission bookkeeping, and fail-atomic rejection of
  deliberately stale continuation snapshots.
- Genuine nonland Saga and Read Ahead entry controls pass unchanged. There is
  no fabricated Land-Saga-with-Read-Ahead fixture and no claim that such a new
  card family is independently qualified.
- Original identical 24-case module and full FACTS: BEFORE 22 FAIL / 2 PASS;
  AFTER 22 FAIL / 2 PASS. All 12 Saga cases now pass the old missing-lore
  frontier. Eight stop at missing Chapter I/II grants; four reach Chapter III
  and reject its overbroad printed-cost search. Ten Spelunking failures and
  two ordinary Cave controls are unchanged.

All completed native gates used CPU5, nice15, 2GiB AS, a 300-second worker
deadline, the original strong precollection fence with only its SOURCE literal
adapted, and an additional no-AI/model/encoder call monitor. Source/input pins
remained equal and guard denials were empty. These are controlled canonical
native entry tests, not gameplay/AI qualification.

## Portable Tests

The two new `backend/tests/test_saga_*entry*.py` modules in `PRODUCT.patch`
load full canonical card objects from `backend/tests/fixtures/saga_land_entry.json`.
They have no dependency on private audit modules, databases, network, models,
or captured gameplay. Run with the repository's normal pytest setup after
reviewing/applying the patch. The original 24-case private audit remains
outside the product patch and is byte-identical throughout.

## Remaining Frontier

Persistent generic Saga self-grants, Construct dynamic P/T, exact printed-cost
Chapter III filtering, and Spelunking are not fixed or qualified by this slice.
Shared Oracle/grant changes require the separate next-phase design/ownership.
