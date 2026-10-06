# Current Mulligan Consumer Composition

Date: 2026-10-06 UTC. Base: published `9714ee5c44073628db6b9fe456e8a4504e6ae65b`.
No main/live edits, deployment or dependency migration.

## Change And Preservation

Only `backend/training/environment.py::lookup_intent` changes production:
public MulliganAction import/binding and a pre-normalization guard. Chosen fields
are validated before helpers. Supplied `current_mulligans` must be a nonnegative
Python integer (not bool/string/float/null) matching the current actor's current
legal offer on a copied root. No selected cards, keep choice, count authority,
actor or continuation is inferred.

Removing only the Mulligan import, binding and branch restores the entire prior
module AST. The existing actor-first check and all 23 prior model bindings remain.
Schema, API, engine, payment helpers and producers are unchanged. A new public
action inventory regression compares the API's discriminator mapping with the
consumer's explicit model bindings, so newly added public types cannot silently
bypass this boundary. This checks inventory, not every card's legal semantics.

## Acceptance

The final current-candidate gate passes **310 ordinary cases**, 176 warnings,
277.61s, exit 0, across **10 complete modules**. JUnit verifies 310 cases, ten
modules and zero failures/errors/skips. No xfails or deselections.

- Original Mulligan audit46 is unchanged; all former rejection failures pass.
- New worker guard52 covers unknown/null fields, strict metadata shapes, stale
  counts, private choices, actual London rounds and HTTP/restart.
- Current composition22 verifies both seats reject invalid actors before any
  helper and preserve default/None/explicit actor equivalence.
- Whole Suspend/keep, London bottom/round/timing and training environment
  neighbors run in the same current-source gate.

Runtime is the isolated upgraded declared-requirements Python environment.
The separate public-action inventory regression passes one case in 0.79s and
confirms all 24 current public action types have explicit consumer models. It was
added after the 310-case gate; the gate counts are not combined.
Fresh local source/database, no external service or NFS SQLite execution. Backend
source hashes before/after match. The initial command collected zero tests because
of two incorrect module paths; its exit4/log/XML are retained. Only command setup
was corrected before the successful complete run; no assertions were weakened.

Frozen dependencies: worker audit `5c03286cf900c8381ca7dddb5601f6d06698398ddd1b619828dd1ceb5365e247`
and guard `6de230a5441606f5f52e6511608a2c0f0540d9899f1548526784431a1d5f1b08`.
Only test/document additions were applied directly; the production increment was
merged into the current source without overwriting prior guard branches.

## Remaining Verification

The separate 15,947-case baseline predates recent keyword/test repairs and remains
active at publication preparation. Its observed failures must retain their own
terminal ledger; this gate is not a full-suite green claim. The repaired BO3
run has passed Burn/Aggro while Control/Ramp is still active. A last-persisted
game2/turn38 checkpoint is captured separately, not claimed to identify the
current in-memory state or a slow callsite. No professional AI, all-card semantic,
complete browser/LAN or release certification follows from consumer validation.

Frontend source is unchanged; previous milestone frontend gates are not claimed
as fresh execution here. Queued phases, entry/mill, paid triggers and shuffle
observers still require their current-source composition acceptance.
