# Day/Night Turn Boundary

Isolated delta over the frozen optional-reveal source archive
`a7b1615732cbaa3e4447d0f7d6b29c840b6f9a7307ac82f69dc6000dcee69e53`.
The earlier Delver product, tests and actual-App ledgers are dependencies,
not duplicated or modified by this patch.

## Rules And Scope

Official Comprehensive Rules effective September 25, 2026:
<https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt>.
CR 731.1 and 731.2c: no day/night designation is invented from spell counts.
CR 502.2-4, 503.1a and 731.2a-b: check the previous active player's spells
before untapping; keep resulting triggers until the upkeep priority window.

Only `RulesEngine._apply_step_start_actions` and `_update_day_night` change.
Remove spontaneous neither-to-day/night transitions and move the existing
designation check before untapping. Existing durable trigger staging carries
untap triggers through snapshot restoration and combines them with upkeep
triggers before publication. No new state/schema fields or event/helper edits.
Existing canonical daybound entry establishment and batched transforms remain
unchanged. No card-name dispatch, hidden-library inspection or fixture fact edits.

The NEW canonical test reuses committed Cathar, Delver, Shock and land records.
Both seats cover neither/day/night and zero/one/two previous-active spells,
nonactive-player counts, dawn/night before untapping, deferred target choices,
source incarnation, restored untap continuation without repeated entry actions,
daybound entry, designation persistence after departure setup, and Delver upkeep.
Explicit timing positions are not claimed to be natural played histories.

## Commands

Run backend API regressions in a disposable local source-only copy without
`.git`, DB, cache or dependencies. Never copy the live database.

```sh
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q \
  backend/tests/test_day_night_turn_boundary.py \
  backend/tests/test_optional_reveal_transform.py \
  backend/tests/test_transform_numeric_ai.py \
  backend/tests/test_cathar_day_night_linked_exile.py \
  backend/tests/test_top_card_choices.py \
  backend/tests/test_activated_top_selection.py \
  backend/tests/test_opaque_selection_http.py \
  backend/tests/test_trigger_target_choices.py \
  backend/tests/test_no_priority_progression.py \
  backend/tests/test_human_auto_progress.py

MTG_TEST_PYTHON=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/home/nick/mtg-deck-testing-lab/frontend/node_modules \
MTG_HUMAN_TRANSFORM_ARCHIVE=/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/day-night-global \
node frontend/tests/browser-delver-repair.mjs
```

The existing full12 runner and every assertion are unchanged. It imports and
casts real canonical cards through actual App/checked HTTP actions in both seats,
restarts the backend, restores snapshots, inspects private choices and rejects
stale actions. No global failure is excluded, xfailed or hidden behind a warning.

## Limits

Two-player ordinary turn progression, not shared-team/extra/skipped-turn support.
Existing phasing, explicit day/night-effect coverage, keyword suppression,
unusual nightbound-only establishment, and AI optional-reveal policy are not
newly implemented or certified. This repair does not expand those families or
make a corpus-wide card support claim. Privacy remains the earlier scoped owned
choice/DOM/legal-view guarantee, not new hotseat authentication.

Frozen terminal report and private runtime evidence supply exact source hashes,
assertion parity, gate totals and cleanup receipts. No main/live deployment.
