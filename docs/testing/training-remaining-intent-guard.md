# Remaining Intent Guard

This incremental change is based on the frozen remaining-family audit source,
not a moving parent checkout. Production ownership is only
`TrainingEnvironment.lookup_intent`; helper, public schema, engine, producers,
dataset and existing tests are unchanged.

## Contract

The explicit public-model guard now also covers activate_loyalty (AbilityAction),
equip (EquipAction), crew (CrewAction) and cycle_card (CycleAction). Unknown keys,
including null and wrongly placed target/X/resource aliases, reject before
complete_action can discard them. Actual legality remains checked_action.

Known producer display metadata is separate from authoritative parameters.
Equip targets is accepted only as a nonempty list of dictionaries with exactly
id/name keys and nonempty string values. An object, null, empty/malformed list
or embedded chosen-parameter key rejects before normalization. This is display
shape validation, not target selection or candidate-legality inference; the
explicit target_card_id is still independently checked by the engine.
Crew suggestions cannot fill missing crew_card_ids. Resource selections are not
inferred. Proper public-model defaults remain unchanged.

Canonical variant cycling also exposes cycling_variant; this known display field
is allowed. Sojourner's Companion's actual whole producer view is qualified for
intent lookup, preserving the independently declared cycle action. This does not
qualify artifact-land search semantics. The existing six-family branches and
everything outside lookup_intent have exact static AST parity with the baseline
after removing only the authorized additional imports/models/branches.

## Qualification

Final 12-module serial gate on a fresh source copy/local SQLite:
413 ordinary PASS, 235 warnings, 346.09 seconds, exit 0. No skip, xfail,
deselection, normalizer monkeypatch or stateful acceptance trick was added to
the new tests. Existing neighbor tests retain their own guard instrumentation.

This includes unchanged primary 72 cases (48 rejection assertions and 24
independent valid controls), 34 new controls, and the existing mana/cast/activated
intent guards, public views, environment, dataset, complete-choice and checked
HTTP neighbors. Both-seat actual accepted execution, complete-root/DB atomic
rejection, aliases, hidden-identity byte equality and pending/restart/replay
checks are included. The frozen audit tests contain only rejection expectations
for unsupported requests, never contradictory unsupported acceptance witnesses.

The earlier 104-PASS focused gate (127 warnings, 50.82 seconds) precedes addition
of the variant-cycling display field/two controls and is historical, not the
final-source gate. Code was frozen during each run.

## Independent Open Engine Gap

The immutable separate canonical Shark Typhoon regression was rerun on the
final guard using a different source-local SQLite database: 2 ordinary FAIL,
2 warnings, 8.34 seconds, exit 1. Both seats preserve selected X=2 and pay four,
discard/draw and restart successfully, but still create no required 2/2 Shark.
No skip/xfail marker, producer rewrite or engine fix conceals this. The consumer
guard does not close this engine gap or claim full Shark Typhoon support.

The original tests/report and canonical-engine audit archives remain immutable.
No parent, main, live, engine, API, action_contract or producer writes. No browser,
neural-competence, expert-data or exhaustive remaining-action-family claim.
