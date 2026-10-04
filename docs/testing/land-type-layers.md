# Basic-Land Subtype Layers

## Implemented Boundary

A pure application-code view applies complete, unconditional basic-land subtype
clauses for all lands, nonbasic lands, controlled lands and an enchanted land.
It distinguishes addition from replacement. Replacement removes old land
subtypes and printed land abilities, preserves other card types/subtypes,
supertypes and colors, and supplies distinct intrinsic basic-land mana abilities.
Generated abilities do not overwrite cached Oracle text or snapshot base data.

Supported source-existence dependencies override timestamps when setting a
source land's types removes its printed type-changing ability; otherwise effects
use timestamps. This is a bounded dependency model, not full layer certification.
Controller, attachment, battlefield membership and timestamp changes invalidate
the immutable input cache. Entry evaluates the land's prospective battlefield
state without moving it or charging life during a view query.

Mana actions/payment, counted land subtypes, supported static predicates and
attachment scaling, landwalk, land-entry choices, AI color reads and public
type lines share this view. Public `base_type_line` remains printed; recovery
recomputes effective types from durable source state.

Mana eligibility and pool provenance belong to the selected ability, not the
whole permanent. Intrinsic mana can pay ordinary spells even when a retained
printed ability has a spending restriction. Automatic payment uses the same
stateful ability reader as affordability; amounts are recomputed after costs.
Already-produced restricted mana retains its original restriction after a
source changes types. Unsupported chosen-type ability clauses remain blocked.

## Canonical Evidence

Seventeen real Scryfall records are normalized in
`backend/tests/fixtures/land_types.json`: Blood Moon, Magus of the Moon, Urborg,
Yavimaya, Dryad of the Ilysian Grove, Prismatic Omen, Hallowed Fountain,
Dryad Arbor, Urza's Saga, Cabal Coffers, Spreading Seas, Lush Growth, River Boa,
Ancient Ziggurat, Unclaimed Territory, Cavern of Souls and Lightning Bolt.
Recognition of one clause does not establish complete support for these cards.

Rules reference: [official Comprehensive Rules, 2026-09-25](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
205.3i (land subtypes), 305.7 (replacement versus addition), 613.8 (dependencies)
and 614.12 (prospective entry). Raw downloaded records/rules and failed checks
will be archived alongside successful acceptance evidence on RCHFiles.

## Checklist

- [x] Reproduce twenty canonical layer/mana failures against the previous code.
- [x] Pass 444 expanded targeted checks, including 74 new regressions, both-seat HTTP rejection without
  memory/database mutation and SQLite restoration.
- [x] Pass 198 post-cost-recomputation mana/layer checks against the final backend.
- [x] Pass frontend lint, runtime contracts and production build.
- [x] Pass eight actual Chromium scenarios: six land-entry/mana/reload cases
  and two casts with automatic payment, chosen opponent and stack resolution.
- [x] Pass all 5,724 backend tests against the final frozen implementation across four
  isolated source/database shards. All 277 test files run exactly once; no
  failures, errors or skips. This is not a serial or fresh-dependency-install run.
- [x] Finish the complete final-source Chromium harness, including restart,
  sideboarding and natural AI/human BO3 paths. An earlier complete run also passes.
- [x] Finish 24 seat-balanced samples across Tempo, Dimir Control, Tokens and
  Ramp, each repeated twice: zero anomalies, timeouts or determinism failures.
- [x] Verify seventeen fixtures against raw Scryfall data and fourteen backend
  files across six isolated copies plus the final browser fixture server.
- [x] Refresh Graphify with AST-only extraction and zero API cost.
- [x] Compare and hash final evidence/source archives before publication.

Evidence is stored on RCHFiles under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/land-type-layers/20261004-working/`.
The final receipt is `final-acceptance.json` inside `final-evidence.tgz`; the
archive includes runnable validation, JUnit reports, raw canonical inputs,
source-parity hashes and all failed/superseded/interrupted attempts. Dependency
environments were reused, not installed fresh. The full backend run reports
748 warnings; passing tests do not establish dependency/security readiness.

The first browser attempt used an incorrect button label. The second correctly
activated a different land with an identical output label, exposing ambiguous
test selection rather than a rules failure. Both failed attempts are retained.
The final test selects the named source and checks its actual tapped state.
Earlier focused attempts also exposed a missing import and incorrect test
action names; failed runs are not counted as acceptance.
Late canonical tests reproduced eight per-ability restriction failures and
twelve actual spell-payment failures against the pre-fix implementation. The
first spell-payment baseline lacked a fixture and is retained as a setup failure,
not rules evidence. A browser target-selector wait was also corrected before
the final complete run passed. Earlier 5,698- and 5,710-test acceptance rounds
are historical checkpoints, not validation of the final backend.
Serial full-suite attempts were deliberately interrupted to include the last
reader correction and then switch to isolated sharding. Their partial results
are retained, not reported as completed acceptance. The final live Control/Ramp
BO3 recovery regression completes three games, including persisted restoration.

An initial 1,200-tick matrix had one Control/Ramp long-game timeout. The same
seed on the published implementation timed out too; all 2,863 normalized log
lines match the extended candidate's prefix. The extended candidate finishes
naturally at tick 1,286, turn 46. The final repeated matrix declares a 2,400-tick
cap up front; the earlier timeout remains part of the evidence, not a suppressed
failure or a forced result. These samples test repeatability, not matchup balance.

## Known Limitations and Next Upgrades

Arbitrary conditional type clauses, resolved spell-based subtype changes,
general dependency graphs/cycles, copy/layer interactions and simultaneous
multi-object entry are not certified. Granted activated mana abilities are not
implemented by this view; preserving a Saga subtype does not certify its chapter
effects. Non-tap, mixed-output and triggered mana remain separate open work.
AI reads corrected resources but remains heuristic, not seasoned-player AI.
The alpha UI redesign remains deferred; passing controls are not an ergonomics
or long-session certification.
