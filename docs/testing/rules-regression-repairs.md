# Cross-Family Rules Regression Repairs

## Scope And Provenance

The independent rules agent's first handoff (`701cd19`, base `f35cb4bc`) adds
19 canonical Scryfall records, pinned rules references, and 30 deterministic
interaction cases. Its historical report is preserved without rewriting its
original failures as passing results. The backend owner reproduced the same
14 failures and 16 passes on main `26c973449fa25591b6fc99d873512b13d8225e92`
before repairs. These are interaction positions, not tournament decks or a
measurement of AI strength. No card text or expected outcomes were invented.

## Implemented Shared Paths

- Compound counter instructions retain supported draw/scry/surveil follow-ups.
  A recognized conditional destination applies only when countering succeeds;
  an uncounterable target does not suppress the later draw. Stack departure
  still respects flashback/aftermath exile and physical-card ownership.
- Recognized graveyard-card exile instructions expose legal graveyard targets
  and resolve through a zone-specific handler, without broadening battlefield
  exile effects. Subsequent draws occur only if the spell can resolve normally.
- Recognized creature-return/life-loss instructions lock mana value in the
  graveyard and preserve it through entry-counter choices. Life loss occurs
  after entry and before stacked ETB abilities resolve. Entry updates the
  object's zone-change identity rather than assigning its zone directly.
- Undying uses effective pre-death keyword instances and counters, ordinary
  APNAP stack triggers, the old controller, and return under the original owner.
  Graveyard/object identity guards prevent old triggers from returning a later
  incarnation. Entry counters use the shared replacement and restart paths.
- The canonical global damage-doubling clause participates in player/permanent
  replacement candidates independently of source controller. Each selected
  source is used once, including across human choice/restart chains. Doubling
  is not prevention and remains active when prevention is prohibited. Shared
  combat player-damage paths apply the same replacements.

## Acceptance And Evidence

- [x] Independently reproduce the untouched 30-case handoff on current main.
- [x] Repair all 14 failures without weakening assertions or adding skips.
- [x] Pass 195 cases: the 30 new cases and 165 relevant existing regressions.
- [x] Pass 24 additional repair-edge cases, both seats where applicable,
  including exact SQLite restoration and atomic wrong-actor HTTP rejection.
- [x] Pass a 118-case follow-up covering the final death-LKI implementation,
  agent cases, all repair edges, entry routes and counter replacements.
- [x] Review terminal full isolated backend gate and resolve any failures.
- [x] Review frontend lint/contracts/build and browser integration gate.
- [x] Review five pinned pair manifests, both seats and repeated execution.
- [x] Archive verified source/evidence on NFS.
- [x] Publish the milestone after the final documentation/graph checks:
  `0ce8fe1`, pushed to `origin/main`.

All backend tests use disposable source copies with their own local SQLite
databases. Tests never run against the live checkout's database. Running scratch
is local; completed verified evidence belongs on RCHFiles. The agent's first-wave
archive and independently produced repair evidence remain distinct.

The initial broad gate caught two multiline Surveil regressions introduced by
the counter-reader change. Whitespace handling was corrected without weakening
the existing assertions; the 161-case affected selection passes. The final
four-shard gate passes 7,187 tests. Two subsequent HTTP-edge cases pass with all
24 edges, and their complete shard is rerun: 1,900 + 2,428 + 1,088 + 1,773 =
7,189 passing cases across the final test files. The unchanged production files
are compared against the frozen gate source before publication.

The original frontend lint, five contract scripts and build pass. The original
41-script Chromium harness passes on its captured pre-whitespace-correction
backend, including process restart and natural BO3 flows. Separately, frontend
test/lint/build and the UI agent's five integration suites pass on the corrected
backend with the new UI. Its complete 41-script integrated rerun is delegated
in `ui-integration-plan.md`; do not conflate those distinct source combinations.

All five pinned pair manifests finish: ten seat-balanced samples, each repeated
twice, with zero determinism failures, timeouts or recorded anomaly categories.
The reversed Blue Control/Ramp sample resolves at turn 52 but takes substantially
longer than the other pairs; no planning-latency claim follows. These replay
sources precede the newline-only counter correction; the manifests contain none
of the affected compound counter cards. Final-source counter, backend and UI
checks are reported separately rather than mislabeling the replay source.
An independent instrumented reproduction confirms actual turn progression and
retains per-decision inputs/timings for the next performance investigation.
No broad simulator-strength or deck-balance claim follows from ten samples.

## Remaining Boundaries

- The counter reader covers the stated bounded clauses, not arbitrary tax,
  conditional payment, library-position destinations or every compound spell.
- The linked-return reader does not implement every characteristic-dependent
  follow-up instruction or general enter-instead-of-return replacement.
- Global doubling does not certify source-scoped damage multipliers, prevention
  shield ordering against every replacement, or mixed Soul-Scar Mage-style
  event conversion. Those need unified event-level ordering and golden tests.
- Undying is not persist, general death-recursion parsing, or all ability-grant
  conditions. Granted supported keywords use shared effective-ability reads;
  unsupported grants/layer dependencies remain unsupported.
- Parser recognition, a passing fixture and repeatable matches are not proof of
  complete card support, arbitrary Magic semantics, expert AI or deck balance.
- The UI redesign and release/storage work remain separately owned agent tasks.

Integration follow-up: UI and offline storage tools have since landed in main
as distinct milestones. The complete integrated browser harness passes after
correcting its stale collapsed-log expectation; see `docs/ui-redesign.md`.
Their release/long-session limitations remain, and the next casting/trigger
batch is open rather than included in this rules gate.

The second regression investigation is assigned in
`rules-regression-next-plan.md`, focusing on costs, faces, targets and AI legality
without modifying engine code or duplicating these five repair families.

Verified source, gate logs, replay inputs/results and combined UI checks are
archived at
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-repairs/20261004T213559Z/`.
`SHA256SUMS` was read back successfully; the validated-gates archive was compared
against its local source. A prior archive attempt used incorrectly ordered tar
options and is not acceptance evidence; use `validated-gates-verified.tgz`.
