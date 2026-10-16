# Task 1.3: canonical positive Saga fixtures

Base: `36ce25f52cae12c9f6f0faf9f6b32e4bedb903ab`. This bounded test/data-only
sidecar changes `test_sagas.py`, with a uniquely new helper and fidelity module.
It does not close the literal repository-wide Task 1.3 requirement or Phase 1.

All six original test names and all 42 assertion ASTs are unchanged. The first
three synthetic Test Saga tests are byte-identical. Their constructor remains
the default branch of `_saga_state`; the new optional source argument only lets
the two real Fable tests supply their canonical permanent at birth. IDs,
positions, counters, owner/controller changes, turn/timing setup, stack
resolution, last-known/zone behavior and snapshot assertions are preserved.

Fable now comes from the complete pinned seed155 parent, is normalized by the
existing `ScryfallSyncService._normalize_payload`, and has its printed front
materialized by `apply_transform_face`. Both full ordered cache-projected faces
are fresh per setup, including printed restoration fields. No Test Saga is
renamed into Fable and no hand-authored mana/type fields override it. The
Corruption of Towashi observer uses the unchanged committed
`day_night_apnap_canonical.permanent` and its complete official RAW object
(`9eecdd8eb4e08a9363414acfefae08e4cfb7180825f01a07396c7b781156d170`),
including current wording. Its ID, owner, controller and battlefield position
stay unchanged.

Kumano's factory input now carries its complete seed155 parent, plus the
original quantity and actual front-face transport name. The factory retains
full RAW faces and materializes the real front. The original assertion that
its types are exactly `["Enchantment"]` passes unchanged; new fidelity controls
also require the actual front name, complete faces and printed restoration
metadata. There is no handwritten `I — Draw a card` under Kumano's real name.

The shared canonical helpers, seed and Towashi RAW/provenance are unchanged.
No network intake, production/parser/rules change, database, native game,
browser, provider, dependency copy or package installation was used.

## Actual qualification

- First whole original plus new fidelity RED: 8 failed, 7 passed, 2.46 s.
  All six originals passed. Captures inspect the real original tests' source
  births before chapter consumption and actual factory input/output, not an
  unrelated standalone builder.
- The new factory-fidelity expectation was then corrected to require its
  exact full RAW faces, rather than normalized cache faces. Original tests
  were still byte-unchanged. Same whole RED: 8 failed, 7 passed, 2.47 s.
- Fixture-only GREEN with that same fidelity source: 15 passed, 2.46 s.
- Final four whole modules: 48 passed, 4.65 s. These are `test_sagas.py`,
  `test_sagas_canonical_fixture_fidelity.py`,
  `test_transform_draw_current_wording.py` and
  `test_day_night_apnap_fidelity.py`. The 15 are included in 48, not additional
  independent samples.

Each run used the same precollection native audit ceiling, with seven exercised
SQLite/socket/child/provider denial controls, `--noconftest`, no filtering and
an outer 300 s TERM / 15 s KILL bound. All SQLite aliases were denied. There
were zero unexpected I/O attempts, no database or source-media additions,
unchanged existing source and 2,946 runtime regular-file hashes, matching FD
sets, no remaining children or extra threads, and disposal of the unused
import-created engine. This is a bounded pure fixture qualification, not a
full backend, full AI, native gameplay, browser or release certificate.
