# Static Aura Control-Layer Handoff

## Immutable Inputs

The single aggregate `AURA-CONTROL-LAYER-OVER-bf9.patch` was prepared over
`bf9f268e2ecd5bee237e99ecd6c81f8e0385b14e`. It was subsequently applied once
over `58c34d095737b5d9f42a9d50c6ffa1ba270d7e6a`, after independently proving
the complete backend tree and all existing-file preimages equal. The packet
is already present in this composition; do not apply it again. Its file-level
pre/post SHA256 and Git-blob pins, and verification receipts are at:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/static-aura-final-bf9-20261009-zebobQ/`

The frozen executed source was composed over
`c0528c8e01d63022fbde46d769918fbf08373b22`. Git objects prove that both commits
have the same complete backend tree:
`e62f844402886723798dfde94dc7b1e5d5a33263`. The later ordering review changes
only `control_layer_view`, corrects one NEW packet test's mistaken dependency
golden, and adds a NEW regression module. All other packet production/test and
canonical fixture bytes are retained. The frontend/browser changes are retained.

Original V2 product SHA256:
`a0f33ff2edef8a414e71a5649d80e25c4338bcd2373948b4d30045b5778e7149`.
Original V2 new-only tar SHA256:
`21ee708be6fdfabd621f701b89ee57c55cacd907e66c63ed39239c06bdd2b13b`.
The original packet's `backend/rules_engine/control_effects.py` SHA256 is
`366fb213fc757c8f8cc8fe0054c6f264d2979ac988efc90f6f24bd8bc73c54c1`;
the reviewed final module SHA256 is
`28ac2ee7b02c951bae3dbc92f095d90eb478aaa5528a6bff4817d6bda9752946`;
canonical Aura facts SHA256 is
`27c507f0e9aafc8fc68d3d8c7267833223031eaaf6e690fbbe63a582af5ff2e3`.

## Surgical Production Scope

Five existing files change, confined to seven functions and two dataclass fields:

| File | Owned change |
| --- | --- |
| `backend/effects/handlers.py` | `change_control` |
| `backend/game_state/serializers.py` | `serialize_match_snapshot`, `deserialize_match_snapshot` |
| `backend/game_state/state.py` | `CardInstance.reset_zone_counters`, `CardInstance.move_to_zone`; new `control_effect_base`, `control_effects` fields |
| `backend/rules_engine/engine.py` | `RulesEngine._revert_expired_control_changes` |
| `backend/rules_engine/state_based_actions.py` | `apply_state_based_actions` |

The sixth production path is the NEW control module. Its final correction over
V2 changes only `control_layer_view` and `expire_control_effects`; all other
function ASTs remain exact. The subsequent ordering correction changes only
`control_layer_view`. No preexisting committed tests are replaced. Seven NEW
repository test modules, one NEW canonical facts fixture, and this NEW document
are in the final composition. Do not also apply V2, V3,
`INCREMENT-OVER-V2.patch`, or extract a separate test tar on top of it.

## Invariants

- Admission is a complete two-line printed body: matching enchant selector and
  `You control enchanted <selector>.`; no card-name dispatch or partial clauses.
- The layer-two view is read-only. It does not call later-layer ability/type
  queries or mutate a root while inspecting legal moves or effective properties.
- Retained explicit underlying control is not guessed from owner. Timestamped
  effects are tied to battlefield incarnation and zone-change sequence.
- Only an actual change to an Aura source's controller creates a dependency.
  Dependencies are recalculated after every effect application. The oldest
  member of a still-active dependency loop must wait for external prerequisites;
  later loop members cannot bypass it. The retained official receipt covers
  CR 613.8a-c; the implementation's dependency relation is bounded to this body.
- Reconciliation occurs at existing mutation/SBA boundaries. A real controller
  transfer updates the physical battlefield lists once, readiness/entry turn,
  and the existing `control_changed` event, preserving owner and object identity.
- Expiry validates every card ledger, including noncache cards, before pruning
  any ledger/cache or changing controller/list/event state.
- Zone departure/reset clears old control metadata. Existing event/cache cleanup
  remains authoritative; no speculative producer/reference rewrite is added.
- Snapshot restore validates both internal control fields and the retained
  duration ledger before temporary-cache integer coercion. Legacy states without
  temporary control keep absent-field defaults. Old unscoped temporary-control
  snapshots are explicitly rejected, not inferred or advertised as compatible.

## Frozen Evidence And Findings

Exact reports, ledgers, denial canaries, runtime/source closure, and complete
source evidence remain immutable at:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/static-aura-current-c052-union619-20261009-kflafzp1/`

The actual native-denied pure gate ran 34 whole modules: 619 collected, 619 call
passes, no failures/skips, wrapper 0, pytest 498.42 seconds. Setup and teardown
reports also passed. No SQL/browser/network/child permissions were widened.
The 900-second bound, 16 MiB evidence bound, 3 GiB + 128 MiB admission and 3 GiB
live floor are historical gate controls, not a new browser execution claim.

