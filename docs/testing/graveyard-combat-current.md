# Current Graveyard and Public Combat Acceptance

Pinned application source is `1f31a72229c140ee1816f074069046efe1fd4c70`;
its application code is unchanged from Fable checkpoint `9437de9`. Tests ran on
an isolated Git source-only copy, not the retained/live worktree or a borrowed
SQLite database. Existing cached dependencies were reused, not freshly installed.

## Exact Whole Cohort

- `test_graveyard_inventory_feasibility.py`: 24
- `test_graveyard_self_activation_product.py`: 58
- `test_public_graveyard_inventory.py`: 109
- `test_public_combat_boundary_audit.py`: 132

Actual corrected terminal: **323 passes in 136.63 seconds**, exit 0. Independent
JUnit proves exact four-module membership and zero failures/errors/skips. All
recorded original backend hashes are unchanged during both executions. No
application, assertion, fixture or dependency changes were made for this gate.

The first whole run had 167 passes and 156 failures in 133.24 seconds. All failures
were missing harness evidence-directory variables: 24 inventory and 132 boundary
`KeyError`s. That complete log/JUnit remains archived. The same whole cohort was
then run with those two variables and the existing self-return trace variable
set to separate fresh owned directories; no tests were removed or adapted.

The pre-import runner denies native SQLite connection and socket events and
checks four denial canaries. This is Python audit/constructor isolation, not an
OS-level hostile-native-code sandbox or per-child nonce certificate.

## What This Proves

Current canonical graveyard self-return, non-targeting/source-incarnation checks,
entry/continuation controls, supported public graveyard inventory, native checked
combat damage/response/crackback controls and hidden-information boundaries pass
their existing bounded assertions. Prior reports' zone/entry failures and 40
combat-leaf failures must not be presented as current defects in this cohort.
This does not prove completeness for arbitrary graveyard clauses/layouts/grants,
general combat planning, natural games, expert AI or statistical decision quality.

No HTTP, SQLite restart, browser or live deployment gate was run. The outstanding
broader plan item remains open. Generated placeholder media is archived separately;
original-source equality is not a claim that no generated files appeared.

Evidence and both full execution ledgers:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/graveyard-combat-current-20261007/`.
