# Shutdown Fixture Compatibility

On immutable `4e7aa7e`, the unchanged whole
`test_simulation_engine_shutdown.py` module reached the actual AST-extracted
lifespan and failed all three cases because its fake namespace lacked the
Stage2 `DatabaseOwner` contract. This was test-fixture incompatibility, not a
demonstrated failure of native shutdown.

The fixture now supplies a clearly fake owner, capacity initializer and shutdown
deadline. Its owner closes the existing fake engine only when the actual lifespan
calls close. Every original test-function AST, including all assertions, is
unchanged. No production lifecycle, database, job or cancellation code changed.

The repaired module and unchanged capacity-lifecycle-policy module passed all
24 cases in 1.03 seconds. A native audit denied SQL, network connections and
child creation before imports; only constructor-attributed asyncio AF_UNIX
self-pipe sockets were allowed. The original strict-socket-policy failure and
subsequent original three namespace failures remain separate archived ledgers.

Evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/simulation-shutdown-fixture-20261008/`.

This is pure fixture and lifecycle-order qualification. Actual abrupt-process
termination, cold recovery, resource escrow reconciliation and final combined
operational acceptance remain separate requirements. It does not extend the
native 257-case storage qualification into a crash/soak certificate.
