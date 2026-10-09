# Portable Backend CI Inputs And Diagnostics

The full backend runner archives current Git HEAD into an owned local source,
sets both exact source markers and runs unfiltered verbose pytest. It does not
select modules, shard, fail fast or add skips/xfails. Existing opt-in tests and
fixture retention remain unchanged. Disabling pytest's cache provider avoids
the observed terminal cache write, not every possible storage failure.

The `58c34d09` workflow's backend ended in `OSError 28` writing cache/nodeids.
Earlier anonymous failure markers were not captured by name, so no gameplay
failure count or resource-only diagnosis is inferred. Frontend passed; browser
reached complete canonical Tamiyo admission and failed before this rules slice.

## Diagnostic Contract

Named node/setup/call/teardown records, bounded failure excerpts, collection
coverage and disk/inode samples are retained. The runner waits its bounded FIFO
sampler and preserves pytest/tee/evidence failure exits. Always-upload diagnostic
evidence is not a substitute for a complete passing test run.

Five observer-off/on generic seven-node pairs preserve exact nodes, phases and
exits: success, ordinary failures, interrupt, evidence write failure and real
ENOSPC via `/dev/full`. Missing/incomplete evidence never becomes a green result.
This qualifies the reporter, not the complete backend suite or a performance fix.

## Authentic Inputs

The deck-only BO3 fixture projects the exact selected decks from the archived
441 qualification. Its provenance pins the archive and original member; no
successful-preflight certificate or closed SQLite is imported. Existing native
series assertions remain, output directories no longer collide, and restore
uses the tracked genuine read-only cold worker instead of a missing audit script.
The final combined source must execute these full games/HTTP/cold episodes in CI.

GitHub-owned consumers validate actual `RUNNER_TEMP` ancestry, source identity,
both marker contents, absence of `.git` and absence of a source database symlink.
Export recovery receives its explicit fresh hosted-CI SQL contract, not a forged
local parent-approved grant. Packaging receives the verified current Git archive
and hash; historical local callers retain their original pinned archive defaults.

## Private Regression

The user explicitly kept the seven-megabyte synthetic trace private. Thirteen
protected repository secrets supply its compressed parts only to the backend
step. The preparer bounds input, verifies the sealed full SHA-256 and exclusively
creates an owner-only input file. The chunk variables are removed before tests.
Neither the raw/compressed/base64 trace nor input-derived Heat reports are
tracked or included in uploaded artifacts. Missing protected input fails closed;
fork pull requests cannot silently skip that regression.

Private assertions remain active but disable pytest value expansion and use
constant failure messages. Ordinary diagnostics are not a general redaction
system. The legacy replay now independently checks complete new color history,
retained target capture and pre-departure copy metadata before projecting only
fields absent from the immutable old receipt. All original gameplay/state
comparisons and the original sealed hash remain required.

Actual final local qualification: three complete whole pure modules, 86 passes,
28.06s, zero errors/failures/skips/deselections, unchanged source and no forbidden
native I/O. This includes 31 ownership/input/privacy controls, the original
49 friendly-damage/private replay cases and six independent corruption
controls. Cast-color and copiable-descriptor expected values come from retained
raw fields, not the corresponding production helpers; refreshed observation
fields are required, and full protocol comparisons reject numeric/boolean type
coercion. This final source includes the current Tamiyo/Aura production slice.
Earlier 48/1, 73/1 and intermediate review/default ledgers
remain archived separately. No local full BO3/CLI/packaging SQL gate is claimed.

Immutable evidence under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`:

- `diagnostics/ci/ci-harness-qualified-0c4-20261009-3kCICi/`
- `diagnostics/ci/portable-inputs-20261009-PKGPdr/`
- `diagnostics/ci/58c34-terminal-20261009-zDbOd6/`

The final strict-type coupled packet is archived separately from the intermediate
portable-input packet; the final parent/public postimages have byte equality.

The full configured remote backend, frontend and browser jobs remain release
prerequisites. Generic reporter and input-component passes do not close them.
