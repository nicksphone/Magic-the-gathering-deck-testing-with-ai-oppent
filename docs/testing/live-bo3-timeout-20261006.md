# Live BO3 Timeout Evidence

Source: published `9714ee5c44073628db6b9fe456e8a4504e6ae65b`, unchanged backend
manifest before/after. Isolated upgraded declared-requirements Python, local
synthetic SQLite. Main/live source and dependencies untouched.

Command: original whole `tests/test_live_bo3_series.py`, pytest verbose with
durations and an outer `timeout 1200`. Both original assertions unchanged.
The owned candidate database had previous regression fixtures; this is not a
fresh-install test.

Authoritative result: **exit124**, not a passing two-case gate. The
`Mono Red Aggro-Burn-73` case passed; the final captured active node is
`Blue Control-Ramp-73`. No completed JUnit pair is claimed. The 1200-second
bound applies to the whole two-case run, not an individually measured decision.

Read-only checkpoint capture retains full state/controller configuration,
capture timestamp, database update timestamp and four relevant source hashes.
Last persisted checkpoint: game2, turn38, end step; Control18 life, one card in
hand, 16 battlefield objects, 16 library cards; Ramp10 life, one hand card,
21 battlefield objects, 23 library cards. This is **not** the actual in-memory
state at termination, a stack trace or proof of a specific slow callsite.

Logs, exit receipt, snapshot and unchanged-source verification are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/suspend-keep-group-keywords-20261006/`.
The earlier 440-case repair gate remains green but does not qualify this pair.
The separate 15,947-case baseline is still active on earlier source and is not
restarted or reclassified by this timeout.

Next: replay the captured checkpoint in a disposable source-matched process,
measure decision/rule/serialization work and identify the responsible call path
before implementing a fix. Do not silently cap search, change cards/seeds,
weaken completion assertions or force matchup balance to manufacture a pass.
