# SBA Committed Graveyard Entry Product

## Scope and Immutable Input

One product file only: `backend/rules_engine/state_based_actions.py`, imports and
`_move_lethal_creature`, `_resolve_lethal_creature_batch`,
`resume_legend_rule_replacement`. No keeper-choice policy/API, handler, combat,
cost, keyword, events, plan, executor, helper or query-scope edits.

Reconstructed from the frozen audit source archive under
`holding-spells/sba-graveyard-entry-audit/mtg-sba-graveyard-audit-29ewS7`.
Its immutable dependency chain is archived fc22540 qualified precommit source,
original22 tests, graveyard consumer integration `34c662ec...`, committed emitter
`4ceec540...`, retained helper `f30fd208...`; full hashes and archive locations are
in `dependencies.sha256` and `reconstruction-input.sha256`. The published metadata
pin is `fc225406d56c1a2f177ccfa8fb0b6008448772f2`; qualified precommit input is not
misrepresented as complete published-commit byte identity. No moving parent roots
or later handler/keyword compositions were read or altered.

Exact SBA product preimage:
`95b354eb8cdb1f29c5ab630a8352727673a57453a7167304f060ccb271e5f6b0`.
Final postimage is separately frozen in `owned-postimages.sha256`.

## Commit Semantics

Every target's plan is selected before LBF publication, list changes or zone
movement. The complete lethal batch is prevalidated and all static replacement
causes are prepared before the first departure. Ambiguous library/exile selection
rejects instead of guessing; empty-string public selection retains unspecified
selection semantics, and explicit source IDs remain exact.

The original simultaneous LBF batch captures all battlefield LKI before any
member departs. The complete battlefield membership removal still precedes
individual retained-plan execution. Dynamic creature classification is retained
from that captured battlefield LKI, not recomputed after loss of type effects.
The shared executor owns destination membership, real move_to_zone identity,
exactly-once actual-GR publication, and retained static cause for a library shuffle.
Only actual GR destinations emit death events. Exile/library replacements do not
emit false dies/entry events. Death counters remain available until the existing
death collector consumes them and performs its existing reset.

Original stabilization loops, trigger staging, checked replacement choices,
zero-toughness/indestructible classification, keeper policy and readonly query
scopes are unchanged. Exile log wording was restored exactly; library replacement
logs now name the actual destination rather than implying death or exile.

## Assertions and Qualification

The original audit tests-only patch and all raw failing output remain immutable
in the baseline archive and are also retained as input evidence here. Applying
the product with the original 26 tests unchanged produced **22 PASS / 4 FAIL in
15.46s**: all 16 original desired reds passed, and only the four old exact
absence-of-entry characterizations failed.

`characterization-only.patch` changes only the one parametrized four-case LKI
test. It retains its death Oracle/types/controller/counter/trigger/private-view
assertions and strengthens it with exact LBF -> entry -> permanent-dies ->
creature-dies ordering, identical full captured LKI at each event, and exact
PRE/POST entry references, owner, previous controller and origin. Other original
test function ASTs are verified unchanged. No xfail, exclusion, missing-field
ignore, fabricated Oracle, name dispatch, manual event or fake stack item.

New product module has 20 cases:

- Actual paid Sickening Dreams, both seats: three simultaneous canonical creature
  deaths; batched LBF before all entries before dies; Traveler/Blood Artist real
  trigger counts; full restart; no query cache active at prepare/emit/commit.
- Actual paid Bolt, both seats: real pending state_based_die, exact offered source
  IDs, wrong-actor atomic rejection, restart before and after checked resume,
  exile without false GR entry or death.
- Controlled competing self/exile plans in single/batch/legend seams: full root
  and collector trace unchanged on rejection, including a later batch member.
- Controlled canonical indestructible Colossus at zero toughness in single/batch
  seams: actual library replacement, retained PRE static cause and real Probe
  trigger; no false dies; full restart. Counter placement is controlled, not
  claimed as an executed counter-placement episode.
- Controlled Humility departure between waves: ability loss causes actual GR
  entry first, then fresh classification/plan allows a later library replacement.
  Source departure is an explicit diagnostic seam, not a claimed removal spell.
- Controlled explicit single replacement choices: exact self-library versus rival
  exile destination, and invalid source atomic rejection.

Earlier final focused gate: **46 PASS in 19.19s**. Earlier 20 whole-module gate:
**525 PASS in 101.89s**. These share the pre-log-restoration product postimage
`0cc6aad5f9e352756b4e217ea03ad5b8d10fcef6344573d9b4b85aaf1cf76fb8`.
Final combined 571-case result on the final log-preserving postimage is recorded
separately in `final571.txt` / `final571.exit`; do not substitute earlier gate
proof for that final byte pin.

Whole modules include classification/per-card query batching, planeswalker query
order, legend/type regressions, death replacement and HTTP, layer/replacement
queries, committed emitter, unchanged original22 Kozilek audit, product episodes
and seams, retained helper lifecycle, self replacements/interactions, static cause
ABI and actual producer HTTP/resolution, basic-land hooks and canonical goldens.
All selected modules execute in full; HTTP cases are not deselected. This is
affected breadth, not a full-backend or later-parent-composition claim.

## Execution Safety and Honest Limits

Existing qualified Python 3.12.3 environment was reused; pins and pip dependency
consistency were checked, with no install. Each invocation is serial and wall
bounded (300 seconds focused, 600 seconds whole/combined). Audit hooks reject
network connects and SQLite outside the exclusive local source root. Actual
HTTP tests use fresh local memory/file SQL, paid actions, cache eviction/restart,
full SQL atomic rejection and both-seat private-view controls.

All unowned inherited backend files are hash-verified unchanged; mutable pytest
cache metadata is excluded explicitly, not product fields. Initial missing
basetemp-parent setup failure and new-test fixture/schema mistakes remain in raw
evidence; they were corrected in test scratch only and are not semantic greens.

Keeper choice remains the existing first-ID policy; no new keeper action is
claimed. Zero-loyalty/attachment shared-executor routes and delegated Saga
sacrifice were not rewritten. Direct handler/combat/keyword migration remains
outside this product. Simultaneous cross-zone observer coverage is bounded to
the executed cases, not all possible event interactions or printed mechanics.
Future historical receipt differences require exact actual-state diffs and strict
identity/publication assertions, not forced goldens or ignored fields.

## Artifacts

`production.patch` is the single-file increment. `characterization-only.patch` is
the separately reviewable four-case expectation adaptation. `new-tests-doc.patch`
adds the new product tests/report. `integration.patch` composes these three on
the frozen audit composition. Immutable baseline tests/output, command bounds,
pins, full snapshots and real collector traces are retained. Graph refresh is
AST-only evidence navigation, not runtime correctness proof. NFS archives are
read-back hash-verified and restored/apply-checked before scratch cleanup; active
SQLite is never run on NFS and databases are excluded from the source archive.

## Final Frozen Result

Final combined gate: **571 PASS, 1029 warnings, 101.68s, exit 0**.
Final SBA postimage: `0484c86f6a41da3b7cb68f84d0223bd70ddf62b609e8ad26056c57e68e3ac3dd`.
No active gate/PID remains. This proves this reconstructed frozen composition,
not the later parent Q7/handlers/keyword/performance composition. Sagan combat
caller audit remains a separately frozen parent-coupling dependency; no combat
writer or combat product hunk is included.
