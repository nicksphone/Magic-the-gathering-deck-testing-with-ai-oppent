# SBA Graveyard Entry Audit

## Frozen Source and Scope

Tests/report only; no product edits. Published metadata pin is
`fc225406d56c1a2f177ccfa8fb0b6008448772f2`. The copied input is its archived
qualified precommit source (`source-qualified.tar.gz`, SHA256
`75ba838e12ebde5414e42a71eb641aeeba0b851b2a5ba61c72a35ad50314e8d6`),
not a claim of whole-tree published-commit byte identity. Published backend
postimages were checked. Applied immutable dependencies, in order:

1. Original 22 tests, patch `b8f7b6089bf569bd86987d0f050ffbb8d2f044aa5324bac2ef4b1fd7e2f1945c`.
2. Graveyard consumer integration `34c662ec987c6a9ad6cfcc06c4327d1ff18fb272f1cf3219f7e98a9ca63a9751`.
3. Committed-entry emitter `4ceec540095e1eb058c969d99db8761cd2516700b533f9ffa0058d77b1b17eea`.
4. Retained shuffle-reference reader `f30fd20873291fd03b73e356da3a4e0b05bf4fc493e3522a7189254e3ecfff3c`.

Unchanged SBA preimage:
`95b354eb8cdb1f29c5ab630a8352727673a57453a7167304f060ccb271e5f6b0`.
All inherited backend files were hash-checked during and after execution.
No moving parent root, live database, dependency install or production edit.

## Executed Ledger

One bounded serial invocation of `tests/test_sba_graveyard_entry_audit.py`:
**16 ordinary failures, 10 passes, 82 warnings, 14.54 seconds, exit 1**.
No setup errors, skips, xfails or exclusions. No additional coupled gate.
Interpreter was the existing qualified Python 3.12.3 environment; package
versions were checked against the retained dependency pins.

| Actual action family | Cases | Result |
| --- | ---: | --- |
| Paid Bolt / Traveler identity and entry, both seats, own/foreign ownership | 8 | FAIL |
| Same paid Bolt death LKI, controller and private-view controls | 4 | PASS |
| Paid second Kozilek, legend departure identity and owner trigger | 4 | FAIL |
| Actual checked legend replacement-source choice, both seats | 2 | PASS |
| HTTP paid Bolt, memory/file SQL, both seats, restart then identity | 4 | FAIL |
| HTTP invalid Bolt target, full root/controller/SQL immutability | 4 | PASS |

Canonical full raw rows are reused unchanged from existing self-graveyard
audit/interactions fixtures and spell-admission safety support. No synthetic
Oracle, fake indestructibility, manual event injection or manufactured stack
item. Actions use `checked_action` and real paid resolution. Initial phase and
foreign ownership are explicitly controlled fixtures, not claimed natural
episodes; `ordinary_position` is fixture-only, never runtime repair.

## Grounded Findings

Paid Bolt actually reaches `_resolve_lethal_creature_batch`, not only the
single-creature helper. Traveler enters the owner's graveyard but its sequence
stays 1 instead of 2, and no target `enters_graveyard` is collected. The resolving
Bolt itself does publish its own stack-to-graveyard entry: this is not a claim
that all entry publication is absent. Actual death LKI preserves printed Oracle,
creature classification, counters and battlefield controller. Traveler and Blood
Artist death triggers retain that controller, including foreign-owned targets.

Paid second Kozilek resolves its real cast draw trigger before permanent entry.
The current legend rule then sends the new permanent to the graveyard through
`resume_legend_rule_replacement`. Its sequence stays 2 instead of 3; no owner
graveyard-shuffle trigger or entry event is collected. No graveyard event was
injected to make these tests green.

Actual RiP/Leyline replacement-source choice is offered and checked, including
wrong-actor rejection and restart. It is **not** a legend keeper choice:
`_apply_legend_rule:318` retains the first ID without offering a keeper action.
That interface limitation is separate; no invented `choose_legend` was used.

HTTP tests use fresh local memory/file SQL and in-process clients with network
connections guarded off. Successful cast/pass requests, cache eviction and
restoration, private-view checks and SQL observations execute before the desired
sequence assertion fails. Invalid-target HTTP controls return 422 and preserve
the complete root/controller/SQL state. This is scoped evidence, not a claim that
the failing paid lifecycle is qualified green.

The observer wraps the real collector and records its actual return value,
payload, source zone/sequence/LKI and callsite. Existing deterministic action
helpers execute independent clones twice; `state_index` distinguishes those
executions. Duplicate trace rows across clones are not duplicate gameplay events.

One passing LKI characterization currently asserts the exact target alias list
`leaves_battlefield`, `permanent_dies`, `creature_dies`. A correct future entry
publisher will require a separate expectation adaptation preserving death order,
LKI and controller assertions. Absence of entry in that characterization is
**not** a desired semantic green; the eight independent paid-Bolt assertions
remain strict desired reds and unchanged.

## Complete SBA Route Map

| Route in state_based_actions.py | Current boundary | Audit status |
| --- | --- | --- |
| `_move_lethal_creature:39` / checked resume at 62 | Old die replacement; manual GR assignment at 56 | Source-mapped; no single-creature GR episode here |
| `_resolve_lethal_creature_batch:100` | LBF batch at 119; manual GR assignment at 136; dies batches 141/142 | Actual paid Bolt trace and strict reds |
| `resume_legend_rule_replacement:67` | Manual GR assignment at 91; actual exile uses move_to_zone | Actual paid Kozilek reds and replacement-choice controls |
| Zero-loyalty loop 234-243 | Shared put_into_graveyard at 240 | Mapped only, not exercised here |
| Saga final chapter 264-294 | Delegates sacrifice handler at 293 | Handler ownership remains elsewhere |
| Attachment checks 361-399 | Shared put_into_graveyard at 386/395; separate attachment/LBF concerns | Mapped only, not certified |
| Nonbattlefield token cleanup 252-261 | Removes memberships, then CEASED | Not a new graveyard entry; do not invent one |

## Proposed Product Boundary, Not Implemented

Request SBA-only ownership for the three manual graveyard paths, including the
actual batch route. Reuse the existing pure entry plan and committed executor;
preserve owner destination, actual zone transitions, retained source identity,
printed static suppression and trusted shuffle receipt contract. Validate and
prepare the entire simultaneous batch before any LBF publication or departure;
do not re-query sources after a sibling departure changes active layers. Preserve
simultaneous LBF/death collection, original controller and death counter/LKI
timing. Publish only actual committed GR entries, never exile replacements.

No handlers/combat/keyword migration or keeper-choice API is included. Snapshot,
hidden-info and malformed-action checks must remain; existing action/projection
breadth and the frozen readonly classification query scopes must not be reduced.
Current findings do not certify all SBA routes, all graveyard rules or all source
reference persistence. Parent's six known coupled failures are a separate gate,
not this 26-case ledger.

## Evidence

Archive contains command/output/exit code, interpreter pins, immutable dependency
hashes, full inherited backend manifests, actual paid-action snapshots and
collector callsites. SQLite remains local during execution and is excluded from
the source archive. This tests-only patch adds this report and one new test module;
all original desired assertions and product preimages remain untouched.
