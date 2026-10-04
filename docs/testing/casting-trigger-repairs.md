# Casting and trigger repair acceptance

## Scope

The second canonical regression handoff (`b94c477`) was reproduced against
main `d58dbec` in a disposable source copy: 34 passing cases and six failures.
The original [agent report](rules-regression-agent-wave2.md) remains historical
evidence, not a claim about the repaired revision. Fixtures retain actual
Scryfall records and pinned Comprehensive Rules; no replacement card text was
invented to produce desirable match results.

The connected batch implements these bounded instruction families:

- Sacrifice-linked damage captures effective creature characteristics when the
  additional cost is paid, before departure. Damage uses the ordinary handler;
  its locked amount survives stack snapshots and source removal.
- Ordered counter placement preserves occurrence-specific amounts and required
  different recipients. Illegal duplicate targets are rejected before payment.
  Resolution rechecks each object's identity and legality without reallocating
  the announced amounts when another target becomes illegal. Clauses that permit
  repeated targets remain permitted.
- The supported ETB instruction granting an owned graveyard instant/sorcery
  flashback until end of turn uses ordinary owned trigger choices, durable
  graveyard references, actual casting costs and expiry. Native and granted
  costs remain separate options when different; X and kicker use existing cost
  machinery. Canonical Oracle text is not rewritten.
- Supported self-return-to-hand graveyard-from-battlefield triggers use departed
  ability/controller information and the new graveyard object reference. They
  respect ownership, suppression, departure replacements and stale references.
- Shared AI selects legal ordered allocations through checked execution. The
  human UI requires deliberate distinct selections and retains batched changes;
  both seats can pay, resolve and reload these casts.

## Checks

All backend/API fixtures used disposable local source-relative SQLite databases,
not the live database. Final backend source archive SHA-256:
`72fcb45f013a0bebb474d7aca4c61b8b27b245ae33abb4f2c436d8ed5aa208fe`.

- 40 original canonical cases and 38 additional edge cases pass. The new edges
  include actual AI decisions for both seats, Aggro/Control and all three
  ordinary difficulty settings, with root nonmutation and actual payment checks.
- Final full backend gate: **7,310 passed**, across four independent disposable
  shards (1,273 / 1,903 / 2,316 / 1,818). An earlier full gate also passed;
  the final one includes the latest source-prefix and isolation-guard changes.
- Frontend unit/table-model checks, ESLint and TypeScript/Vite build pass.
- Full rules-only browser harness passes, including deliberate ordered targets,
  natural AI/human BO3, sideboarding and backend-restart recovery.
- Tempo/Tokens and Burn/Dimir: two seeds, both seats, each repeated. All eight
  logical samples (16 executions) finish within the declared 2,400-tick cap;
  no determinism failure, timeout or recorded anomaly. This is not a statistical
  balance result or a certificate of optimal play.
- The canonical regression fixture guard still rejects a Git worktree. CI
  extracts tracked backend source into a disposable directory and declares its
  exact root with `MTG_ISOLATED_TEST_ROOT`. A real outside-Hermes isolated copy
  passes the 78 focused cases; no live-checkout safety bypass was added.

Early failed attempts are retained: a guessed missing test filename, a generic
self-reference mismatch, a test-helper argument-order mistake, and the first
combined UI fixture import. Corrected runs are separately labeled; they do not
erase the earlier failures or weaken the canonical gameplay assertions.

Verified evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/casting-trigger-repairs/20261004T222346Z/`.
Active code and databases remain local. Archived databases are evidence only;
do not run SQLite on NFS.

## Known Limitations and Next Upgrades

The existing fixed ordering of different casting-cost payments is not general
CR 601.2h choice support. Ordered allocations recognize complete bounded
counter-placement clauses, not every multiple-target instruction. Granted
flashback recognizes the specified ETB and printed-mana-cost instruction, not
arbitrary grants or general permission/layer semantics. Self-return recognition
is likewise bounded. Unsupported effects must remain explicit in diagnostics.
Full replacement/layer dependencies, broader Oracle semantics, long-session
human acceptance and expert AI remain unfinished.
