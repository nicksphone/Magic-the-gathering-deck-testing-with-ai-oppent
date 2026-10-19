# Suspend and keep-hand intent audit

## Frozen scope

Test/report only, source copied from the immutable d3 published-source.tar in
parent-integration/backend-dependency-compatibility-20261006. No production change.
Use the independently qualified cached Python, not the older runtime interpreter.
Exact source/runtime hashes and all test nodes are recorded in the handoff archive.
Source-local disposable checkout, no .git, exact .private-choice-audit-source marker,
MTG_ISOLATED_TEST_ROOT explicitly set, empty local SQLite before the gate. Network
connections prohibited during HTTP qualification. Main/parent/live data untouched.

## Public contracts and measured views

SuspendAction accepts only type='suspend' and card_id. KeepAction accepts only
 type='keep_hand' and bottom_card_ids (default empty list). Both forbid extra keys.
Measured whole HTTP Suspend views on both seats contain exactly type, card_id,
card_name, mana_cost, time_counters, card_view. Engine views lack only card_view.
Measured keep_hand views contain only type. These are observed metadata, not a
blanket permission to strip arbitrary fields or authoritative choices.

## Terminal result

Two complete NEW modules: 68 executed, 32 consumer failures, 36 positive controls,
133 warnings, 112.54s, exit 1, timeout bound 900s. No skip/xfail/deselection. Every
failure is the sole final unsupported-intent must-reject assertion (DID NOT RAISE).
Public model validation, raw lookup and HTTP 422 checks had already rejected each
request. Finally blocks confirm unchanged input and full training root; the HTTP
rejection helper checks authoritative snapshot, controller data and SQLite dump.
No engine RED in these bounded controls; not a whole-engine certification.

Both seats, nonnull and null variants:
- Suspend: targets, from_exile, payment_choices, resolving_item.
- keep_hand: card_ids, bottom_count, player_id, resolving_item.

Independent positive controls never accept the unsupported request as a witness.
Suspend uses authentic full raw Rift Bolt and Ancestral Vision records from the
existing suspend_canonical fixture/provenance. Each record's hash is verified and
Oracle text retained unchanged. Both-seat whole views, deliberately typed actions,
actual payment/exile/time counters, no spell-count increment or stack creation,
encoded replay, private observations and HTTP restart pass. Source, timing,
unpayable and stale-source rejection controls pass.

keep_hand passes explicit reversed non-prefix ordered selections, typed/whole-view
augmentation, encoded replay, private observations, wrong-seat rejection and HTTP
restart at the supported legacy unbottomed resume boundary. Duplicate, opponent,
stale, incorrect-count and null bottom choices reject without mutation. No chosen
IDs are inferred from the bare view. The legacy boundary intentionally uses the
already-supported mulligan_count/bottomed compatibility state; it is not represented
as a current offered London bottom-selection hint.

Current London flow is separately executed for both seats through TWO actual
mulligan rounds and explicit choose_mechanic bottom selections, including pending
snapshot restore/replay/privacy, followed by whole-view keep_hand/HTTP restart.
keep_hand cannot replace the pending choose_mechanic action. The current API does
not advertise bottom candidates in the keep_hand view.

## Narrow proposal, not implementation

Guard exactly suspend and keep_hand in lookup_intent using public SuspendAction and
KeepAction before complete_action. For suspend, accept only measured presentation
fields with exact current-actor offered-view matching; keep_hand has no measured
display metadata. Preserve explicitly selected bottom order and all existing guard
branches. Reject unsupported keys even null; never infer source, target, actor,
payment or bottom choice. Public API, engine and normalization helper stay unchanged.

No other Suspend cards, special costs, mechanics, omitted-choice inference or
complete London UI coverage is claimed. Existing authentic fixtures sufficed; no
external retrieval or new fixture/provenance was needed.
