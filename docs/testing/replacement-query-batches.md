# Bounded replacement source query batching

## Scope and frozen provenance

The only new production change is in `rules_engine/replacement.py`:
`_battlefield_oracle_texts` constructs its existing ordered source list inside
the existing `rule_query_scope(state)`. The scope ends before sorting/yielding.
Controller filters, text filters, source suppression, timestamps, order,
source objects and returned text are unchanged. All current text-filter
callbacks are text-only predicates. A future mutating callback would violate
the readonly query precondition. No scope covers a consumer, effect application,
combat resolution, SBA pass, or a whole mutable projection.

Measured source: frozen parent
`5be711a492529e42c7f677cf821a98621cbfe64f`, from the completed tick902 diagnostic,
plus the exact already-qualified continuous color predicate patch.
Diagnostic qualified source SHA256:
`d5a205043e8eb981b15590acb6d5825515a7203a191b7fd85ce8ce0fc2abfb78`.
Continuous prerequisite patch SHA256:
`78e5b09d88ff6e36a362c5d9eae0e150367e5cb2ef459d1f20b3ae8fd769e5ce`.
It applies without adjustment. Its frozen audit test and provenance files are
also supplied unchanged for the broad gate, as separate prerequisites, not part
of this performance patch. No AI, search, mana, layer-helper, engine, validation,
schema, API, frontend, parent, or main edits.

The later six-patch parent candidate at
`/home/nick/.hermes/cache/scratch/mtg-next-composed-gate-wASfmI` is a future
composition target, not the source qualified or timed here.

## Complete retained decision

Input: canonical Tokens/Ramp, seed `2225858263`, turn31, tick902, acting seat2,
DeclareBlockers; three attackers, four blockers, all 256 existing intents.
Full input snapshot SHA256:
`4f5209b6a76a5d556a71b94fdd6ed39bf4bae232a1d88b5dfd674844232ef81e`.
The prerequisite archive reconstructed the input twice through all 901 recorded
checked actions and verified every saved context. Metrics alone did not contain
a full snapshot. Earlier AI choices were not regenerated; policy evaluation
uses a fresh master agent, since prior agent-private history was not retained.
The original matrix timeout is not an individual decision timing.

Serial unprofiled timing order was baseline, candidate, candidate, baseline:

| Run | Baseline seconds | Candidate seconds |
| --- | ---: | ---: |
| First | 56.402502 | 46.995816 |
| Repeat, reverse order | 53.884189 | 45.048720 |
| Mean | 55.143345 | 46.022268 |

Measured mean reduction: **16.54%, 9.12 seconds** on this one retained snapshot.
Other workers were active on the host; no universal speed or whole-game claim.
All runs completed under 420-second watchdogs, with no alarm restart, pruning,
new cap, omitted action, or modified search budget.

Separate complete instrumented profiles took 175.518s and 146.265s. These include
cProfile and full projection snapshot recording and are not unprofiled timings.
Both retained 256 intents and 256 successful projections. Every projection's
full before/after snapshot, return result, and intent array compares exactly;
the decompressed full snapshot streams are byte-identical. Both performed
1,509 SBA calls and 250,112 generator resumptions. Layer-four query calls fell
from 1,235,977 to 970,818 through existing bounded reuse. Overlapping cumulative
profile times must not be summed.

All six runs choose the same fully announced action:

```json
{"type":"block","blocks":{"p1-029":["00000000-0000-0000-0000-00000000004a"],"p1-025":["00000000-0000-0000-0000-00000000004d"]}}
```

The full checked applied snapshots are byte-identical, SHA256
`7f7d56dc9b732b97d78e1e794f97bbc10646f7a353615912fb156cc3ef57bcdf`.
Every root remains unchanged. No cache is persisted across mutations or restart.

## Executed qualification

Reused `/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, Python3.12.3;
all eight dependency pins match this source's requirements. No installs.

23 new focused cases plus three existing diagnostic cases: **26 passes**.
The unchanged baseline with the new tests yields four ordinary assertion
failures and 19 passes: missing bounded construction and unreduced actual
layer scan work. The initial red probe had missing-mock-attribute fixture errors;
those are archived but are not the red assertion proof. Final test spies allow
the optional new import on the baseline without changing gameplay assertions.
Canonical fixtures only: both-seat suppression, actual Song resolution,
explicitly controlled source-removal seams, exact ordering/filter/controller
parity, scope cleanup on exceptions, nested queries, restart, root purity and
opponent hidden-metadata invariance. These state-only runs forbid all SQLite
connections and socket connections/binds.

55 complete affected modules, no exclusions, skips, xfails or deselections:
**1,323 passes and one unchanged baseline failure in 131.24s**.
All 57 HTTP-named cases pass. The entire six-module continuous-color gate is
included, including its twelve formerly red predicates and twelve HTTP cases.
Breadth covers damage/prevention/death/entry/counter/life replacements, source
LKI, attachments, layers, first-strike and double-strike windows, afterlife,
counter/type changes, SBA survival, AI read boundaries and combat search.
Tracked backend source and the new focused test are unchanged through the gate.
All 77 audited SQLite connections stayed in the initially absent isolated local
`candidate/backend/mtg_lab.db`; no blocked connection or external socket.
The stopped database passes read-only integrity checking before archival.

The remaining ordinary failure is
`test_combat_damage_windows.py::test_replay_keeps_both_combat_damage_priority_windows`.
Its old `record_action` test spy does not accept the existing checked execution's
`reject_invalid=True` keyword. The same TypeError reproduces on the unchanged
composed baseline. No product or existing test fix is included. A separate
proposed spy-signature/keyword-forwarding patch is archived, not applied or
qualified. This gate is therefore not claimed wholly green or main-ready.

The retained snapshot separately passes snapshot roundtrip, both-seat hidden
information counterfactuals, and malformed-action immutability. The existing
`blocks: []` path still raises AttributeError rather than ActionRejected;
it remains immutable, and no validation fix is claimed here.

## Reproduction and handoff

Archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/combat-replacement-query-batches/20261006-parent5be711a`.
It contains exact composed baseline/final source, dependency patches/fixtures,
the incremental patch, complete full snapshots/profiles, all projection states,
ABBA receipts, JUnit, baseline failure/red proofs, interpreter and source pins,
SQLite audit/stopped copy, graph refresh and verified SHA256 inventory.

From the corresponding isolated `backend/`, with local evidence directory `E`:

```sh
PY=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
PYTHONPATH="$PWD" timeout --signal=INT --kill-after=10s 420s "$PY" \
  tests/test_tick902_replay_diagnostic.py profile "$E/candidate-timer" --without-profile
PYTHONPATH="$PWD" timeout --signal=INT --kill-after=10s 420s "$PY" \
  "$E/projection-profile.py" "$E/candidate-profile"
PYTHONPATH="$PWD" AUDIT_OUTPUT="$E/db-audit.json" \
  timeout --signal=INT --kill-after=10s 600s "$PY" \
  "$E/qualification.py" -q $(cat "$E/broad.modules") --junitxml="$E/broad.xml"
```

Copy snapshot/manifest/legal inputs from the archive into local running scratch;
never execute SQLite on NFS. `production.patch` is replacement-only;
`integration.patch` additionally supplies the new focused test and this report,
over the composed frozen baseline. The continuous-color prerequisite remains
separate. Full games, the later six-patch composition, universal rules coverage,
all AI loops, and universal performance are not qualified by these results.
