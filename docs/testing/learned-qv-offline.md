# Offline Learned Q/V Groundwork

Status: component-qualified checkpoint/inference, multi-run intake, CPU numerical
learning and explicit opt-in live-agent routing. Real-game policy fitting,
heldout gameplay quality, application persistence and release-candidate
qualification remain separate acceptance work. Production still defaults to the
existing heuristic; no checkpoint is downloaded or activated automatically.

## Model And Boundary

`ai/learned_qv.py` performs inference using the standard library. A shared
64-hidden-unit ReLU encoder consumes bounded typed semantic trees, not opaque
card/action IDs, private engine state or a lossy fixed-width raw observation.
References gather authorized earlier entity descriptors. Lists preserve order;
sets/maps retain multiplicity with permutation-invariant aggregation. Text uses
learned byte embeddings with ordered position moments, not a dense recurrent
operation for every byte. `QVPolicy.prepare(state_features)` caches a fixed
decision's state/entity embeddings; `predict(action_features)` scores complete
accepted actions without accumulating action-specific cache entries.

The strict registered pairs remain separate: decision/features v1 with schema
SHA256 `0b3aadfead9f66999c8b6c3ddc13699ad7dc5dd1c76179e95585042ba0339ed5`,
and decision/features v2 with schema SHA256
`9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06`.
Unsupported or mixed contracts fail closed. Neither this bounded representation
nor its structural tests establish exhaustive gameplay-feature coverage.

Checkpoints are bounded strict JSON: fixed tensor shapes, exact scalar types,
finite values, engine/schema bindings and dataset/split/trainer provenance.
There is no pickle, executable deserializer, app Torch dependency or default
model download. A zero-update checkpoint may serve protocol fixtures; it must
not be presented as a fitted or gameplay-qualified policy.

## Corpus And Training

The existing exporter defaults to the unchanged v1 path. Its explicit
`--decision-frame --public-context` flags opt into the context-bearing frame.
`scripts/train_qv.py` accepts repeated original sealed `--dataset` roots. Intake
validates manifests/shards, preserves transitions and true seed/family/deck/
position grouping edges, rejects duplicate runs and mixed engine/schema epochs,
and enforces aggregate limits rather than multiplying them per root. Run hashes
scope episode addresses; they are not input features or replacements for groups.

The multi-run split uses schema 2 and scoped episode addresses. Schema 1 remains
available for the original single-run interface. Every eligible episode belongs
to exactly one partition, with no grouping edge or identical trajectory crossing
training and heldout data. Incomplete episodes remain recorded but supply no
terminal target; they are never relabeled as draws. Unobserved actions are not
negative labels, and heuristic/scripted origins are never upgraded to expert.

Only training rows update the optional CPU PyTorch model. Evaluation reports
heldout Q/V errors separately. Empty or unusable partitions are unavailable, not
zero error. Collection readiness is not policy qualification. The declared real
train/eval families, seeds and seat mirrors must be fixed before collection;
the generic collect-only splitter does not authenticate that declaration.

```sh
# Intake only; no Torch required. A fresh split is written even when unready.
python -m scripts.train_qv --dataset /owned/run-a --dataset /owned/run-b \
  --engine-hash FULL64HEX --collect-only --split-out /owned/fresh-split.json

# Optional CPU-Torch runtime; explicit frozen partition and fresh output.
python -m scripts.train_qv --dataset /owned/run-a --dataset /owned/run-b \
  --engine-hash FULL64HEX --split /owned/predeclared-split.json \
  --out /owned/fresh-checkpoint.json --seed 17 --epochs 20 --seconds 300
```

All outputs must be outside sealed datasets and all six recursive engine-hashed
directories: `rules_engine`, `effects`, `game_state`, `ai`, `card_data`, and
`training`. Existing files are never overwritten. Store datasets/checkpoints in
owned runtime-data locations, never source. Freeze every hashed live-adapter and
actor-projection change before final real-game export/training, or the resulting
dataset/checkpoint engine binding will become stale. The cooperative training
timer does not replace an independently enforced outer deadline.

## Explicit Live Binding

`ai.learned_policy.bind_live_policy(raw_checkpoint_bytes)` validates and hashes
the same bounded immutable byte buffer. It accepts only the registered v2 actor
context contract for the current engine and requires positive update/sample
counts. Those counts establish eligibility, not the truth of a training claim
or measured playing strength. Supply the returned in-memory handle explicitly
to `AIAgent(learned_binding=binding)`. The adapter accepts no filename, HTTP
request, saved-match instruction or ambient setting as activation authority.

