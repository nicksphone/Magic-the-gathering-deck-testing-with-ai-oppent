# Conditioned Q/V Implementation Plan

> Use test-driven development and one final independent review. The user has
> delegated engineering choices; do not pause for repeated design questions.

**Goal:** Add an explicitly selected state-action interaction that can learn
conditional preferences when the existing ReLU ranker has locally flat state
gradients. Do not activate a model or claim gameplay strength from a toy fit.

**Design:** Preserve the existing encoder, Q/V heads and life-context term.
The new checkpoint activation adds a zero-initialized 64-weight linear term
over the elementwise state/action embedding product. Use the existing softsign
bound. A new explicit activation discriminator owns the extra parameter shape;
legacy and life-context payloads, defaults and mathematics stay unchanged.
Keep current actor-relative v2 context validation and all source/provenance
checks. No old checkpoint or dataset header migration is supplied.

**Evidence:** On a labeled synthetic v2 preference problem, both current heads
reach 8/16 correct rows and 0/8 contrasts. Encoded states/actions remain distinct,
but all eight groups share one ReLU region; local state-ranking gradient is zero
and total training gradient is about 1.1e-11. A matched fresh prototype adds only
64 weights and reaches 16/16 and 8/8, minimum bounded margin 0.934. These are
internal learning diagnostics, not Magic labels or accepted model weights.

## Scope

- `backend/ai/learned_qv.py`: explicit activation/shape registry, strict parsing,
  stdlib inference and prepared-state handling.
- `backend/scripts/train_qv.py`: matching zero-initialized Torch head, forward
  calculation and weight export.
- `backend/scripts/train_qv_preferences.py`: matching context handling and
  explicit CLI activation support, with no default or objective change.
- New pure protocol and CPU training regression modules only. Parent owns
  public status/docs, graph, commit, archive and any future deployment.

## Steps

- [x] Write failing tests for new discriminator/shape acceptance, malformed
  payload rejection, initial zero-head equivalence and explicit interaction math.
- [x] Implement the smallest matching Torch/stdlib change. No encoder rewrite,
  dependency, new feature epoch, state cache or card-name branch.
- [x] Verify prepared inference purity and Torch/stdlib parity, including
  nonzero interaction weights. Importing stdlib inference must not import Torch.
- [x] Verify legacy seed/weights/output compatibility and strict rejection of
  cross-family extra/missing parameters. Unsupported schemas remain rejected.
- [x] Reproduce the observed synthetic conditioning case, then pass it using
  the unchanged seed, labels, row count, learning rate and training budget.
- [x] Run complete directly affected modules with the cached CPU runtime;
  preserve every failure, skip or harness limit rather than implying full green.

Independent result: 15 whole modules, 272 tests and 27 subtests passed in
103.94 seconds. The zero/tiny-weight overflow found in review was reproduced,
fixed with matching weight-first multiplication and verified with seven added
numerical controls. Native SQL/network were denied, the exact inference child
was guarded before project imports, and all 2,649 backend inputs stayed equal.
This completes this implementation plan only, not AI quality or RC acceptance.

## Release Limits

No new model may be installed from these protocol tests. Current canonical
resource-preference admission, TRAIN convergence, untouched development contrasts,
matched games and privacy/latency acceptance remain separate. The live backend
stays on its previously verified gameplay version until separately qualified.
