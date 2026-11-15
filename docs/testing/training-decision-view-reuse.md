# Training Decision View Reuse

The exporter previously reconstructed the same actor view separately for its
observation, prompts and optional public context. It now uses the existing
one-view bridge for an unmodified native TrainingEnvironment. Custom adapters,
subclasses and instance-level method overrides retain the public-method path.
There is no persistent view cache or change to the dataset format.

## Evidence

- New regressions first reproduced 20 unnecessary-view failures with 33 passing
  controls. The corrected 53 cases preserve complete records, canonical JSONL,
  accepted actions and final snapshots against the same-source legacy path.
- All four whole exporter/frame/context modules passed: 151 tests in 125.78
  seconds on the application runtime. No cases were excluded. The original CLI
  test made three actual child launches covering creation, resume and refusal
  to overwrite. Parent and child audit hooks reported no forbidden I/O.
- Canonical seeded roots cover both seats, pregame, mulligan, paid Bolt,
  announced spells and native Consider choices. Privacy, custom public methods,
  cancellation and teacher errors remain covered.

The earlier compatibility run excluded the CLI case and was not a whole-cohort
qualification. Subsequent harness attempts stopped before tests because of the
default logging path and an unpinned pytest collection root. Their logs remain
archived; owned logging and an explicit collection root corrected the harness
without widening I/O permissions or changing tests.

## Measured Scope

An independent current-source diagnostic replayed all 584 recorded actor frames
from the incomplete Midrange/Blue Control game exactly. The next choice took
0.1104 seconds unprofiled: the old collection timeout did not establish a
stalled decision there. A private checkpoint was saved before choosing.

Ten alternating view-recipe pairs at that checkpoint gave identical inputs and
unchanged roots. Median construction was 0.24860 seconds for the old recipe and
0.13526 seconds for the existing bridge. This position-specific measurement is
not a whole-game speedup, UI latency distribution or AI-strength result.

## Compatibility

Training snapshots bind the adapter source fingerprint. The edited exporter
therefore intentionally cannot restore a pre-edit training checkpoint; no header
was rewritten and validation was not relaxed. The benchmark used the unchanged
matching source. Normal application saved-match handling is not changed.

No model was trained or activated. The live gameplay backend remains separately
pinned to its verified draw-fix build. Broad strategic and full-game acceptance
are still open.
