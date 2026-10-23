# Checked-Action Full-History Copy Candidate

Public base: `55066210a3c0cf2b65ed871477d9b750debee222`, tree
`c155ebc787ecd6ef118f5340ab60416304f71c58`. The candidate changes only the
checked-action root clone to existing `copy_match_state(state,
include_history=True)`, adds one canonical120 regression module, and this ledger.
It does not change the copier, legality/execution checks, defaults or other callers.

Current component result: corrected RED observed, then GREEN 110 passed / 330
ordinary phases, zero failures/errors/skips/subreports/denials, exit 0 in 77.8655
seconds. Parent independently closed GREEN at 22:14:18 UTC. Full candidate CI
and any whole-game performance measurement remain separate, not inferred here.

## Aggregate Diagnosis

A separately closed bounded diagnostic on frozen backend
`78bb2fdf4c7a0bf773c43cb1b341b574a4ac8e0e7cfa134ae7c1c52233573330`
recorded 2220 eligible checked-action calls, exactly matching apply-action STARTED
counts. All 88 periodic samples completed; sampled segment wall time was
13.2746 seconds: copy 11.5019 (86.6459%), validation 1.01397 (7.6384%), action
execution .74242 (5.5928%), residual about .0163. Monitoring overhead is included.
These are sampled checked-action segment times, not whole-game CPU attribution.
The closed game capsules did not contain resumable MatchState checkpoints;
no missing state or field costs were reconstructed from them.

A separate genuine initial-state benchmark used the admitted two-deck pair and
first-game seed: one factory construction, three whole generic deepcopies,
one independent copy per root field, then three existing-helper comparisons.
Generic seconds: .049793/.049456/.051121; helper: .033983/.033479/.033566.
Ordered warm N=3 mean ratio was 1.4884. Isolated cards cost .043211 seconds and
starting_decks .004653; the state contained 120 cards and 6211 non-atomic objects.
Per-field times are not additive because whole-copy traversal shares one memo.
Full serialized equality, original pickle purity, mutable isolation, aliases,
RNG/history and source/runtime checks passed. This is initial-state evidence,
not a measured whole-game speedup, deadline completion or AI-strength claim.

## Additive TDD Ledger

| Attempt | Actual scope and result | Disposition |
| --- | --- | --- |
| First RED, original new test | 110 calls: 104 passed, six failed; all 98 existing cases passed. Two route assertions failed as intended at line 78; four new accepted controls failed at line 57 on an invalid stdlib attribute-dictionary identity assumption. | Failed the intended RED contract. Evidence retained unchanged; no GREEN started from that attempt. No production/gameplay defect inferred from the four new assertion failures. |
| Corrected RED | Same 110 IDs and 330 ordinary phases: 108 calls passed and exactly two route calls failed with AssertionError at corrected line 81. 87.3495 seconds; outcome contract true, exception null, no denials, source/runtime checks true. Parent independently closed the role at 22:12:27 UTC. | Intended failing canary observed honestly. Pytest/actor/manager exit 1 remains exit 1; these are not 110 passes. |
| GREEN | Same 110 IDs and 330 ordinary phases: 110 calls passed, zero failures/errors/skips/subreports/denials; 77.8655 seconds, exit 0, all checks true. Parent independently closed at 22:14:18 UTC. | Scoped corrected copy-route and existing-contract component qualified. This is not full candidate CI, whole-game performance, or RC completion. |

The correction changes only the false card-dictionary identity assertion into
peer/shared member-alias and original-dictionary detachment checks. Standard
deepcopy can preserve a distinct copied attribute dictionary while its mutable
members alias the copied card's members. All original valid snapshot, root,
history, RNG, sibling, mutation and exception assertions remain. No additional
counter-dictionary identity requirement was added. No observed mulligan/counters
failure or specific counter-rebinding cause is claimed.

## Scope And Limits

The complete new module declares 12 cases using the existing full-RAW canonical120
fixture through production normalization/factory APIs, not handwritten printing
facts. Its reference uses the same checked-action code and genuine validators/
engine, binding only root cloning to stdlib deepcopy. Real keep/mulligan-round
values, shuffle RNG, history, cyclic metadata, aliases, siblings, rejected
requests and a labeled fault after a real accepted transition are retained.

The native declaration is five unchanged whole existing modules, 98 cases,
plus the complete new module: root-copy preallocation, root registered-set,
root metadata, mana-continuation phase guards and self-creature-change fb775.
The entire payment-trial-copy module remains held from the pure native profile
because its transitive import reaches main/TestClient. Full CI must cover it
without stubs, filters or permission widening. Base PR34 CI does not by itself
qualify the new candidate tree; candidate-wide qualification remains separate.

The existing copier preserves full history by default and shares a memo across
root/card copying. Exact CardInstance/container fast paths have boundaries for
custom hooks and global copy registrations. The tested supported contracts are
not universal Python clone equivalence. No new copy framework or arbitrary-Python
RC exit is introduced. No private capsules or raw traces are published here.
