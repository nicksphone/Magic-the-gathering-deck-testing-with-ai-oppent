# Creature Subtype Separators and Ray Cleanup Tests

Current composition over published selector commit
`3978b30053d2726f9d6492ce6dd1d26b50bd2d6c`.

The shared creature subtype reader now accepts spaced ASCII dash, en dash,
and em dash separators, matching the existing land-type parser convention.
It does not infer subtypes from unseparated words. The three unchanged
continuous-static-effect tests that failed before this correction now pass.
Seven new probes exercise the parser ABI; they are not canonical card fixtures.

The independently approved Ray test adaptation retains every original
assertion and Act branch. It first checks the real counterable delayed tap
at cleanup, restores the snapshot, and passes priority to resolve that trigger
before checking the final tapped state. No trigger or effect is injected.
The original immutable audit artifacts are unchanged.

## Executed Acceptance

Ten whole modules, **183 passed, 2 warnings, 27.58 seconds, exit 0**:

- `test_changeling_subtype_layers.py`
- `test_continuous_source_queries.py`
- `test_continuous_static_effects.py`
- `test_continuous_static_order.py`
- `test_domain_land_type_layers.py`
- `test_graveyard_stat_selector_audit.py`
- `test_graveyard_stat_selector_product.py`
- `test_replacement_and_layers.py`
- `test_creature_type_separators.py`
- `test_temporary_control_lifecycle_audit.py`

SQLite aliases and network operations were denied before pytest collection
with a process audit hook; no subsequent forbidden attempts were recorded.
Production/test hashes remained equal throughout the gate. Dependencies were
reused, not freshly installed.

The adapted HTTP module is present but **not executed in this qualification**.
The original mixed-I/O 149-test cohort remains unstarted pending a new owned
SQLite/startup contract. No browser, live-service, full-card, full-suite, or
general control-layer correctness claim follows from these tests.

Evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/subtype-ray-current-20261007/`.
