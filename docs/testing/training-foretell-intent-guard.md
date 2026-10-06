# Foretell Intent Guard

## Frozen Dependency

Incremental over the immutable Foretell/Ninjutsu audit archive
`training-groundwork/foretell-ninjutsu-intent-audit-q2NlXB`.
Its test-only patch SHA256 is
`5b06cfe31ef1bf4ea2b116567186b8eedd37a4d8b0c5388214fb7f170960e13d`.
The source was reconstructed from its audited backend tar, not recopied from
moving main or a running parent checkout. All 960 original files passed
the archived manifest before any edit. Baseline manifest SHA256:
`2d853ab583fdbc31eb936d723ee1d540bd30e5f3c3fbd2123dfb4ef1c7112632`.
The graph report from that archive was read first; the isolated code graph
was refreshed after this change (AST-only, no external API).

The production precondition is `backend/training/environment.py` SHA256
`51053fc95f921958af7b2026a5bd87e3c5aaa163590587e08ba3af50ff298bb7`.
Its qualified postimage SHA256 is
`8416c70395a0c6436d7cb40e20824beac5c88cfdb65bc4be7c8c68fb29e9d017`.
Apply only this increment after the audit dependency, not a cumulative
replacement of prior guard patches. No parent/main/live files were written.

## Contract

Only `TrainingEnvironment.lookup_intent` changes in production: import and
bind the actual public `ForetellAction`, then add its foretell branch.
The public model validates all non-display fields before `complete_action`.
Unknown requested fields reject even when null; invalid/missing chosen
`card_id` rejects before the helper. No card, face, cost, target, resource or
continuation choice is inferred. Raw API, typed lookup, encoded actions,
schema, producer, engine and AI helper remain unchanged.

Qualified display keys are exactly `card_name`, `mana_cost`, `fixed_costs`,
`granted_reductions`, and HTTP's `card_view`. Any supplied key must match
the actual current eligible foretell view for the explicitly selected card
and actor. `card_view` must match the actual serializer on that same copied
state. Null, changed, extra nested or choice-shaped metadata rejects before
normalization. Missing action fields are never recovered from display.
Raw HTTP still rejects even genuine display keys; submit a complete typed
action, not the whole view, to the raw API.

Matching display requires generating legal moves on a private root copy;
bare typed foretell intents avoid this additional display comparison.
This is not a full-hand performance qualification. New producer metadata
must be independently qualified, not silently allowed.

All 17 prior model bindings and all 12 prior display branch bodies are
byte/AST unchanged. Removing only the foretell import, binding and branch
from the postimage makes the entire module AST equal to the preimage.
The initial invariant probe mistakenly included the outer enclosing guard;
its unsuccessful diagnostic is preserved separately from the corrected
passing proof. No production change was made in response to that probe.

## Qualification

- Focused: original 34 audit cases unchanged plus 56 new controls;
  **90 ordinary PASS**, 129 warnings, 96.09s, exit 0, bound 900s.
- Neighbors: ten whole selected modules;
  **735 ordinary PASS**, 168 warnings, 236.39s, exit 0, bound 2400s.
- No skips, xfails, pruning or deselection in either gate. Both are serial
  and use fresh, source-local SQLite. No foreign DB/symlink or live network.

The original audit module remains SHA256
`fdb503b144c561226572d4f3461c6238f1673f54442c8d41fbe8d0cd45b3877d`.
Its immutable baseline **16 consumer RED + 18 controls PASS / 54.35s** stays
in the prior archive; this fix makes those same 34 assertions ordinary
green without adaptation or contradictory witnesses.

New controls cover both seats: unknown/null authoritative fields;
missing/null/object/empty card IDs; exact/null/changed/nested display;
whole engine/HTTP legal views; no missing-card inference; wrong-actor and
stale-view rejection; raw HTTP/root/controller/DB atomic rejection; actual
typed HTTP execution, persistence and restart. Before-helper tests observe
calls with a spy that delegates unchanged to the real helper, not a fake
validator or fabricated successful result.

The unchanged audit supplies canonical Doomskar full Oracle, exact special
action/cast costs, later-turn actual destruction, deterministic snapshot and
encoded replay, actor-private input permutations, observer-qualified exile
privacy and zone-incarnation controls. HTTP restart preserves the actual
foretell record and face-down state; this does not redesign HTTP seat
authorization or the existing two-human hot-seat response policy.

Neighbor modules are recorded verbatim in `evidence/neighbor-modules.txt`:
training environment/dataset/example export, public AI action contract,
three canonical foretell mechanics suites, public mana intents, cast/ability
allowlist and combat intent guard. This is selected qualification, not the
full repository suite or a claim about newer parent/main source.

The 961 backend files, including the new guard test, have identical manifests
before and after both gates:
`61cd7f0f682c557728f8392daefa68afc0ebb812afab52fc20f984a0ea8d4b89`.
Docs and graph evidence were added after tests and are outside that tested
backend manifest. SQLite and generated image/cache files are diagnostics,
not patch/runtime dependencies.

## Remaining Limit

Ninjutsu remains unqualified: no copied JSON supplied a complete canonical
Ninja fixture. No shortened Oracle fixture, fabricated card, skip or implied
Ninja support was added. This increment neither adds its consumer guard nor
claims its execution/privacy/timing/cost/restart coverage. No neural-policy
competence or expert-dataset claim is made.
