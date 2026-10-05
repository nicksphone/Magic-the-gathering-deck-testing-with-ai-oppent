# Versioned Training Trajectories

This is an offline dataset exporter, not a trained model or certified expert data.
The existing `AIAgent` teacher is always labeled **heuristic**, including on wins.
The initial teacher is explicitly **baseline generic**: both seats use the
`Midrange` archetype, the requested `strong`/`master` difficulty and
`opponent_archetype=None`. It does not analyze either deck's identity or supply
opponent style. This is not the live per-deck-configured AI policy. This deliberate
baseline keeps deck inference/strategy changes outside dataset groundwork;
future own-list analysis must remain trusted and not infer opposing hidden facts.
Other trusted scripted/adaptor callbacks remain `scripted` or `unverified`; the
exporter has no mechanism to claim expert provenance. Expert collection,
human qualification, licensing and paid training are separate future gates.

## Records And Information Boundary

Each immutable JSONL episode shard contains a versioned start, zero or more
accepted transitions, and an explicit end. A transition's `input` is the actual
acting seat's pre-action `TrainingEnvironment.observe` result. Its action is the
complete normalized action accepted by the real engine, not a legal-move hint,
fabricated target/payment choice or proposed action that failed execution.
Future/next observations, seeds, snapshots, hidden replay logs, opposing submitted
lists and teacher reasoning are never exported. The trusted teacher uses the
adapter's `decision_view` boundary, not an omniscient engine search. Authorized
remembered cards come only from that existing boundary.

`EpisodeAliases` replaces visible internal instance IDs with per-observer public
encounter aliases. Alias assignment does not sort by raw deck-order IDs. The
reversible raw-ID/action map stays only in trusted process memory. Canonical
card names, printed fields and face metadata are not hidden instance IDs. Actions
referencing absent/unencodable objects stop the episode instead of guessing.
This is not a fully graph-canonical, permutation-invariant feature encoder;
public zone encounter order remains meaningful. Never directly model-encode raw
environment action IDs, private snapshots or evaluator mappings.

`model_input(record)` returns only the current actor's observation. Outcomes and
provenance are labels/evaluator data, not input features. Do not concatenate the
opponent's observations or future same-seat rows into a decision context. A
trajectory file contains both seats' authorized perspectives; a downstream
sequence loader must keep actor boundaries and causal prefixes intact.
The adapter observation is intentionally sparse: it does not include every
prompt/continuation or own-list prior used by the heuristic teacher. It is not
yet a sufficient feature state for every choice or an exhaustive action mask.

Engine, deck and policy hashes are in the separate immutable run manifest.
The manifest's `teacher_config` records the exact baseline mode, implementation,
difficulty, archetype, null opponent archetype and disabled deck-identity analysis;
it is also covered by the policy hash and is never model input. Heuristic runs
without this configuration cannot resume under this revision: create a new run,
do not relabel or overwrite old manifests. Scripted/unverified origins do not
inherit the heuristic's configuration.
The heuristic policy hash includes AI sources/priors, composed knowledge metadata,
the teacher adapter and the runner source; changes cannot silently share a run.
Hashed seed/deck-family/episode-position grouping tokens remain outside model
input. Raw seeds and opposing deck lists are absent even from exported metadata.
Hashes detect changes; they do not authenticate a maliciously rewritten dataset.

## Completion, Budgets And Resume

Only an engine-declared terminal episode receives terminal rewards. Tick/byte
budgets, cancellation, interruption, rejected/incomplete action proposals and
teacher failures produce explicit incomplete ends with **null** terminal rewards,
not terminal draws. Rejected proposals are never transition labels.

CLI bounds are 64 episodes, 1,000 accepted ticks per episode and 50 MiB total
output; defaults use 16 ticks. JSON records are also bounded. Teacher calls are
not preempted mid-search, so tick limits are not strict wall-clock guarantees.
The engine may report existing unsupported mechanics; this exporter does not
certify every builtin card or invent a choice to keep a run moving.

New runs use exclusive directory creation. Existing directories are never
overwritten. `--resume` checks configuration/engine/policy hashes, locks the run,
and verifies each immutable newline-terminated shard and its content digest.
It resumes at the **next episode boundary**, not inside a partially collected
game, and does not extend already sealed tick-limited episodes. Each shard is
streamed to an exclusive pending file and committed without replacing a target.
Hard termination or malformed/pending/user files make resume fail closed. Nothing
is silently truncated, deleted, repaired or treated as a draw; inspect the private
run and start a different output directory. There are no exported state checkpoints.

`episode_groups` and `grouped_split` keep connected seed, family, deck-hash,
episode and declared tactical-position groups together. All transitions of an
episode inherit its split. Shared-family datasets may form one component and
cannot yield an independent evaluation split.
Round-robin shared-family/deck edges can transitively join every episode into
one component. `grouped_split_report` and the CLI's final diagnostic JSON report
**NOT evaluation-ready** whenever either heldout or training is empty, with
`empty_heldout_split` / `empty_training_split` reasons. An exit-zero export means
collection completed, not successful evaluation. Nonempty partitions report only
`partitions_available`, not teacher quality or evaluation qualification. The
bounded two-seed demo is **NOT evaluation-ready**; do not report heldout scores.
Declare common families for deck
variants and common position groups for retained fixtures; insufficient family
labels cannot establish a real unseen-deck evaluation. Duplicate games never
become independent samples by changing teacher versions or seating.
Freeze the split with each dataset revision; do not later evaluate a component
whose members were already used in training.

## Invocation

Local finished exports must use the verified mounted NFS dataset root:

```sh
python backend/scripts/export_training_trajectories.py \
  --out /mnt/rchfiles/codex-storage/mtg-deck-testing-lab/training-groundwork/dataset/example-new-run \
  --seeds 17 18 --ticks 4
```

CI may explicitly choose an existing ephemeral directory, with no implicit local
fallback:

```sh
python backend/scripts/export_training_trajectories.py \
  --ci-temp "$RUNNER_TEMP" --out "$RUNNER_TEMP/example-new-run" \
  --seeds 17 18 --ticks 4
```

Upload the explicit CI artifacts if needed. The runner does not use SQLite or
network retrieval; canonical existing builtins hydrate from offline metadata.
Tests cover both-seat hidden permutation byte equality, full action alias
round-trip, actual terminal canonical Bolt resolution, nonterminal labels,
group leakage, deterministic shards, malformed/partial resume refusal, byte
limits and a small actual seeded CLI run. This is not expert-play acceptance,
whole-game policy qualification or arbitrary-card correctness.
