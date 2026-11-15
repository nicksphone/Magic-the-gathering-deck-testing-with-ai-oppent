# Native Q/V Dot Implementation Plan

## Goal

Use CPython 3.12 `math.sumprod` only for the existing life-context v2
activation's stdlib affine products. Preserve legacy v1's naive dot bit-for-bit.
Execution is already delegated and approved; no further confirmation gate.

## Architecture And Constraints

Change only `QVPolicy._linear` in `backend/ai/learned_qv.py`. Branch on the
closed `LIFE_CONTEXT_ACTIVATION` discriminator; retain the legacy expression
unchanged and share existing bias, finiteness and ReLU handling. Supported local
and CI Python is 3.12. No fallback, cache, dependency, activation default,
checkpoint/schema change, model retag or other production edit.

Work only in an exact owned git archive of
`23a169624fc929ae71ec7a60b0f1a268b9d822d1`, with no `.git`, DB or dependencies.
Parent alone writes S. Never change P, the current preview, E12 frozen source,
or immutable checkpoint `41c4e20c6dd05d63bc064ef72fc9bb461a397227c97bd8c1dab47849cb90f9b9`.
The source change creates a new engine hash; fresh fitting is a later parent task.

## Steps

1. Add one public synthetic module, `backend/tests/test_qv_sumprod.py`.
   Capture actual RED for native dispatch and strict v2 length rejection, plus
   legacy zero-native-call/bit-exact/default, malformed/nonfinite and original
   naive-dot surrogate controls. Exercise direct and prepared validation paths.
2. Apply the smallest activation-gated native-dot branch in `_linear` only.
   Run the whole new module GREEN, then freeze production/test bytes for review.
3. Run nearest whole existing codec, prepared-cache, live-policy and preference
   modules under pre-import SQL/socket/child/write guards. Use cached CPU Torch
   for existing optional export parity; no installs or network.
4. Provide the three-path patch, pre/post pins, actual RED/GREEN receipts and
   concise numerical/error-boundary notes. Parent owns independent review and
   whole coupled qualification. Keep any AST-only graph evidence outside the
   three-path patch and engine source.
5. Only after parent integration/qualification may a separately authorized new
   engine/fresh-fit pipeline run. Do not reuse or activate the old checkpoint.

## Acceptance And Measured Limits

The closed runtime-only spike used six exact captured typed states, including
the two public canonical roots and four private E12 feature samples. Two raw,
order-balanced timing rounds measured 2.055-2.275x faster direct predictions on
canonical roots and 1.647-1.828x on the private samples. Maximum absolute drift:
Q 1.6653345369377348e-16; V 2.7755575615628914e-16. Sampled strict argmaxes,
top-tie sets and pairwise rankings stayed unchanged; this is not generalization,
strength, whole-game speed or universal near-tie evidence. No private packs or
weights belong in tests or this patch.

V2 is not bitwise unchanged: `sumprod` uses extended-precision intermediates.
Its unequal-length ValueError intentionally differs from private legacy zip
truncation. Public malformed/nonfinite inputs must still fail closed. Tests use
a frozen original affine surrogate and public deterministic weights; compare
v2 with bounded tolerance, retain exact legacy bits, and retain existing Torch
export parity tolerances without relaxation.
