# Tick 302 Block Causal Review

The four-row natural-game run retained one `bad_blocks` diagnostic: row 0,
turn 11, defender seat 2. A bounded review reconstructed that real archived
decision on immutable `349a5d2`, without calling choose_action, replaying a game,
changing weights or suppressing the metric.

All four declared alternatives were legal and completed actual checked public
priority continuation through immediate combat:

| Declaration | Defender life | Sprite Dragon | Insectile Aberration |
| --- | --- | --- | --- |
| Actual: Aberration blocks Human, Sprite blocks Adeline | 18 | graveyard | battlefield |
| No blocks | 14 | battlefield | battlefield |
| Aberration blocks Human, retain Sprite | 15 | battlefield | battlefield |
| Swap the assignments | 18 | graveyard | graveyard |

Attacker life stays 19; Adeline survives and no line produces a winner. The
chosen chump preserves three life versus retaining Sprite, at the cost of that
creature. The existing metric detects a lost blocker against a surviving
attacker with a nonfatal no-block baseline; it does not prove strict domination
or certify optimality. Future racing and response branches were not evaluated.
The natural-game aggregate still reports `bad_blocks=1`.

## Verification And Limits

Independent artifact checking exited 0 for all four alternatives. The actual
declaration matches the archived post-declaration snapshot except diagnostic
logs. Root, agent/class cache, RNG, legal moves and private card identities are
preserved. A separate public-context graveyard query returns unknown coverage;
that does not establish that the original agent called the query or that it
caused the block.

The explicit restored fresh runtime's 1,558 mapped non-pip files stayed equal.
Source 2,681 pins and 136 owned imports were verified, native SQL/socket/child
controls passed, resource/RNG closure was equal, and the review PID ended. These
are native audit controls, not arbitrary-child OS isolation.

The first observer compared post-combat blocks with declaration-time blocks.
Its failure remains archived; the correction compares the same phase while
retaining life/winner checks. A separate launch failure caused by the missing
older runtime also remains preserved. Neither is a gameplay failure. This
review does not retune AI, clear a warning or establish expert strength.

Verified NFS handoff:
`gate2-ai-clone-scope/badblock302-qualified-new-dVB-d3QCeT/handoff.tar.gz`,
SHA256 `1a3e2698cabaa8e9241758d3cf12adf42f75aa77cf2ba31a86ccdd255552dee0`.
Parent verifier receipts are under
`parent-integration/fresh-https-badblock-evidence-20261008/`.
