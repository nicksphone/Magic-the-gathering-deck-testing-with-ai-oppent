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

### Opt-In Life-Context Q Codec

The default remains `mtg.qv.v1` / `relu-tanh`, with the original parameter set,
seeded initialization and v1/v2 feature behavior. The explicit new pair is
`mtg.qv.v2` / `relu-softsign-life-context`; it requires the registered feature-v2
contract and adds only `q_context.weight` of shape `1 x 192`, without a bias.
Unknown or mixed discriminators, extra/missing parameters and retagged old
weights fail closed. There is no converter, normalization or warm start.

The same complete 64-wide tree encoder and original Q/V heads remain. Let `a`
be the encoded action. New raw Q is the old raw Q plus the linear projection of
`outer([1, self_life / 20, opponent_life / 20], a)`, flattened context-major.
Life is extracted strictly from unique typed-map paths
`state.root.observation.players.self.life` and the corresponding `opponent`
path. Both must be explicit finite number nodes. Missing, duplicate, boolean,
nonfinite or incorrectly typed paths are errors, never default-zero inputs.
There is no label, card-name or private-identity lookup for this term.
The 192 context parameters initialize to zero after all legacy modules, leaving
legacy seeded weights identical and restoring the caller's CPU RNG state.

Only the new Q uses softsign `x / (1 + abs(x))`; V remains `tanh(raw V)`.
Torch forward, raw preference logits and stdlib prepared inference use the same
contextual raw Q. In a synthetic binary64 fixture, logits 22 and 19 have
negligible tanh separation, while softsign retains a margin about 0.00652.
The CPU Torch fixture separately checks an exact tanh tie at 22 versus 20.
Softsign can still lose separation at
extreme finite magnitudes; it is not a universal no-ties guarantee.

The return-fitting API and its existing CLI accept explicit
`q_activation='relu-softsign-life-context'` and
`--q-activation relu-softsign-life-context`, respectively. The preference API
accepts the same `q_activation` keyword; it has no standalone CLI. Omitting the
option leaves legacy activation unchanged. No live binding, activation gate,
model selection or current-engine contract check is changed by this codec work.
`backend/ai/learned_policy.py::bind_live_policy` delegates architecture validation
to `QVPolicy`; it has no independent hardcoded model-version restriction. A valid
positive-update/sample V2 checkpoint with the current engine/feature contract is
therefore admissible through the existing explicit operator authority.
`backend/main.py::_live_policy_provenance` emits the `mtg.live-policy.v1`
provenance envelope and checks the module constant `VERSION`, not the payload's
checkpoint version. That envelope is not a V1-only checkpoint barrier. No model
is activated by this offline pipeline, and admissibility is not deployment or
playing-strength qualification.

## Corpus And Training

The existing exporter defaults to the unchanged v1 path. Its explicit
`--decision-frame --public-context` flags opt into the context-bearing frame.
`scripts/train_qv.py` accepts repeated original sealed `--dataset` roots. Intake
validates manifests/shards, preserves transitions and true seed/family/deck/
position grouping edges, rejects duplicate runs and mixed engine/schema epochs,
and enforces aggregate limits rather than multiplying them per root. Run hashes
scope episode addresses; they are not input features or replacements for groups.
The aggregate default stays 50 MiB. An explicit `--max-corpus-bytes` may admit
at most 100 MiB across all roots; each original run remains limited to 50 MiB
and each row to 2 MiB. The same limit applies during intake and sample loading.
This explicit capacity option passes all 39 cases in its four-module declaration,
including the 31 inherited cases; its larger charged-size controls are labeled
accounting protocols, not large-game training evidence.

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

## Same-State Preference Training

`scripts.train_qv_preferences.train_preferences` is an optional offline API that
reuses the same model and checkpoint contracts. Each row contains `state`,
`preferred` and `alternatives`. Supply `return` only when the actual
actor-relative terminal return was observed; otherwise omit it, not `null`.
All actions must share the state's authorized entity bank. Only checked actions
from that same position belong in the comparison; an unchosen action receives
no invented terminal outcome. The caller must verify original dataset/teacher
provenance and group-disjoint train/evaluation partitions before calling it.

