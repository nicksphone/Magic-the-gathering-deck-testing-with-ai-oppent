# Historical 745 AI Natural-Game Evidence

Runtime source: immutable `7455a9db6a87c2b75e64cfbef2274ac5b0a6432c`.
This is historical runtime evidence, not current-source gameplay qualification.
The subsequently published Spree/Crypt checkpoint changes backend runtime bytes.
No policy weights, search depth, turn-clock fallback, winner or action was changed
to obtain these results. These games did not execute the Spree/Crypt increment.
Separate first-main hidden-information observations on matching newer backend
bytes are recorded in `ai-first-main-hidden-observations.md`; they are not games.

## Two Completed Orientations

Seed `299881142`, master difficulty, player 1 starts in each orientation:

- Blue Control seat 1 versus Burn seat 2: Blue Control won at turn 23 after
  654 checked actions, 2,119.251 seconds.
- Burn seat 1 versus Blue Control seat 2: Blue Control won at turn 22 after
  623 checked actions, 366.498 seconds; game wrapper exited zero.

These are TWO separately executed completed games, with each deck starting once,
not a single successful paired run or two statistically independent samples.
The original paired run remains exit 1: its second game stopped at the declared
free-disk threshold after an 84-action prefix. That prefix is unavailable for
completed-game quality measurement and was not merged into the 1,277 actions.
The completed first game was not rerun.

The reverse run retained every journal record in lossless concatenated gzip
members, within the declared 256 MiB cap. Its limits remained 6,000 checked ticks,
6,000 seconds, launch free space at least 5 GiB and per-record free space at
least 3 GiB. No evidence truncation, timeout relaxation or forced ending occurred.

## Decision Evidence And Limits

Artifact-only analysis pairs every completed outer decision with its genuine
checked application by normalized action, actor and compact quality payload.
There are exactly 654 and 623 such pairs. The first game's 2,518 nested simulated
observations remain separate; the reversed game had no nested observations.
Root-minus-log purity, append-only diagnostics and global RNG receipts pass.

The existing six bounded anomaly counters are zero for each player, with producer
availability true: missed land drops, unused-mana passes, lethal misses, bad blocks,
stall streaks and redundant removal casts. This is not proof of optimality,
hidden-identity counterfactual invariance, expert strength or semantic correctness
of every encountered card. Independent seeds, broader archetypes, measured
before/after improvement and final-source gameplay parity remain required.

Only Burn (12 entries, 60 cards) and Blue Control (13 entries, 60 cards) played:
25 distinct names. The four other decks in the input file were not played.
The raw input has 23 unspecified layout strings and two normal layouts; no
missing Oracle/layout facts were inferred. Ready/unsupported preflight metadata
does not certify complete-card semantics.

## Source, Closure And Archives

All 2,612 original source hashes match. The reverse game appended only the
previously absent shipped generic SVG: 644 bytes, SHA256
`a3114095c760517186807f8753d109000174460a20ee72693ff9b9a69efc5e85`.
The guard records the actual pinned producer/code/module/globals and copyfile
pre-open frame; post-run hash/size verifies the completed append. Strict full
file-set equality remains false; the separately declared exact append invariant
passes. No existing source was modified.

Native SQL/socket/child controls passed; unexpected application I/O is empty.
Owned source/import/runtime hashes, FD/thread/child and RNG closure were verified.
No game database was created, and actual game processes ended. These are observed
native audit boundaries, not an OS sandbox or full release certificate.

Immutable NFS evidence under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`:

- `gate2-ai-clone-scope/current745-natural-pair-incomplete-kJ3UPu/` preserves the
  original failed pair, completed first game and separate corrected analysis.
- `gate2-ai-clone-scope/current745-reversed-natural-complete-QbNCKN/` preserves
  the completed reverse game, full source/runner/journal, exact 623-pair analysis,
  declared corpus and separately joined orientations. Full manifest SHA256:
  `88365f57930cfd437ed67d0f79e13be94e5b6c152ccfa98228528ed56cd48e44`.

The parent independently checked the full manifest. All tar member bytes were
read back. The original failure, weaker aggregate and resource-stop receipts
remain immutable. This evidence does not close the broader AI/rules goal.
