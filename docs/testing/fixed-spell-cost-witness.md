# Fixed Spell-Cost Joint Witness

Scoped cost-seam follow-up. Parent owns cast/parser changes; Sagan owns shared
planner/substitution forwarding. No engine, mana, AI, model, importer, main
checkout or live database edits by this workstream.

## Implementation

Only `check_cost_option_available` changes in existing `costs.py`. A NEW
`spell_cost_witness.fixed_cost_selections` helper lazily enumerates complete
fixed discard/sacrifice combinations using stdlib `combinations`. It reuses
`additional_cost_candidates` and validates each selection using the unchanged
`additional_cost_selection`, analogous to `_activation_selections` without
incorrectly substituting activation-specific sacrifice prohibitions.

Each physical mana probe reserves the announced source and the candidate fixed
selection. `any` short-circuits at the first joint witness, but never arbitrarily
cuts off later combinations. No first-candidate-only logic, tactical scores,
invented Oracle instructions, eager Cartesian pool, or new dependency.
Worst-case exact search is combinatorial; no universal runtime bound is claimed.

Exhaustive discard-all/sacrifice-all groups yield no pre-mana reservations;
existing payment recomputes them after mana. Reserved victims may still tap for
mana before sacrifice. Existing life, target, X, modifiers, type/prohibition and
pre-mana escape checks remain unchanged.

An independent source-boundary check proves **every byte outside this one
function unchanged**, including all parsers and globals. Baseline costs SHA256:
`c477f674881bd92e76114e1e086c89af31670b34651ae65d0195336c7dd39302`.
Patched costs SHA256:
`86834afb19d4e5254a180043e0c3cd670818755036dc39ce3cac67107e0a4770`.
The function signature is unchanged. The patch excludes the parent's frozen
subtype-parser dependency and excludes Sagan's separately owned changes.

## Canonical Reproductions

Both seats use unchanged retained public Oracle records:

- Tower/Village Rites: one creature cannot fund Tower mana and the fixed
  sacrifice. A distinct creature permits both payments.
- Prospector/Goblin Grenade: the sole Prospector cannot sacrifice itself for R
  and pay the Goblin sacrifice. A separate Goblin permits joint payment.
- Familiar/Tormenting Voice: R in pool and one other hand card cannot fund the
  generic mana and additional discard. A separate hand card permits both.
- Familiar/Cathartic Reunion: both mandatory discards must be reserved together;
  one additional hand card makes the generic-mana payment possible.
- Blood Pet/Ornithopter/Village Rites: reserving the first candidate, Blood Pet,
  cannot fund B. Reserving the later Ornithopter leaves Blood Pet for B and pays
  both costs. Availability must find that later witness. Explicitly selecting
  Blood Pet rejects; explicitly selecting Ornithopter succeeds, atomically.
- Crop Rotation can tap its selected Forest for G before sacrificing it.
- Kaervek's Spite's exhaustive groups remain post-mana; mana discards are not
  frozen into the additional discard-all payment.

Tests compare complete root snapshots before/after every probe, repeat probes,
restore serialized roots and compare full successful checked-action results.
They do not execute fake draws, rewrite card facts, or claim trained competence.
Absent noncreature power/toughness remain null in the existing test adapter; raw
source records are not rewritten. All four existing fixture files are hash-pinned.

## Qualification

Source: parent's announced-source archive SHA256
`678818066e7ad0ef67ddc9c063790aa10dad4e9cd7d1c3f83cd8e5becbdd75a2`,
then Sagan's approved engine-only shared delta SHA256
`65c266a72110f30631e177d42277a62ced7ebe39d54409591a37500c15dde411`,
then this surgical cost-seam patch. No performance-patch dependency is assumed.

- NEW canonical suite: **8 failed / 15 passed before; 23 passed after**.
- Core-only serial neighbor gate: **464 passed, 18 deselected, 2 known escape
  xfails**, zero SQLite/socket connection attempts; 30.46 seconds.
- Fresh archived-input restore and clean patch application reproduces **464
  passed, 18 deselected, 2 xfailed**, zero forbidden attempts; 29.81 seconds.
- Separate opt-in local ASGI: **4 passed**, all 422 responses with unchanged
  root/controller/full in-memory database dump; exactly four `:memory:`
  connections and zero network attempts.
- Actual AI materialization: eight canonical positive probes across both seats
  and Tower/Prospector/Familiar/Blood Pet all admit, with unchanged roots.
- Full availability investigation after the actual shared plus cost deltas:
  **64 passed, 6 failed**. The six are the separately documented identity-less
  AI heuristic probes, not this cost seam. No AI fixes or marker removal here.

The 18 deliberate core exclusions are 14 DB-backed HTTP neighbors and four
now-fixed historical delve xfail duplicates; unmarked Sagan acceptance covers
the latter. Separate memory HTTP covers the source boundary, not every excluded
HTTP contract. The first broad gate accidentally included six variable-cost
HTTP fixtures: the audit guard blocked their SQLite opens (six setup errors,
464 passes). No database file was created. That failed gate remains evidence,
not qualification. Initial fixture-adapter failures also remain archived.
Independent counts overlap; do not sum them into a larger certified suite.

## Caller Contract And Limits

The frozen availability report and 61-callsite ledger describe the actual
cost-options -> movegen -> admission/AI routes. The shared source guard is not
duplicated in caller-specific hooks; this seam adds fixed-cost joint existence.

Existence is not a guarantee that every displayed candidate, implicit default,
or cheapest AI victim is payable. The Blood Pet reproduction proves some
selections fail despite an alternate witness. Parent may optionally add a
keyword-only choice-aware availability seam for an already announced selection,
validating exact IDs with the same candidates, or expose a selected payable
witness for materializers to reuse. Do not silently replace explicit selections.
Existing callers need no signature change for the existential contract.

The eight actual materializer probes selected payable victims; no concrete
unpayable-cheapest-victim AI bug was observed, so no new AI materializer hook is
proposed on that basis. The separate six identity-less heuristic false positives
remain an AI-owner follow-up, with no AI source changes authorized here.

Mana-created escape fuel still fails the existing pre-mana count gate: two known
xfails remain explicit. No granted Underworld Breach escape/delve, full
announcement-zone staging, all-layout or all-mechanic support is claimed.

## Application

Require the exact reviewed baseline costs body, absent NEW helper/test/doc
paths, parent's cast-source fix and reviewed Sagan shared delta for composed
qualification. NEW tests reuse the unchanged historical overlap fixture/test
dependency plus existing public fixtures. Apply the surgical four-file patch,
not the isolated worktree's staged parent-parser dependency. Re-run qualified
neighbors after further parent changes; no live import or deployment occurs.
