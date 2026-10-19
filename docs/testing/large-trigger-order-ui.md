# Large Simultaneous Trigger Orders

Source baseline: immutable `2678d4e720abd5f4f45f8dfe03c42b9442bb5d3b`.

The backend enumerates every order for at most six triggers, but emits only the
natural order above six. Its validated choose_trigger_order action accepts every
complete permutation of that group's public IDs. The previous UI exposed only
those enumerated buttons, so a human could not choose other legal orders for a
large group.

Controls now renders a manual picker above six triggers. Human clicks select
bottom-to-top order; the last chosen trigger resolves first. Submission requires
every offered ID exactly once. Undo/reset never submit. Match, revision,
controller or group changes remount the draft. Existing small-group shortcuts
and backend/API/schema rules are unchanged. No trigger or target is inferred.

## Observed Checks

- The NEW actual-Controls regression fails on the old UI and passes after repair.
- Both seats: an actual paid canonical Prodigal Pyromancer enters beside seven
  trusted-board nonlegendary Soul Wardens. One public order is offered; a reverse
  non-enumerated order passes strict validation, survives snapshot roundtrip,
  produces the selected source ordering and resolves seven real life-gain triggers.
- Wrong seat, missing, duplicated and unknown IDs reject through validation with
  unchanged full snapshots. No injected stack item/pending group or Oracle rewrite.
- Actual compiled picker callbacks: reverse order, stale duplicate click,
  incomplete submit, undo/reset; Controls reset keys and absent/small-group boundaries.
- Final complete configured npm test, lint and build exit 0 using the existing
  Node dependencies and hash-locked H2 Python interpreter. No new dependency.

These are source-isolated component and backend protocol checks, not a mounted
React or browser certificate. The seven-copy starting board does not certify a
natural deck/game or every trigger/APNAP combination. Final browser acceptance
remains required.

Evidence: mounted NFS `parent-integration/large-trigger-order-ui-qualified-20261008/`.
