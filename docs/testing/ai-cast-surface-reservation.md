# Selected cast surface and interaction reservation repair

## Frozen Baseline And Scope

2026-10-06, isolated frozen C13zTw qualified-audit-source.tar.gz SHA256
93bcbf05fa3f24d985ec32782b9f6db0e3db600ea27ea60a5145445b4b573b61.
Prior archive: ai-knowledge-consumer-audit/mtg-ai-knowledge-audit-source-C13zTw.
It includes original tests/report dependency d881c00be5a197bd55135f54c14b0f3b2379cf7ec174423ff6cea03c0b48c10d
and the held combat-read-scope experiment. This is NOT a current-main/c16
qualification, engine fix, playing-strength or speed claim.

Only production file backend/ai/agent.py, exactly two existing functions:
- `_matchup_move_adjustment` reads `_card_for_move` instead of stored front.
  No scoring weight, archetype, card name or other branch changes.
- `_instant_value_reservation` enumerates own-hand cast surfaces using existing
  `_card_for_move`, current timing, supported-spell contract and authoritative
  available_cast_options_and_hints / collect_cost_options /
  check_cost_option_available. Layout face enumeration matches existing casting
  families, not transformed back faces. Counters retain prospective reservation
  without inventing a stack target. Existing removal tags remain supported;
  supported return_permanent_to_hand recognizes an actual opposing battlefield
  target. No arbitrary metadata, hidden library/hand forecast or new taxonomy.

After materializing the original value spell in a planning copy, reservation
checks whether any recognized own response remains in hand with an affordable
current engine cost option. It never substitutes the front cost for a selected
Adventure cost. Actual cast/payment engine remains sole authority. Existing
own-turn/endstep/cleanup/stack/emergency/deployment gates and -6 penalty remain.
Effect inference uses report_unsupported=False and only runs after target/cost
availability, so discovery cannot append unsupported diagnostics to the root.
No shared tactical/engine/event/cost/API/UI/source edits. AST inverse replacement
proves the complete module outside these two functions unchanged.

## Exact Qualification

Original23 test source, original fixture and original report byte-identical:
- Before:13PASS/10ordinaryRED (sealed original audit).
- After:19PASS/4ordinaryRED, 1warning,3.53s.
- Final original23+NEW30 whole modules:49PASS/4ordinaryRED,1warning,6.70s.
  Exit1 deliberately retained; no removal/deselection/xfail of REDs.
- Eleven whole neighbor modules:496PASS,9warnings,103.02s,exit0.
- Four unchanged bounded actual MASTER witnesses, difficulty master,
  archetype Tempo or Control, opponent_archetype Ramp, seed701, both seats:
  all exit0, unchanged final action/reasoning. Tempo casts Petty Theft face1
  at opposing Topiary Stomper; Control passes holding Counterspell.
  Actual agent receives opaque libraries and opposing hand, omitted opponent
  deck metadata. Actual checked action and root/snapshot restore equality pass.
  These are synthetic controlled positions, not natural games or expert plays.

NEW30 controls cover both seats: scarce versus remaining Island/pool mana;
uncastable Adventure; endstep/cleanup/own-turn/emergency; no opposing target and
friendly-only targets; interaction itself unpenalized; selected Stomp surface
and real checked materialization; hidden-order/root/restoration equality; real
Phyrexian payment authority with Angel of Jubilation prohibition. Existing
neighbors additionally retain canonical topdeck deployment/counter reservation,
selection, cost/mode and hidden-information behavior. Exact module list/logs
and JUnit/exit ledgers accompany evidence; no gate-scope shrinking.

## Preserved Failures And Limits

Four original Growth Spiral/Arboreal Grazer ramp classification REDs remain
unchanged. Their canonical extra-land execution omissions are outside scope;
this patch does not assign ramp value to an unimplemented clause.

Initial NEW26 gate had four no-target purity failures from infer_effect logging;
logs preserved, repaired without weakening assertions. A subsequent NEW4
Dismember probe hypothesized reservation -6 when payable. Two failures showed
its old tactical tags are empty and inference exposes temporary_pt_buff, not
the newly authorized bounce effect. Original probe/test/logs are preserved in
initial-phyrexian-probe/. Final controls explicitly assert existing empty tags,
authoritative payment available only when not prohibited, and unchanged zero
reservation. This is a disclosed test hypothesis correction, not Dismember
classification certification or a debuff-scoring repair. No production widening
beyond the two authorized functions; any such next scope needs coordination.

No full latest/main suite, new game matrix, winrate, latency, training or neural
claim. Optional persisted CardKnowledge quality remains documented future
nonconsumption. No Oracle edits, new canonical declarations or fake cards.

## Reproduction And Dependencies

Source tar above already contains the prior3-path audit. Apply ONLY this
increment; do not reapply old combat, LKI or audit dependencies. Product-only
single-file patch is also supplied for surgical parent composition; compare
exact preimage before merging, never whole-overwrite a newer agent.py.

Fresh own local SQLite, external interpreter:
/home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python.
From backend, set PYTHONPATH=$PWD and PYTHONDONTWRITEBYTECODE=1:

```sh
"$PY" -m pytest -q tests/test_ai_knowledge_consumer_audit.py \
  tests/test_ai_cast_surface_reservation.py
"$PY" -m pytest -q tests/test_deck_analysis.py tests/test_tactical_tags.py \
  tests/test_ai_oracle_semantics.py tests/test_card_hydration.py \
  tests/test_knowledge_models.py tests/test_mechanic_metadata.py \
  tests/test_ai_topdeck_deployment.py tests/test_ai_opaque_top_choose_horizon.py \
  tests/test_ai_selection_activation_policy.py tests/test_cast_choice_modes.py \
  tests/test_contextual_cost_prohibitions.py
```

Private evidence includes preimage/source manifests, AST proof, historical REDs,
current receipts/full-master script and exact config. Each optional master call
used external35s+5s grace; no retries/search changes. SQLite is local only, never
executed from NFS. Parent/main/live untouched; completed owned scratch removed
only after mounted writable private NFS copy/hash verification and process check.

Graph maintenance: own-root AST update reached1602/1602 files; 30s bound
ended exit124 before full graph completion. Partial log retained; no parent
graph writes or full-freshness claim.
