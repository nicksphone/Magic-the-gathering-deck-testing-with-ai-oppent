# Land and priority intent audit

## Exact frozen source

Source-only copy of ninjutsu-intent-guard-v7dOO1/evidence/qualified-backend-source.tar.gz,
consumer patch SHA256 `c86696a396f26ee9e08e4a0bb5fd74d15f73611bcbeb49bb809a465f6b872a8d`.
All 965 archived source files were verified before adding this NEW test module.
This is NOT the parent's newer nth/private composition. No engine dependency,
moving root, parent/main file or live database was read or changed. Own fresh
local SQLite per run; HTTP fixtures forbid external network.

Unchanged production SHA256 pins:

- training/environment.py: `1dc1c4f67931a2910c6af1133d585b5b6442794c6dc4072962e85f7eb8a11ff4`
- api_contracts.py: `73066efb66fbdce758885e6554dda0fab5d833cdc80041c83d16cd3e7d2373da`
- ai/action_contract.py: `17cda2570d58b0c17d3694990c74cc62bd360938e6d88d1b5ea54f739b542435`
- rules_engine/engine.py: `eb2ad608b61c6d9de5771ad82bca0c3dadc2bb2b7cc83d5f239b796a06d04690`
- rules_engine/keyword_actions.py: `55bae25b6894fd90218fc0b7c9cb13db1a4b07faf38d4081739354648776382f`
- rules_engine/move_generator.py: `3d38ea57162c4095e749b85e10b415506c5902ae9962b3c11139a35df433424c`

## Public models and views

api_contracts.py:68 PassAction carries type only. LandAction at :85 requires
card_id; permits strict origin booleans (default false), permission key,
selected_face_index and entry_choice. InputModel forbids all extra fields.
move_generator.py:151 emits bare pass_priority. Ordinary hand-land views at
:295 carry type/card_id; HTTP main.py:781 adds card_view. _land_moves at :24
also supports deliberate entry_choice and graveyard permission metadata;
face/exile producers are separate branches. Those special mechanisms were
inspected as schema/view context, NOT execution-qualified by this basic audit.

lookup_intent's existing 19-family guarded map does not include either family.
It calls complete_action directly; that helper filters to public model fields.
Therefore unsupported request fields can silently disappear before checked
legality. Raw API, encoded/raw lookup and engine legality are not weakened here.

## Terminal evidence

Final complete 48-case run: **32 ordinary consumer failures, 16 independent
passes**, 103 warnings, 72.77s, exit 1, timeout bound 900s. No skips, xfails,
deselection, contradictory acceptance witnesses or production changes.
All 32 failures are final unsupported rejection expectations: DID NOT RAISE.
Each first verifies public schema rejection, strict lookup rejection, HTTP 422,
full root/controller/SQLite-dump purity and input immutability. Unsupported
player_id, phase, resolving_item and targets appear both null and non-null in
both families/both seats. A delegating real-helper spy requires rejection before
helper; that postcondition is not reached because current consumer accepts.
No unsupported intent is executed as a supposedly valid control.

Independent controls use actual canonical Mountain/Island instances from seeded
existing built-in decks, not edited Oracle or invented cards. They deliberately
play the second of two hand lands, leaving the first in hand, or pass priority
without advancing phase after one pass. Whole engine/HTTP views, typed HTTP
execution, exact encoded replay, snapshots/restart, wrong actor, land combat
timing rejection, opponent hidden-order byte equality and reversible private
action aliases pass for both seats. Missing/null/empty land IDs reject; no source
or actor is inferred from suggestions. Valid land actions explicitly declare
from_exile=False/from_graveyard=False, preserving public model default semantics.

Draft1 is retained: 32 consumer failures, 12 passes, four test-comparison
failures, 113.67s, exit 1. The four controls incorrectly compared omitted false
origin defaults to normalized typed output. Only independent valid scenario
declaration was corrected before the final full run; unsupported sole rejection
expectations were not weakened. Draft1 is not engine evidence or green acceptance.

Final before/end 966-source-file manifests match, SHA256
`4b020c524c5cc08274189463ce6429452615459a23ce74b8eb35e051aae8d5d7`.
All 965 original source hashes match the frozen preimage. The new test SHA256 is
`fce1da1842f44bda04d10e8b1da03a32a90d2d13f4b1b6818795295550159f5b`.

## Narrow proposal only

Authorize lookup_intent-only pre-normalization guards using PUBLIC LandAction
and PassAction, preserving existing 19 guards. Pass display allowlist should be
empty for qualified bare views. Basic land HTTP card_view should be exact current
actor/source-qualified presentation, not an authoritative choice container.
Reject unknown/null aliases before complete_action; preserve explicit origin,
face, entry and permission fields without selecting missing cards or choices.
Do not blindly allow unqualified special-face/graveyard display metadata. Add
actual supported-view controls before any such widening. No implementation is
included; this two-path artifact supplies regression tests and this report only.
No special-land coverage, generic mechanics, UI completion or policy competence
claim follows. The unrelated Ninja engine failures are outside this run.
