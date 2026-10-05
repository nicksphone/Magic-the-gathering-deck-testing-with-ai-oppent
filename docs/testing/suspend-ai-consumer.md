# Bounded Suspend AI Consumer

The policy and actual `agent.py` hooks are integrated with the engine and human
controls. Parent composition against `e4d8aa8` passes 892 backend checks, ten
real-HTTP AI cases and ten actual-App browser cases, including both seats and
restart/replay. The original isolated policy evidence below remains historical;
it is not a claim of arbitrary-card support or optimal timing.

## Consumer Contract

The hook removes `suspend` from ordinary move ranking, considers it only after
existing planning and idle Foretell return pass, and dispatches `suspend_cast`
before generic mechanic selection. Without the last hook, the production agent
looks up the literal `decline` as a card ID and raises `KeyError` on both seats.

The policy uses a private decision view, copies for materialization, complete
typed actions, and checked engine admission. It never reads unseen Oracle text
or predicts a particular draw. Existing public/opaque settlement and position
evaluation compare each admitted optional cast against an admitted decline.
Printed mana waiver, additional costs, taxes, prohibitions, target legality,
resolution and pending cleanup remain engine-owned.

Idle investment preserves selected ordinary plays and every currently affordable
hand counter/removal payment. It avoids an affordable normal cast of the same
card, nonpositive value/savings, low life, public creature power at least our life,
and investments whose current turn plus delay exceeds nine. The pressure guard
is deliberately conservative, not a lethal-combat proof. Long-delay and late-game
optimization are not certified.

Optional casts enumerate actual offered cost options and single player/creature/
permanent/planeswalker targets. Existing materialization supplies more complex
choices; unsupported or unsettled continuations decline, not pass or auto-choice.
An offered X cap of zero is explicitly announced as zero. No canonical fixed
Suspend printed-X card is qualified by this gate. Multi-target/mode exhaustive
search, adversarial responses and arbitrary Suspend variants are not certified.

## Focused Gate

Canonical unaltered backend fixtures: Rift Bolt, Errant Ephemeron, Ancestral Vision,
Aeon Chronicler (unsupported variable-Suspend control), Drannith Magistrate and
Ivory Mask. Existing canonical Counterspell, Thalia, Stifle and Grizzly Bears
fixtures provide reservation, tax, countered-trigger and pressure controls.
Explicit upkeep fixtures exercise rules continuations, not historical games.

Both seats cover useful cast/draw/creature and haste, ordinary-cast preservation,
insufficient payment, taxes, prohibition, no target, unfavorable self-burn,
late delay/race, countered last-counter trigger, hidden-library-order invariance,
root and legal-move immutability, snapshot replay and fresh Python-process replay.
Production probe configuration is `strong`, `Midrange`, opponent `Aggro`.

From an isolated checkout with backend delta, policy patch and reviewed hook:

```sh
cd backend
MTG_SUSPEND_HOOK_PROBE=1 /path/to/external/venv/bin/python -m pytest -q \
  tests/test_ai_suspend_policy.py tests/test_ai_suspend_hook_probe.py \
  tests/test_suspend_lifecycle.py tests/test_ai_action_contract.py \
  tests/test_ai_selection_activation_policy.py tests/test_ai_information_boundary.py
```

Without the separate agent hook, omit `MTG_SUSPEND_HOOK_PROBE`: direct policy tests
run and production-hook tests explicitly skip. This is not deployment qualification.
No live actions, database access, engine changes, coverage flags or NN claims.
