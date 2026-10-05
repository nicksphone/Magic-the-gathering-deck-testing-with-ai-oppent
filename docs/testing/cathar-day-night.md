# Day/Night Entry And Linked Exile

## Implemented

Shared entry preparation and commit choose the daybound/nightbound face for the
current designation. This applies to spell resolution, non-cast entries and
linked returns without changing a pending spell's front-face characteristics.
Night entry uses Moonrage Brute, not Brutal Cathar's front-face exile ability.

The trigger matcher recognizes the bounded self instruction "enters or
transforms into [current face]" and uses ordinary human/AI target selection.
Targeted exile-until-source-departure uses the existing linked-exile ledger.
Transformation is not departure; actual departure returns linked cards. A
departed/blinked source before resolution does not exile, and a departed/blinked
target is a new object rather than the original target.

No card-name exception, altered Oracle text, statistics or deck balancing was
added. Full Scryfall responses and SHA-256 provenance back the cached fixture
facts; cache defaults/face aliases are checked explicitly.

## Validation

- Frozen old runtime: 34 of 35 canonical tests fail, demonstrating the defect.
- Composed candidate: 433 focused checks and 35 canonical checks pass.
- Live-revision isolated copy: 106 focused entry/transform/linked-exile checks
  pass. Added provenance and actual API tests pass 42 overlapping canonical/HTTP
  checks, covering both seats and none/day/night designations.
- HTTP names/quantity match creation retains cached faces. Real cast/pass/target
  actions, serialized views, pending target choice and linked exile survive
  SQLite restoration. Controlled canonical boards isolate timing from shuffles.

Evidence is retained on RCHFiles under `cathar-369726e-vIWuTz/` and the parent
hotfix qualification directory. API checks use disposable local databases, not
the live user's saved game. Dedicated [Cathar browser acceptance](cathar-browser.md)
now passes six cases on both seats, including pending choices, two real backend
restarts and 48 actual-App HTTP actions. Parent composed-source execution also
passes all six. Shared browser CI runs the dedicated gate after Officer, once
ordinary owned services stop. Lightweight ordering and isolation checks pass;
an actual hosted full-gate execution remains unverified. These results are not
universal transformation or Oracle certification.

## Existing Games And Remaining Work

Saved games are preserved. Already-missed effects are not retroactively created;
exercise a new entry or a legitimate later transformation to test the repair.
Arbitrary combined trigger clauses, unusual linked-exile instructions and broader
day/night replacement/layer interactions still need separate coverage.
