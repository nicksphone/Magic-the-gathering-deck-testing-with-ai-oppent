# Root Metadata Copy Contract

This isolated candidate is based on immutable fb775e1e5d5cbc480b2be3f1ab8e1511c65536c7.
Only `game_state.copying.copy_match_state` and its imports change in production;
`_copy_card_field` is byte-identical. No mana experiment, game policy, field list,
history default, search limit, or state projection is changed.

## Implementation

For an exact ordinary MatchState with default root reconstruction, allocate and
memoize both the root and its attribute-state dictionary before visiting Card
fields. Copy every root attribute through the existing one-memo container
copier. Finish with `clone.__dict__.update(copied_state_dictionary)`, not an
assignment: references to the copied state dictionary remain distinct from the
clone's actual `__dict__`, as in stdlib reconstruction. Retain keep-alive entries.

Root subclasses, explicit root/attribute memo overrides, non-default root hooks,
custom attribute dictionaries and registered root reducers retain the original
fallback. The caller's memo is still copied, not mutated. `_field_copier` remains
a Card-field-only ablation hook. Arbitrary user hooks that change class copy
protocols during traversal are not certified by this bounded test inventory.

The original Card-first implementation had a reproduced correctness defect:
Card metadata that visited the root attribute dictionary before the root could
reconstruct a partial root and lose later attributes. Early allocation fixes
this, and intentionally makes the actual root and dictionary visible to nested
copy hooks. This is an explicit behavior correction, not just a speed claim.

## Actual Evidence

- Original whole NEW protocol module: 21 passed, 2 failed. One failure counted
  256 stdlib per-atomic root-metadata copies; the other exposed the partial-root
  defect. The module was unchanged for GREEN.
- Added preallocation module: first attempt 1 passed, 5 failed, including two NEW
  fixture errors from mutating the shared class's `__new__`. That ledger remains.
  Correcting only that NEW constructor control to an isolated subclass produced
  a clean 3 passed, 3 failed against unchanged production. The corrected module
  was then frozen before the product change.
- Required whole `test_ai_selective_copy`, NEW root-metadata module and NEW
  preallocation module: 34 passed in 14.42 seconds.
- Separate whole `test_nested_card_copy`: 8 passed in 2.61 seconds.
- An optional five-module composition stopped at collection because whole
  `test_payment_trial_copy` imports `test_mana_abilities`, which imports the API
  fixture and `main`. The existing guard denied that import. This failed epoch
  is retained as HOLD; neither that module nor the five-module cohort is claimed
  qualified. No filter, Main/SQL permission or old-test change was used.

All successful stages retained the same pre-import native audit and private-call
profile guard: 11 denial controls, no unexpected events, no database, equal source
and FRESH runtime maps (3674 files, 4 links, 429 directories), equal FD inventories,
no children or non-main threads. Runtime Python used `-I -B`, bytecode suppression,
inner alarm 900 seconds and outer TERM 900 plus KILL grace 15 seconds. These are
pure component tests, not HTTP, native-game or full mana-route acceptance.

## Controlled Direct Measurement

One private whole measurement case passed in 5.54 seconds. It made eight complete
copy calls on one genuine Factory-created 120-card public fixture: one warmup per
implementation and three randomized baseline/candidate pairs, plus one stdlib
reference copy outside timing. All complete results matched that reference and
the input pickle stayed unchanged. The baseline was exact pinned fb775 code.

Median whole-copy wall time was 80.120 ms baseline and 74.798 ms candidate
(three paired samples; roughly 6.64 percent lower in this run). Raw pairs and CPU
times are retained privately. The unchanged audit/private-profile instrumentation
remained active during measurement. This is a small controlled microbenchmark,
not an uninstrumented speed certificate, a native performance result, or proof
that this change solves the observed long payment-planning run.

No candidate has been applied to W or the frozen mana source. Whole35, 249/60
mana-route evidence, all 14 automatic-owner completion and native promotion remain
separate open acceptance work.

## Registered Set Protocol Correction

The original 34/8/1 candidate remains an immutable historical packet. Independent
review found a concrete root-metadata regression: its unchanged Card-field copier
uses `set.copy()` for exact atomic sets, bypassing a public registered set reducer
when that copier is newly used for root attributes. A registered stdlib set
dispatcher could likewise be bypassed. This finding does not require an in-copy
mutation of class protocols.

A separate epoch reproduced the defect with a whole NEW protocol module:
9 failed and 3 passed in 3.35 seconds. Only `copy_match_state` then changed: retain
early root/dictionary memo allocation, but select stdlib deepcopy for root fields
when a set reducer or set dispatcher is registered. The ordinary fast path and
all Card-field code remain unchanged. In particular, the partial-root cycle
correction is not discarded by returning to Card-first root reconstruction.

The identical NEW module passed all 12 cases in 3.38 seconds, covering direct and
nested sets, type/value/alias behavior, caller memo precedence, real dispatcher
precedence over reducers, sibling isolation, exception identity, dictionary/root
cycles through Card metadata, ordinary default behavior and Card-only ablation.
Both registries are restored in `finally` by the test utility.

One combined whole-module gate then passed 54 cases in 19.94 seconds:
`test_ai_selective_copy`, `test_root_metadata_copy_contract`,
`test_root_copy_preallocation_protocol`, `test_nested_card_copy`, and
`test_root_copy_registered_set_protocol`. All prior module bytes were unchanged.
The same 11 native/private denials, no unexpected I/O, complete source/FRESH maps,
FD equality, no children/threads/database and quiet directory fuser checks apply.

No measurement was repeated for the corrected epoch: the earlier guarded 6.64
percent result belongs to the earlier candidate only. The existing Card copier
policy is not newly claimed generally stdlib-equivalent. Main-compatible whole5,
whole35, all 14 automatic mana owners and native integration remain OPEN. Neither
W nor any frozen mana source was edited or overlaid.
