# Pending mechanic sacrifice: retained graveyard plans

Exact base: published efbd52dfd0511d644940d59c9c46d07db5e10554 source archive,
plus original immutable direct-graveyard audit patch25bef513. This increment
changes ONLY the sacrifice slice of keyword_actions.finish_mechanic_choice.
No Ninjutsu/entry, handlers/combat, costs, events, API or planner changes.

All selections are validated before complete-batch graveyard plans are selected.
Unresolved library/exile competition fails closed before any LBF or mutation.
All genuine static replacement causes are prepared while every selected source
is still on the battlefield. Existing shared execution consumes retained plans
after LBF, preserves owner destinations/incarnations/LKI, and increments the zone
sequence. Existing sacrifice events, actual-graveyard-only death filtering and
paused stack finalization remain byte-for-byte unchanged. No arbitrary library
priority, invented cause or name-specific code.

Current qualification is deliberately NOT global graveyard completeness:
- Original94 unchanged:84PASS,10 ordinary handlerFAIL (different owner/scope).
- NEW33 strict keyword controls:33PASS.
- NEW8 canonical Kozilek from-anywhere dependency probes:8 ordinaryFAIL because
  the efbd shared executor has no enters_graveyard producer. Do not xfail/skip.
- Combined135:117PASS18FAIL,674warnings42.78s,exit1.
- Nine WHOLE neighbors:303PASS1119warnings86.65s,exit0.

NEW tests cover both seats, foreign ownership, batch causes before first LBF,
preflight of a late ambiguous card before any raw-core event, mixed library/death
batches, last-known counters, Humility selected in the same batch, paused trigger
order/restart without repeated sacrifice/refund, and actual memory/file HTTP
batch choices, cold GET continuation, privacy and root/controller/SQL rejection
purity. Snapshot subprocesses are real processes, not HTTP server restarts.
Trusted canonical annihilator pending positions do NOT qualify combat/attack.

The independently owned Lagrange enters_graveyard producer/executor ABI is a
future frozen dependency, NOT fabricated here. Do not substitute a moving root
or assume its eight trigger tests pass until composed and rerun. Jason owns the
retained-shuffle helper; Lagrange owns handlers/costs; neither was edited here.

Product preimage d4677c1bf4b6bd0fedda199c4aebc4ba62dd5db7f23dfd330855ed7446bc4218.
Product postimage f8133a438104783951b3b4d2d7513ea3feaab54b21c7e20a3e1eae8701ea865f.
AST/hash guards require every other keyword function and the entire prefix/suffix
outside the one authorized slice to match that preimage. Surgical hunks only;
no whole-file overlay. Original audit/fixtures are separate immutable dependencies.