The bound agent ranks an existing heuristic shortlist of at most nine checked
actions, not the exhaustive legal-action space. Shared actor-view projection
uses the supplied public moves without constructing another game or recomputing
legal moves in a masked world. Only semantic feature packs reach the model;
the original state is retained solely for authoritative action admission.
Incomplete choices, unsupported encodings, stale contracts, unusable candidates
and invalid numerical predictions retain the normal heuristic fallback. Stable
ties preserve shortlist order. A configured learned adapter does not mean every
decision uses neural scoring.

Saved controller snapshots may retain a closed per-seat checkpoint identity and
feature/engine contract. Restoration never activates weights from that metadata.
The caller must explicitly supply a trusted agent whose actual validated
`LivePolicyBinding` has the same checkpoint SHA, contract and current engine;
otherwise the recorded identity remains with visible `restore_requires_opt_in`
heuristic fallback. An ordinary agent plus matching strings is not eligible.
The `mtg.live-policy.v1` envelope registers only the loader-validated
`mtg.qv.v1` model. Empty metadata preserves the legacy snapshot format.

Three whole import-only controller/persistence modules pass all 40 cases,
including genuine loader-binding identity and mismatch checks. Their positive
checkpoint is an explicitly labeled protocol fixture, not a trained model.
New-match operator activation, completed-game history, actual HTTP/SQLite
restoration and trained-model application acceptance remain separate work.

The corrected live declaration passes all 302 ordinary cases in eleven whole
modules, including the new 17 routing tests, in 329.93 seconds. The new tests
use explicitly identified numerical/protocol doubles over genuine paid spell
states; they do not certify fitted weights, latency, strength or saved-match
activation. The first complete run recorded 300 passes and two new expectation
failures: canonical actions included the public schema's three false origin
defaults. Only those expected dictionaries were corrected; production action
normalization and all inherited assertions were retained. A separate corrected
whole-new-module run passed all 17 cases before the complete 302-case run.

## Observed Component Evidence

These are separate actual scopes, not a summed coupled suite:

- Collector: original missing-capability baseline 15 FAIL; composed product
  15 PASS. The tests include controlled canonical native terminal episodes and
  incomplete exports, not an actual policy-training corpus. An initial product
  attempt had 1 PASS/14 import-guard setup errors; the corrected role admitted
  only the already-installed `httpx` import while retaining network/SQL/child
  denial. No product or test-body change repaired that setup issue.
- Output boundary: 4 PASS/4 desired failures before extending the exclusion to
  all six hashed directories; the same whole eight cases then passed. An earlier
  zero-test pytest log-path setup stop is preserved separately.
- Unchanged default checkpoint/inference regression module: 8 PASS on the
  composed model under the application runtime, with no Torch import required.
- Unchanged explicit optional Torch script: 3 PASS under the separately pinned
  CPU runtime, using one CPU thread and no skipped learning checks. Actual XOR
  learning changed weights over 720 updates: Q-MSE
  `1.003077937161645 -> 0.0018114180331212516`. The actor-relative value protocol
  changed weights over 200 updates: Q-MSE
  `0.9977634164186865 -> 0.002428453797014304`. Typed-tree export/inference parity
  assertions also passed. These are numerical protocols, not Magic quality.

The older optional run's null observer-count fields remain immutable; the new
three-case run collected its actual unittest result directly. No historical
ledger was rewritten. Successful roles recorded source/runtime before/end
equality, closed child groups/resources and no denied I/O attempts.

Default tests are `tests/test_learned_qv.py`, `tests/test_qv_multirun_corpus.py`
and `tests/test_qv_output_source_boundary.py`. Optional actual CPU checks are
`python -m scripts.check_qv_torch`, outside default test discovery. Runtime
recreation must use the retained official CPU-wheel index and exact wheel hashes,
not unconstrained/GPU-default installation. No Torch import is added to app startup.

The legacy environment/dataset declaration separately passed all 92 cases in
177.99 seconds, including the genuine exporter CLI children, after closing two
dataset locks in an old test fixture's `finally` block. No assertions or dataset
semantics were removed. This earlier component run preceded the live-adapter
extraction; it is not a second execution of the current 302-case declaration.
Real terminal-game collection, final-epoch
training/reload, heldout Q/V evaluation, real-decision latency, checked live
application persistence, matched gameplay quality and native/browser acceptance
remain open.
