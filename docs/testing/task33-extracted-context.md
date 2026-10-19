# Extracted Matchup Context

Over `92a59e1135fa53e1c4363734a61211bfb88e4a81`, training extraction now
preserves explicitly supplied opponent archetypes and action indices. It uses
the existing prior consumer's alias normalization and conflict handling; it
does not infer a matchup from hidden cards, deck names or teacher settings.
Indices must be nonnegative integers, excluding booleans. Unlabeled, unindexed
exports retain their complete legacy row. No policy weights change.

The new 29-case module first records 19 failures and 10 passes against the old
extractor. The corrected portable test plus both complete existing prior modules
pass all 122 cases in 1.34 seconds. The initial 122-pass packet depended on an
unpublished preimage in one new test; it remains held, not retrospectively
qualified. The corrected test uses a self-contained complete expected row.

Parent integration separately runs seven complete modules covering the launcher
and extraction/prior consumers: **185 passes in 7.72 seconds**, no failures,
errors or skips. All source and installed dependency hashes remain equal during
the run, with no unexpected I/O or measurement charges. Its first attempt had
145 passes and 40 fixture setup errors because the existing operator binary
environment binding was omitted; only the harness environment was corrected.

Evidence is private on RCHFiles under
`diagnostics/ci/task33-context-portable122-92a-qualified-20261015-3ILFAsXY/`
and `parent-integration/operator-context185-current92a-20261015/`.
These are synthetic explicit-event pipeline tests, not newly measured games or
trained artifacts. The incomplete matrix, matched quality comparisons and
remaining Phase 3 requirements are unchanged.
