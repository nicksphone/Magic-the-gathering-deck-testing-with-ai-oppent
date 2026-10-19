# Reviewed public graveyard metadata

The current MatchState and CardInstance dataclasses gained permission/protection
and kicker metadata after the inventory schema pins were established. The old
pins therefore rejected even reviewed default states before examining public
card clauses. The repair updates those two pins and explicitly checks the new
context; it does not change AI weights, move selection, models, or rules handlers.

Accepted context is exactly two integer-seat keys with empty color-history sets,
known history, and empty typed spell-protection, player-hexproof and retained
counter-prohibition containers. Public card kicker metadata must be None or
integer zero with was_kicked exactly False. Active, malformed, missing, unknown,
contradictory or future-schema context remains conservative. Complete printed
clause coverage and the existing continuation checks are still required.

## Observed qualification

On immutable b0373b629d5dd7de8b63a8562b160e7b71d0955e application source,
the original four whole modules produced 269 passes and 54 failures. With only
the inventory repair and a new 104-case module, the five whole modules produced
427 passes in 161.75 seconds, with zero failures, errors, skips or deselections.
All original 323 nodes and their order were retained; all 54 original failures
passed with unchanged assertions.

The independent protocol checker passed. Native SQL/socket/child controls were
denied before application import; the original alias controls remained intact.
All 2,634 frozen source files and the read-only runtime inventory were unchanged
after execution. There were no foreign application imports, unexpected denials,
database creation or surviving owned threads/children. This is evidence about
the guarded Python process, not an operating-system sandbox certificate.

Full tested source and evidence are archived under:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/gate2-ai-clone-scope/public-graveyard-b037-candidate427-complete-FEdWRP/`.
The archive checksum and complete local tar comparison both passed before parent
integration. The parent inventory preimage matched the tested preimage exactly;
its intervening commits changed test discovery, documentation and graph files.

This qualification does not establish expert AI strength, arbitrary-card
coverage, full natural-game benchmarks or final composed release readiness.