The Q objective is listwise preference cross entropy, with a separate weighted
actual-return V loss only for rows with an observed return. A checked
nonterminal ordering preference can train Q without inventing a future value.
V MSE counts only observed targets; it is `null` when none exist. Metrics report
`value_samples` and `preference_only_samples` separately. Preference-only
updates leave the V-head parameters untouched, although shared-encoder changes
can still affect V predictions. Q is therefore a bounded ranking utility, not a calibrated
return or win probability. Heuristic teacher choices are not expert labels.
Feature-equivalent alternatives must be filtered before fitting, with original
rows retained and filtering reported; the API rejects indistinguishable labels.

Ranking optimization uses the unbounded Q-head logits, before runtime squashing
(`tanh` by default, softsign only in the explicit new mode).
Squashing first can attenuate the gradient or reduce the loss by saturating both
choices without correcting their ordering. This follows the
[cross-entropy logit convention](https://docs.pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html).
The existing `preference_loss` remains a bounded-score diagnostic;
`ranking_logit_loss` separately records the actual optimization loss, identified
by `ranking_loss_input`. Neither loss is a playing-strength measurement.
Strict ranking, margins and export parity still use bounded runtime Q, so
saturated runtime ties are not counted as successful rankings. Legacy runtime
Q/V, checkpoint shapes and feature encoding remain unchanged.

Preference `batch_size` is an optional integer in `1..256`, default `1`.
Each shuffled batch uses mean per-row raw-logit cross entropy, so rows with more
alternatives do not receive extra weight. The objective is the masked per-row
mean `mean_i[CE_i + value_weight * indicator_return_i * Verror_i]`: sum observed
V errors and divide by the actual batch length, including rows without returns.
Omitting a missing row's V-loss contribution is not an invented zero V target;
no V error or target is constructed for that row. A batch with no returns has no
V term and does not train the V head. Final partial batches use their actual
length, not the configured batch size or the number of observed returns. The default
one-row update order and resulting weights remain identical to the pinned old
trainer in the synthetic regression. The report separates `optimizer_updates`
(also `updates`) from `row_exposures` and records `batch_size`; progress
`processed` counts row exposures. Checkpoint provenance `updates` counts optimizer
steps and `samples` counts admitted rows, not epochs or exposures. The unchanged
100,000-row-exposure maximum and finite cooperative time budget apply regardless
of batch size. Batching does not authorize a larger corpus or training budget.

`tests/test_qv_life_context.py` exercises synthetic codec/boundary protocols.
`tests/test_qv_life_context_training.py` adds optional CPU Torch checks for raw
formula and Q/V parity, seeded/zero initialization, default-one-row equivalence,
observed-only V masking, batching/accounting and a two-row synthetic joint fit.
These tests do not copy archived private rows, publish fitted weights, qualify
full canonical game features, establish playing strength or authorize deployment.

Torch is imported only after admission checks. The trainer checks finite losses,
clips gradients, enforces bounded updates/time, and checks every training
candidate against standard-library inference before returning a checkpoint.
Its timer is cooperative, so callers still need an independent outer deadline.
Keep held-out rows out of optimizer updates and evaluate the saved/reloaded model
on separate tactical checks and fresh games. A successful fit or increased
teacher agreement does not authorize activation or establish playing strength.

Pure admission checks require no Torch installation:

```sh
python -m pytest tests/test_qv_preference_training.py tests/test_qv_preference_optional_returns.py
```

In the optional CPU-Torch runtime, `python -m scripts.check_qv_torch` also checks
actual context-sensitive preference learning and exported inference parity on
explicitly synthetic numeric inputs. This is not a gameplay-quality benchmark.
The optional CPU module `tests/test_qv_ranking_logits.py` additionally checks
wrong preferences under large positive and negative common score offsets,
including actual parameter updates and unchanged bounded inference diagnostics.

## Explicit Live Binding

`ai.learned_policy.bind_live_policy(raw_checkpoint_bytes)` validates and hashes
the same bounded immutable byte buffer. It accepts only the registered v2 actor
context contract for the current engine and requires positive update/sample
counts. Those counts establish eligibility, not the truth of a training claim
or measured playing strength. Supply the returned in-memory handle explicitly
to `AIAgent(learned_binding=binding)`. The adapter accepts no filename, HTTP
request, saved-match instruction or ambient setting as activation authority.

The bound agent ranks an existing heuristic shortlist of at most nine checked
actions, not the exhaustive legal-action space. A candidate with a genuinely
checked unanswered-win forecast takes priority over Q utility. Without a winning
line, an alternative not known to lose takes priority over a checked terminal
loss; unknown forecasts are not presented as proof of survival. Within the same
forecast class, highest Q and stable ties are retained. Unknown choices or
hidden-zone changes cannot establish that forecast. Every Q/V prediction still
requires validation, including candidates examined after a winning line. This
is tactical-safeguarded ranking, not a forced win against possible responses or
evidence that the weights learned the tactic. The router explicitly opts into
finishing already-declared defensive combat using the existing bounded checked
pass loop; default forecast callers keep their original stack-only horizon.
Any later own non-pass response, including a mana ability with potentially
nontrivial costs, prevents that forecast. Unresolved choices, unsupported combat
and hidden-zone changes stay unknown. If every critical block forecast is
unknown, the router defers to the normal heuristic rather than claiming neural
survival analysis. Shared actor-view projection
uses the supplied public moves without constructing another game or recomputing
legal moves in a masked world. Only semantic feature packs reach the model;
the original state is retained solely for authoritative action admission.
Incomplete choices, unsupported encodings, stale contracts, unusable candidates
and invalid numerical predictions retain the normal heuristic fallback. Stable
ties preserve shortlist order. A configured learned adapter does not mean every
decision uses neural scoring.

Registered learned ranking is in-game only. While `pregame_pending` is true,
keep, mulligan, required bottoming and opening-hand choices use the existing
heuristics, even with a valid learned binding. The tactical preference corpus
does not qualify those decision families; binding a model must not replace
opening-hand policy with untrained rankings.

Saved controller snapshots may retain a closed per-seat checkpoint identity and
feature/engine contract. Restoration never activates weights from that metadata.
The caller must explicitly supply a trusted agent whose actual validated
`LivePolicyBinding` has the same checkpoint SHA, contract and current engine;
otherwise the recorded identity remains with visible `restore_requires_opt_in`
heuristic fallback. An ordinary agent plus matching strings is not eligible.
The `mtg.live-policy.v1` envelope is emitted by
`backend/main.py::_live_policy_provenance`; its identifier is a provenance schema,
not a checkpoint architecture filter. Model validation is delegated to `QVPolicy`
by `backend/ai/learned_policy.py::bind_live_policy`, with the existing explicit
authority, positive update/sample and current-contract requirements.
Empty metadata preserves the legacy snapshot format.

The original three whole import-only controller/persistence modules pass all
40 cases. The later four-module lifecycle declaration passes all 69 cases,
including those 40 cases and 29 new startup, fresh-profile, restoration and
completed-history controls. Positive checkpoints in these tests are explicitly
labeled protocol fixtures, not trained models. Repository session doubles are
not actual SQLite or HTTP persistence qualification.

Trusted startup calls `main.configure_new_match_policy(binding)` before the app
lifespan. New AI seats retain their saved difficulty/archetype profiles and
receive only the validated binding; human seats do not receive it. Restoration
still requires the recorded identity to match the configured trusted binding.
Completed-game history retains a closed policy-provenance record using the
existing string-log storage; metadata is not a model-loading instruction.

The private operator configuration may explicitly add the closed object
`"learned_policy": {"checkpoint": "/owned/private/checkpoint.json", "sha256":
"FULL64HEX"}`. The checkpoint must be an owned private file outside source and
the served frontend. The supervisor starts `operator_start`, which checks the
expected SHA and binds the same bounded bytes before launching a single
loopback worker. Omitting this object preserves the original heuristic startup.
No HTTP endpoint, environment model selector or saved snapshot can choose a
checkpoint. A separate four-module operator declaration passes all 51 cases;
these are startup/file protocols, not an actual trained-model server run.

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

The optional progress/fusion comparison also needs the exact public pre-fusion
trainer, not a private game fixture. From `backend/` in a Git checkout with the
original commit available, using the separately installed CPU-Torch interpreter:

```sh
reference_dir=$(mktemp -d)
git show 2d50b00fd3f3ad37da1091a0223cfe5c6bac4bfc:backend/scripts/train_qv.py \
  > "$reference_dir/train_qv.py"
printf '%s  %s\n' \
  fdfb909f0e216715e6cab00a324fad4306ef755aab6580cb3a8ca9e99c375b58 \
  "$reference_dir/train_qv.py" | sha256sum -c -
QV_REFERENCE_TRAINER="$reference_dir/train_qv.py" \
  python -m scripts.check_qv_training_progress
```

The module rejects a different digest, a linked reference or an absent explicit
binding. The reference stays outside the checkout and is not an application
model or training corpus. Its four numerical/protocol tests are separate from
the original three CPU checks and do not establish playing strength.

The legacy environment/dataset declaration separately passed all 92 cases in
177.99 seconds, including the genuine exporter CLI children, after closing two
dataset locks in an old test fixture's `finally` block. No assertions or dataset
semantics were removed. This earlier component run preceded the live-adapter
extraction; it is not a second execution of the current 302-case declaration.
Real collection exposed a missing explicit defender mapping in the heuristic
teacher's untaxed attack declaration. The producer now materializes the core's
existing default opposing-player defender without changing strict action
admission, explicit defenders, costs or bands. All 122 cases in the five-module
producer declaration pass, including 14 new controls. Earlier incomplete runs
remain incomplete and are not eligible training games.

Four final-epoch games completed with genuine terminal outcomes: 514 and 366
accepted training-game steps, plus 701 and 629 heldout-game steps. Their selected
original files total 57,980,407 bytes. The original 50 MiB collection protocol
remains a failed protocol: its fourth run stopped incomplete at 510 steps with
`output_budget` and null terminal rewards. That run is retained as diagnostic
evidence, not relabeled or supplied as a terminal training game. A separately
declared, same-seed fourth run completed under the new capacity protocol without
changing the game rules, action cap or per-row limit.

The separately bounded, phase-instrumented verification completes in 524.35
seconds: the 510 accepted transitions and header are byte-identical, all four
terminal episodes retain the fixed split and group/fingerprint boundaries, and
no identical state-feature bytes cross the partitions. It admits 880 training
and 1,330 heldout decisions. The original 300-second verification timeout remains
preserved as a failure, not retroactively converted into a pass.

The first bounded fit performs all 880 optimizer steps but exits without a
qualified checkpoint; complete final metrics/export/reload verification is not
established. The separately declared longer-time attempt keeps the same data,
split, seed, iteration count and model architecture. It also completes 880
updates, then records the exact cooperative validation deadline at 1,204.25
seconds without publishing a checkpoint. Both input/runtime/resource closures
pass; neither run is a completed fitted model. The subsequent trainer change
adds an optional phase observer and shares the final-weight forward between
final MSE and export parity. All 41 default cases and seven actual CPU-Torch
checks pass, including exact reference weights/losses and preservation of the
last parity rejection. In the 65-sample protocol, Torch forwards decrease from
260 to 195 while all 65 stdlib comparisons remain. This is a measured work-count
reduction, not a measured speedup on the real games. The 64-sample progress
cadence reports a completed-count floor; fused-phase times overlap and must not
be summed. The real-game fit on this trainer remains pending.
No fitted-policy or expert-strength qualification follows from collected games
or completed optimizer steps alone. Final-epoch training/reload, heldout Q/V evaluation,
real-decision latency, checked live application persistence and matched gameplay
quality remain open. The separately qualified native 50-case declaration is
recorded in `current-2d50-native-browser50.md`; it does not measure learned-policy
strength or exhaustive browser/action coverage.
