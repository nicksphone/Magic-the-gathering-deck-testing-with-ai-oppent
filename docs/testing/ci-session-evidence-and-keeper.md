# Evidence Writer And Keeper Fixtures

The two missing call-phase hashes in the `8b1bffa2` sanitized CI ledger match
the two unparametrized public `test_closed_http_runtime_callers` functions.
Those tests intentionally change the evidence environment variable until their
fixture teardown. The reporter followed that temporary value and wrote their
call records elsewhere. It now retains the original session directory for all
three writers. Existing symlink checks and completeness requirements remain.

A real regression runs both unchanged caller tests plus an intentional public
failure. The old reporter records six of nine phases; the correction records
all nine, including the original failure and its safe signature. Separately,
exact SQLite exception identities and allowlisted numeric codes now distinguish
errors without exporting exception messages, SQL or arbitrary error-name text.
The combined whole CI-script suite passes 138 tests in 15.088 seconds. This does
not establish the cause of the 532 hosted startup failures; snapshot cleanup and
production backup behavior are unchanged in this increment.

Six reproduced SBA test failures also came from an omitted human legend-keeper
decision. The fixture now chooses its declared keeper through the actual public
offer, preserving departure, owner, trigger and replacement checks. Its strict
resume tag follows the current `legend_keeper_die` continuation, not an alias.
The worker's five whole modules pass 136 cases; the independent parent passes
the original 26 plus four new proof cases in 56.94 seconds. Gameplay code is
unchanged. Earlier red and setup ledgers remain separate.

Private verified evidence is in the RCHFiles `diagnostics/ci` archives
`ci-session-root-parent138-20261012-orvcbtts`,
`sba-keeper-parent30-20261012-cirr8xkh`,
`current-28087-ci-sqlite-diagnostics-20261012-eShFG08W` and
`current-8b1-sba-keeper-testonly-20261012-I7D48Z37`.
Whole hosted backend qualification and strategic AI scoring remain open.
