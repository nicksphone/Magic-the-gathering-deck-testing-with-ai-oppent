# No-Priority Untap Progression

## Root Cause

On tracked `433b230`, `main.autoplay_tick` submitted `checked_action` with
`pass_priority` for every empty human window. At untap, the move generator
correctly returns no player actions. The action validator therefore rejected
that fabricated pass before reaching the legacy engine untap special case.
The original unit and shared browser gate reproduced this at `main.py:893`.

Manual Next Step is also a player pass, not a raw `RulesEngine.next_step` call:
App submits `api.act(..., pass_priority)` for human seats and one autoplay tick
for AI seats. Controls disables human Next Step without a legal pass. This
candidate leaves that contract, the action validator, and frontend unchanged.

The engine's `next_step` performs step-entry actions when entering a step.
Natural cleanup-to-new-turn progression untaps and continues directly to
upkeep. Pregame completion likewise performs untap entry before progressing.
The low-level legacy `take_action` had an untap pass shortcut, but that is not
permission to publish a player pass as legal. Retained untap snapshots and the
browser fixture need an internal transition, not an external action exemption.

## Proposed Fix

The separately delivered `proposed-transition.patch` adds a narrowly guarded
`RulesEngine.advance_no_priority_step` and calls it before either controller's
autoplay action selection. The hook only ends an already-entered untap step.
Pregame, winner (including draw), any pending choice/order and any stack object
block it. Other steps are refused without mutation. It delegates to existing
`next_step` and stops at upkeep, the first response window.

Untap entry is not reapplied: doing so could consume a second stun counter on a
still-tapped permanent. Upkeep events, day/night work, triggers and ordinary
step bookkeeping use the existing engine transition. The following autoplay
tick uses existing response checks and checked player actions. Draw uses its
ordinary step-entry action exactly once; the hook does not advance draw or
resolve a stack. No broad bypass of validation, stack/choice resolution, AI
selection, mana or legal response opportunities is added.

The existing coordinated API wrapper owns mutation locking, revision checks,
rollback, idempotency and persistence. The hook is internal and is not a new
HTTP/player action. Explicit human passes at untap remain HTTP 422; AI-seat
manual actions remain HTTP 403. No changes to `action_validation`, mana,
frontend, CI, schema or AI policy are included.

## Regression Checks

New `backend/tests/test_no_priority_progression.py` uses existing canonical
fixtures: Island decks, Grizzly Bears, Think Twice and Phyrexian Arena. It tests
both seats, snapshot restore, no second stun consumption, natural turn entry,
all guard refusals, manual-action memory/database immutability, human/AI
one-tick API transitions with player-action/AI-query spies, idempotent retry,
upkeep trigger plus payable response preservation, automatic single draw and
land stop, and an opponent draw response without another draw or advance.

The stack guard uses an actual checked Think Twice cast; pending guard sentinels
are deliberately not executable choices. The new module refuses execution
from a tracked source root, preventing its API fixture from opening tracked or
live SQLite. Execute tests only from a disposable local source copy.

The main venv was verified against every backend requirement pin. System
Python packages differ and were not used. No dependency installation or paid
service is required. Baseline reproducer failed; candidate qualification
passed 184 tests across these modules:

```sh
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q \
  tests/test_no_priority_progression.py tests/test_human_auto_progress.py \
  tests/test_next_turn_draw.py tests/test_api_input_contracts.py \
  tests/test_pregame_priority.py tests/test_priority_stack.py \
  tests/test_priority_stops.py tests/test_cleanup_choices.py \
  tests/test_cleanup_hand_size.py tests/test_named_counters.py
```

The ordinary unchanged browser harness copies tracked/untracked regular source,
excludes caller SQLite/dependency directories, owns its loopback ports/process
groups, and creates fresh local SQLite and Chromium profiles:

```sh
MTG_TEST_PYTHON=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/existing/local/frontend/node_modules \
MTG_KEEP_TEST_ARTIFACTS=1 bash frontend/tests/run-browser-ci.sh \
  browser-auto-progress.mjs browser-start-recovery.mjs
# Separate fresh harness invocation for the complete shared gate:
MTG_TEST_PYTHON=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/existing/local/frontend/node_modules \
MTG_KEEP_TEST_ARTIFACTS=1 bash frontend/tests/run-browser-ci.sh
```

The focused browser run passed. The complete unchanged shared gate exited 0
with 484 PASS lines, including its three natural BO3 modes and committed
Officer/Cathar epilogues (six controlled Cathar cases, not later parent cases).
Executed outcomes are recorded in the verified evidence archive. This
qualifies this frozen backend proposal, not
parent's staging, later composed frontend/CI wiring, all-rule support, or every
AI loop. The hook relies on the engine's step-entry contract; it is not repair
for fabricated snapshots that omit turn-based entry actions.
