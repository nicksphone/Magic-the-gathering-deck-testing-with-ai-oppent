# Ordered Noncombat Damage Conversion

This bounded increment joins the existing supported source-controlled noncombat
damage conversion with the permanent damage replacement query/application path.
It does not clear coverage warnings or certify every replacement interaction.

## Contract

`replacement_options` retains its existing option fields. Optional `amount=None`
means a read-only potential-event query; explicit nonpositive amount excludes
permanent damage choices. Execution uses only positive actual remaining damage.
Source identity, retained LKI and actual resolution controller are forwarded by
the existing pre-pop Stack query. No card-name dispatch or inferred amount.

Selected sources apply once. Human chains requery the modified remaining event,
exclude prior sources, and use existing `choose_replacement` continuations.
Conversion queues existing effect counter placement and ends the damage event:
zero actual damage, lifelink or damage-dealt event. Nested counter choices retain
the genuine resolving frame; they are never overwritten by a damage-chain pause.

Matching protection uses the existing option shape with virtual source ID
`protection:<target_id>`, analogous to shield-counter options. It describes the
actual target's effective protection, not a fabricated card added to game state.
The affected controller selects protection versus conversion. Prevention locks
omit protection but do not disable conversion. Legacy combat application defaults
remain combat-only: combat cannot acquire noncombat conversion.

Copied-spell source characteristics come from existing saved copy metadata/LKI,
with the actual resolver controller retained through continuation. Ordinary core
damage follows actual source/LKI controller, not an unrelated handler actor.

## Evidence

Original49 + ordered20 are unchanged and ordinary PASS. Original protection38
remain unchanged:24 PASS and14 separate upstream failures. Twelve cannot compile
Healing Salve's actual any-target prevention mode; two compile Pyroclasm to the
wrong recipient. Neither compiler is edited here.

New26 supplement includes four genuine paid Sickening Dreams/White Knight episodes
with both seats and both selected orders, paid discard/mana, actual resolving
frame, cold JSON restore, private observations and wrong-actor/unoffered-choice
full-root purity. These use an already supported nontargeted black damage provider;
they do not stand in for Pyroclasm support. Four further paid Bolt episodes preserve
nested Doubling Season/Winding Constrictor counter choices and their actual frame.
Four virtual-protection core calculations are explicitly component tests, not
illegal red targeted spells or invented gameplay episodes.

Final18 whole modules:455 PASS/16 ordinary FAIL,61.50s,exit1; no exclusions,
skips,xfails or errors. The two other failures are unchanged phase-cursor fixtures
in `test_resolution_conditions`; no scheduler/test adaptation is included.
All SQLite aliases and socket operations are audit-hook denied. No HTTP/SQL gate,
browser readiness, all-card coverage, matchup estimate or universal CR claim.

## Scope

Only `replacement.py` candidate/query/application functions, three damage-family
functions in `handlers.py`, and the existing replacement-options query arguments
in `stack_engine.resolve_top_of_stack` change. All Ray guards/transport outside
that tiny query hunk are byte-identical. Corrected Ray control functions, producer,
scheduler, costs, engine, combat, schema, AI and coverage remain unchanged.
