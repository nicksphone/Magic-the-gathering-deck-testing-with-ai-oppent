# Versioned Actor Decision Frames

Status: the four whole regression modules executed 70 ordinary passes in 54.23s
on 2026-10-21, with zero failures, errors, skips or SQL/socket/process attempts.
This includes the original 50 structural cases, six causal public-reference
cases, two genuine draw-choice cases and 12 boundary cases. Source, selected
runtime, system inputs and resource closure checks passed. This is ordinary
trusted functional evidence, not a sandbox or kernel privacy certificate.
It is not a learned-policy, strength, whole-game or full-choice qualification.

The default `mtg.dataset.v1` exporter, observation input, manifest and reader
semantics remain unchanged. An explicit `decision_frame=True` option emits
`mtg.dataset.v2`. Its input is exactly `version`, `observation`, and `prompts`,
using decision version `mtg.decision.v1`. The exporter captures the acting seat's
actual `observe(seat)` and `prompts(seat)` before calling the chooser. It does
not reconstruct prompt context from a selected action or private snapshot.

`training.decision_frame.build_decision_frame(observation, prompts)` returns
the detached frame and a private reversible binding object. The reverse map is
never serialized. Prompt-only options require authorized semantic descriptors;
an unresolved reference is an explicit error, not a zero vector or hash feature.
Accepted complete actions remain labels. Actor terminal rewards, source hashes,
seeds, grouping metadata and future observations are never input features.

`encode_state(frame)` and `encode_action(frame, aliased_action)` return
`mtg.features.v1` packs with exactly `version`, `root`, and `entities`.
The closed node kinds are `null`, `bool`, `number`, `text`, `list`, `map`, `set`,
and `ref`. Reference indices gather prior semantic entity records; they are not
scalar features or learned identifier embeddings. Maps and set-like collections
use commutative aggregation preserving multiplicity. Lists, stack order, modes,
payments and ordered selections retain their order. All existing typed action
fields must be represented or rejected explicitly; codec protocol cases do not
certify that each payload is a legal game action.

The CPU model learns shared width-64 representations. Text uses learned UTF-8
byte embeddings, mean/first/second positional-moment pooling and a length signal,
then one dense projection per text, not a dense recurrence per byte. This retains
an order signal, not an injective text representation. Typed lists retain their
ordered learned fold. The revised ABI hash is
`0b3aadfead9f66999c8b6c3ddc13699ad7dc5dd1c76179e95585042ba0339ed5`.

Preflight limits are depth 64, 262144 nodes, 4096 entities, 65536 UTF-8 bytes per
text, and 1048576 total text bytes. Reject before deep copies or model allocations;
never truncate. The learner and inference reader validate the same closed tree.

The regression module is `backend/tests/test_training_decision_frame.py`.
It separates genuine native observation/action capture from explicitly labeled
codec protocols. Existing environment, action contracts and tests are unchanged.
The public composition requires a fresh graph update; private test-source graph
caches are not publication inputs.

The frozen baseline test helper incorrectly counted dynamic reference-map keys
as schema field names while also forbidding identifier TEXT features. The
approved separate correction excludes keys only for `target_distribution`,
`blocks`, `attack_targets`, and `damage_assignment`; it retains their parent
fields, all values, all actual schema fields, semantic `mode_targets` text keys,
all 50 cases and every assertion. The original test bytes and RED stay preserved.

## Opt-In Public Context

The byte-exact public schema files are [legacy feature v1](../schemas/learned-feature-v1.json)
and [public-context feature v2](../schemas/learned-feature-context-v2.json).
Their file SHA256 values reproduce the ABI constants below without an external
archive; preserve the original JSON bytes rather than reformatting them.

`TrainingEnvironment.decision_context(seat)` reads the current nonterminal
actor's view. `episode_records(..., decision_frame=True, public_context=True)`
captures observation, prompts and this context before the chooser. The new frame
is `mtg.decision.v2`, with the additional `public_context` field; encoding selects
`mtg.features.v2` and ABI
`9a1a15d9d41e4585bdb69a87150367df8f6f699c7cde98c84cb6cc07e84eaa06`.

The public announcement projection permits only `target_player`,
`target_card_id`, `target_card_ids`, `target_stack_id`, `target_distribution`
and `mode_targets`. Nested mode targets permit only `target_player`,
`target_card_id` and `target_stack_id`. It never copies a whole resolving
payload, private continuation, captured reference frame or hidden card facts.
Announcement availability is explicit and reference lifecycle remains `unknown`.

The bank contains all base entities first, then one-hop card/stack context.
Base and context records gather only earlier base entries; only root/action
references select appended context entries. Publicly announced unknown
references carry only their role and unknown visibility. Attachments and public
target incidence are retained, but this is not an injective graph encoding,
current-target legality proof, temporal model or full mechanics representation.
All entities share the existing bounds; there is no truncation or cap increase.

The genuine draw regression exposed a semantic namespace collision: an offered
choice ID `draw` incorrectly replaced the mechanic kind `draw` with an alias,
creating a self-reference. A one-line exclusion preserves semantic `kind` while
typed choice IDs/options remain references. The strict earlier-reference guard
is unchanged. Corrected tests also failed on the sealed legacy encoder before
the fix; their final version adds a direct assertion of the genuine frame kind.
The earlier invalid draft assumed an unlabeled producer and is preserved as a
test-oracle defect, not gameplay evidence. The first composed run's 68 passes
and two encoding failures are also preserved separately from the final 70 pass.

The engine content hash changes with these source posts. Checkpoint admission
must bind the exact engine/decision/feature/ABI tuple; do not relabel old weights
or repin old dataset manifests. Corpus production, real learned weights,
inference latency, live policy selection and generalization remain separate
acceptance work.
