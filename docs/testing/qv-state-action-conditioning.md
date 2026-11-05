# Opt-In State-Action Conditioning

This is a model-learning correction, not an accepted gameplay model. No weights
from these checks are installed in the running application.

## Observed Problem

A controlled synthetic preference problem has 16 rows in eight pairs. Each pair
requires the action ordering to reverse when one context value changes, while
life totals and an irrelevant numeric backdrop remain present. Both existing
heads finish at 8/16 rows and 0/8 complete pairs with the same seed and budget.

The encoder still distinguishes the states and actions. All eight pairs occupy
the same ReLU region, however, where the concatenation head is locally affine.
The common state term cancels when comparing two actions. At the observed
stationary point, the local state-ranking gradient is zero and the total
training-gradient norm is approximately `1.1e-11`.

This is one reproducible limitation, not a proof that the old architecture can
never learn context or that it explains every failed real-card fit.

## Implementation

Explicit activation `relu-softsign-life-state-product` retains the encoder,
Q/V backbone and existing actor-relative life-context head. It adds one
zero-initialized `q_interaction.weight` with shape `(1, 64)`:

```text
raw_q = existing_raw_q + sum(weight[i] * state[i] * action[i])
q = raw_q / (1 + abs(raw_q))
```

The discriminator registers the additional parameter; a missing, malformed or
cross-family parameter is rejected. The registered v2 feature contract, strict
life-context validation and source/provenance checks remain required. Existing
activations, defaults and checkpoint payloads are unchanged. There is no
checkpoint migration or old-data reheadering facility.

Torch training and stdlib inference implement the same additional term.
Both apply the weight before multiplying the two embeddings, so finite large
embeddings do not overflow an intermediate product with a zero or tiny head.
Truly nonfinite raw scores and training gradients still fail closed; there is
no clipping of an invalid score or disconnected zero-head shortcut.
Prepared inference retains its detached state and does not import Torch.
The existing return-training CLI can select the variant explicitly with
`--q-activation relu-softsign-life-state-product`; preference training accepts
the corresponding explicit `q_activation` argument.

## Evidence Boundary

The original isolated prototype and production regression use the same seed
`17`, labels, 16 rows, 60 epochs, paired batches, 480 optimizer updates, learning
rate `0.003`, temperature `0.25` and no value targets. The prototype reaches
16/16 rows and 8/8 complete pairs, with minimum bounded margin `0.934`.
These are labeled synthetic typed-tree inputs, not Magic cards, game outcomes,
expert decisions, held-out strategy tests or accepted model weights.

Original private conditioning evidence is archived under
`qv-conditioning-diagnostic-20261105-OTrvj9kQ` in the project's protected NFS
storage. Its four generator ASTs match, and the life baseline and zero-head
prototype have identical initial raw ranking loss. Old protected feature and
checkpoint bodies were not consumed.

Independent qualification passed **272 tests and 27 subtests across 15 complete
modules**, with no failures, errors or skips, in **103.94 seconds**. The two new
modules contain 57 tests. The suite covers strict shape/context/provenance
checks, nonzero Torch/stdlib parity, prepared-state purity, legacy seeded weights
and RNG, and the fixed-budget conditioning regression. Both old heads remain at
8/16 rows and 0/8 complete pairs; the explicit new head reaches 16/16 and 8/8.

Native SQL and socket operations were denied before project imports. The fresh
inference subprocess had its own installed audit guard; its exact fixed command
was the only allowed child. All 2,649 recorded backend inputs matched before
and after. No protected old learning bodies were read or model activated. The
one warning is the already-cached CPU Torch runtime's absent optional NumPy.

Independent review caught the intermediate-product overflow described above.
Seven added numerical regressions exercise zero/tiny weights, genuine overflow
and retained gradients. The final focused review found that issue closed. The
original red tests, initial passing worker stage and two stricter-harness setup
failures remain preserved rather than relabeled as gameplay defects or passes.
Those harness attempts mishandled relative symlinks, captured pipe descriptors
and a `Path`-valued subprocess working directory; no production changes were
made to satisfy them.

## Remaining Acceptance

Fresh current-source canonical card decisions must demonstrate TRAIN convergence
and untouched development contrasts before any model is considered useful.
Matched full games, hidden-information safeguards, latency, broad archetypes
and BO3 strategy remain necessary. Improving this synthetic protocol neither
closes those requirements nor authorizes switching the live checkpoint.
