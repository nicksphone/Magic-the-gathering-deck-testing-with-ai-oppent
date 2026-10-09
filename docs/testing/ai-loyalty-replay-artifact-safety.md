# AI Loyalty Choices And Replay Artifact Safety

Checkpoint: 2026-10-09. This composition starts from published
`9d519b57ef7ab408af315a85a68f7c87d0bb3fd8`. Its only production changes are
`AIAgent._choose_action` and replay CLI artifact-path validation in `main`.
No rules, schema, frontend, deck contents or dependency versions change.

## Behavior

The actual agent now dispatches loyalty card selection and Aura attachment
menus using their distinct public action fields. Optional hand selection honors
zero/max counts and retained source references. Attachment uses a live offered
`choice_id`, legal current attachment options and the retained Aura reference.
Stale references do not follow a departed/reentered object. Hidden opposing
identities do not change the tested decisions. Offered-order selection is a
legality fallback, not an optimal strategy certificate or corrupted-save recovery.

Replay summaries, progress, pinned deck input, deck export, full traces and
decision metrics must name distinct artifacts. Validation runs before simulation
or diagnostic-file creation and rejects equal paths, symbolic aliases and hard
links. Distinct inputs/outputs retain their existing roundtrip and paired-seat
protocol. This prevents the CLI from overwriting pinned inputs or conflicting
evidence; it is not a general adversarial filesystem race defense.

## Actual Qualification

- Corrected new output-safety baseline: 15 strict rejection failures / one
  positive pass. All failures are `DID NOT RAISE`; baseline results overwrite
  the pinned deck input in the reproduced summary-alias case. These are mocked
  CLI contract checks, not natural games. The initial 16-failure draft includes
  one new positive-fixture error from its missing `observer` keyword argument;
  that separate ledger remains preserved.
- Focused composition: 48 passes in 8.34s, exit zero. These are the 16 output
  checks plus the unchanged 32 worker actual-agent assertions. The worker test
  imports the existing committed entry fixture instead of duplicating it.
- First combined 13-module attempt: 366 passes / 26 setup errors in 55.63s,
  exit one. Its pure guard denied the existing memory/file repository fixtures;
  the error, SQL-attempt and source-equality ledgers remain preserved.
- Same 13 whole modules, same ordered 392 nodes and unchanged assertions:
  392 passes / 450 warnings in 62.19s, exit zero. Only the declared memory and
  evidence-local `owned-test.sqlite` connections were admitted. All other SQL,
  sockets, subprocesses and source writes remained denied. There were 31
  connections and 13 file databases, no additional denied attempts, no remaining
  SQL file descriptors and only the main thread at closure. Actual direct fuser
  on those 13 files exited one with empty output. Source before/after hashes match.

The combined cohort includes the four complete AI information/projection/pending/
landfall modules, four replay/manifest/progress/metrics modules, the two
repository cohort modules, existing entry lifecycle checks and both new modules.
Counts overlap earlier component runs; they are not independent AI samples.

## Evidence And Limits

Verified evidence is under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/ai-loyalty-replay-safety-20261009/`.
The isolated runner redirects only runtime media-cache paths to owned evidence;
the real generator is unchanged. Native audit instrumentation is not an OS sandbox.

The independent worker's immutable-current-source 32-pass and 211-pass gates,
including its earlier denied-mkdir attempt, remain separately archived under
`gate2-corpus-readiness/loyalty-ai-current9d-fnx3_2f2-20261008/`.
This composition is not browser/HTTP acceptance, a natural-game benchmark,
13-archetype coverage, expert AI, complete-card semantics or release certification.
All original release requirements remain open where not independently qualified.
