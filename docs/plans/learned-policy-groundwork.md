# Learned Policy Groundwork

## Status

The deterministic [training environment](../testing/training-environment.md)
is implemented for built-in decks, private observations, accepted complete
actions, terminal rewards and snapshot restoration. Its action encoding is
partial; some pending choices still require explicit encoding work. The composed
adapter/AI/input/metadata gate passed 323 checks; this is not a trained policy.

The [versioned dataset exporter](../testing/training-dataset.md) is implemented
with actor-private observations, complete accepted action labels, provenance,
bounded immutable shards and explicit incomplete outcomes. Its teacher is a
generic heuristic, not expert supervision. Grouped datasets without a held-out
partition explicitly report NOT evaluation-ready.

Complete choice encoding, useful feature coverage, expert data, training and
learned-policy evaluation remain unfinished. Existing simulations are regression/evaluation runs.
Canonical metadata, rulings evidence and tactical tags are knowledge inputs,
not learned gameplay or proof of effect execution. No neural policy is trained
or deployed, and no expert supervision is claimed from heuristic self-play.

## Step-By-Step Gates

1. Verify canonical metadata and complete mechanics for a declared initial corpus.
   Record card/face/Oracle/rulings provenance separately from execution coverage.
   Preserve explicit unsupported and ambiguous effect clauses. Expand the corpus
   as validated mechanics land; do not wait for every Magic card to start learning.
2. Expose a deterministic training environment around the authoritative engine.
   Observations use the existing private AI boundary; only permitted information
   reaches the policy. Legal actions, pending choices and terminal rewards remain
   engine-generated. Illegal policy outputs cannot mutate gameplay state.
3. Export versioned observation/action/choice trajectories and engine/deck hashes.
   Keep private replay evidence out of public fixtures. Split evaluation by seed,
   deck family and retained tactical position; prevent duplicated games or future
   observations from leaking into training examples.
4. Establish a move-ranking/value baseline, initially using verified decision
   examples and suitable expert trajectories. Separate provenance-backed expert
   decisions from current heuristic demonstrations; weak self-play is not expert
   supervision. Specify action encoding, legal masking and uncertainty handling.
5. Train offline with reproducible checkpoints and bounded resource budgets.
   Begin with a small supported corpus; measure sample efficiency and inference
   latency before choosing a larger network or committing expensive compute.
6. Add self-play against a varied opponent population. Preserve engine legality,
   hidden-information limits and loss/draw rules. Validate reward accounting; do
   not force win-rate targets, fabricate cards or rebalance canonical decks.
7. Compare frozen policies against the existing baseline on held-out, seat-balanced
   games and tactical fixtures. Measure missed deployment/land/lethal opportunities,
   resource/counter timing, blocks, illegal outputs, stalls and latency. Report
   sample sizes and uncertainty; matchup win rate alone is insufficient.
8. Integrate behind an explicit policy version/feature switch with deterministic
   inference where configured, fallback and rollback. Persist policy and engine
   provenance in snapshots/results. Keep learning out of live match mutation.

## Acceptance Still Needed

- A concrete observation/action schema and tested adapter for all supported
  pending choices; no opponent-hand or unseen-library access.
- Train/evaluate commands, reproducible dependency/compute requirements, dataset
  manifests, checkpoint loading and offline behavior.
- Before/after evidence on unseen decks and seeds, not just successful training
  or a fixed scripted position. No current seasoned-player guarantee.
- Human review of expert-data availability/licensing and any paid compute budget
  before collecting proprietary data or launching paid training infrastructure.

## References

AlphaZero combines learned policy/value evaluation with search and self-play:
https://deepmind.google/research/alphazero-and-muzero/
AlphaStar combines imitation and reinforcement learning in an imperfect-information
game: https://deepmind.google/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/
These are architecture precedents, not claims of equivalent resources or outcomes.