The historical packet retained the exact same 20 witness assertions:
recorded 12 FAIL / 8 PASS before and 20 PASS after correction. Eight faults prove
expiry rejects a late noncache malformed ledger before any root write. Twelve
goldens used three canonical Confiscate Auras, both seats and all six entry
orders. Later review established that their controllers include a no-op edge,
so they are NOT a genuine dependency loop and the old timestamp expectation
was wrong. Their historical source and passing ledger remain immutable, not
evidence of that expectation's correctness. The final NEW test retains every
query-purity assertion and expects the actual opposing-controller chain.
These are controlled queries, NOT paid cyclic attachments or natural gameplay.
The separate two-Aura dependency test
uses genuine paid casts, cold restore, and bounce departures in both seats.

The original Dominate -> Ray of Command -> owner Cloudshift -> cold restore ->
cleanup paid reentry episode already passed in both seats before the V2 review
correction. Suspected stale-cache theft was not reproduced. Historical prototype
and probe-authoring failures are preserved, not recast as product failures.

Fresh handoff verification checks aggregate forward/reverse application, exact
postimages, complete backend equivalence, unrelated-file preservation, AST scope,
and frozen ledger/archive readback. The 619 gate is NOT rerun or relabeled as a
new bf9 test run because the executed production/test bytes are unchanged.

## Historical Parent Verification

The separate current-parent check uses an isolated source-only copy of
`58c34d095737b5d9f42a9d50c6ffa1ba270d7e6a` plus the same aggregate. All fourteen
applied production/test/fixture/document postimages were verified against the
frozen packet in both the parent and owned copy before execution. The actual
six complete new test modules collect and pass 73 cases, with two warnings,
in 271.36 seconds, exit 0 within the 300-second bound. Source before/after
hashes are equal and the native SQL/socket/subprocess attempt ledger is empty.
This run did not execute separate denial canaries; its evidence does not claim
an additional installed-control qualification or transfer child permissions.

The raw log, JUnit, receipt and full source maps are at:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/static-aura-applied-current-58c34-20261009/`

The verified reboot checkpoint retains the same bytes and terminal evidence:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/reboot-pause-20261009-cOt2ci/`

This 73-case run preceded the final ordering review, and includes the same
incorrect three-Aura expectation described above. It and the 619-case run are
immutable, distinct overlapping ledgers, not a summed suite or a substitute
for final corrected-source qualification. The protected parent DB is unchanged.

## Final Ordering Review And Qualification

Two independently reviewed defects were reproduced before correction: a no-op
source-control effect incorrectly created a dependency, and a later member of
a true loop bypassed its externally blocked oldest member. The first new
four-case module produced 2 FAIL / 2 PASS on the original packet. The expanded
52 cases produced 26 FAIL / 26 PASS on that same production source. After the
first correction, 52 passed, but the next two external-prerequisite regressions
still failed. The final correction passes all 54 unchanged desired regressions.

The complete final seven-module cohort passes 127 cases, two warnings, in
276.35s, exit 0 within its 600-second bound. JUnit records no failures, errors
or skips. Source before/after hashes match; native SQL/socket/subprocess attempts
are empty. There were no separate denial canaries, SQL/browser executions,
child-frame qualifications or dependency installations in this run.

The 48 four-Aura loop orders, four source-change/no-op cases and two external
prerequisite cases use complete canonical cards and real allocated timestamps,
but explicitly controlled boards/retained ledgers, not paid or natural loops.
Independent static review found no remaining blocker in the supported bounded
Aura/fixed-controller model. All other control-module function ASTs match the
original packet. Canonical facts and unrelated packet paths remain byte-equal.

Raw RED/GREEN ledgers, original mistaken golden bytes, final scope/review,
JUnit, source maps and the three-path correction are retained at:

`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/static-aura-dependency-review-20261009-jgB6dA/`

`CORRECTION-OVER-FROZEN-AURA.patch` SHA256:
`d79c34673c94945011981be4b6d3831656ab039d21513c1efb7a74eedf920aed`.
Apply it only after the original aggregate, not on an already corrected tree.
The parent production/test postimages equal the final executed candidate.

## Integration And Limits

In a separately owned checkout pinned to the base, first inspect `MANIFEST.json`
and verify packet `SHA256SUMS`. Apply the aggregate and correction once:

```sh
git rev-parse HEAD
git apply --check /path/to/AURA-CONTROL-LAYER-OVER-bf9.patch
git apply /path/to/AURA-CONTROL-LAYER-OVER-bf9.patch
git apply --check /path/to/CORRECTION-OVER-FROZEN-AURA.patch
git apply /path/to/CORRECTION-OVER-FROZEN-AURA.patch
graphify update .
```

The handoff agent never writes or applies anything in the read-only parent.
Graph refresh for this packet uses a separate owned AST-only projection; no
parent/generated graph hunks are included. An integrator owns the eventual
parent composition and graph refresh.

This is pure in-process qualification, not a serializer-child, mixed HTTP/SQLite,
browser, natural-AI, or full-release certificate. The historical 52 genuine
serializer-child denials remain unqualified. No SQL/browser/vendor fixes,
dependency installs, event rewrite, or unrelated engine repairs are shipped.
The main agent's browser-CI investigation remains separate.
