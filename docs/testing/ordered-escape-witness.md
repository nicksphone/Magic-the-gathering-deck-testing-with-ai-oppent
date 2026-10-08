# Ordered Native Escape: Narrow Pure Qualification

## Exact Root And Scope

Base: immutable Git `352f3b86579f216f7ce52f34070dffa9811c1063`.
Owned root: `/tmp/mtg-escape-witness-352f-UZKWvV/source`.
Python: `/home/nick/.hermes/cache/scratch/mtg-qualified-python-recovery-EnC3vJ/bin/python`, Python 3.12.3; pip 26.2.1. Pip-only maintenance does not explain any product failure.

Product patch modifies only check_cost_option_available, the native-escape block of RulesEngine.take_action, can_pay_with_pool_and_lands, _plan_payment, _spell_payment_plan, auto_pay_cost, paid_candidates, and prepare_entry_counters's escaped-count branch. New shared bounded postcondition and escape_payment_condition are appended to spell_cost_witness.py. Original fixed_cost_selections is byte-identical. begin_spell_entry and all other function bytes are unchanged; apply hunks, never overwrite entire files.

Separate marker-only patch removes the two-line strict-xfail decorator on test_native_escape_can_use_card_created_by_mana_payment after both original bodies actually strict-XPASSed. Both parameters, bodies, and all assertions remain byte-identical. No other markers are removed.

All 2,496 base regular files compared: six product files and that one decorator-only test file changed; all other original files byte-identical. exact-source-verification.json records before/after hashes and exact outside-function equality. Four new test modules are packaged separately; the audit runner is not a product integration file.

## Executed Ledgers

- Original new28: 14 pass / 14 fail, 2.27s, exit1. Two failures were new-fixture missing nullable fields; original test version and raw failure preserved.
- Corrected new28 PRE: 16 pass / 12 fail, 1.85s, exit1. All twelve desired casts actually rejected before mana payment could create the fourth graveyard card.
- Witness POST unchanged28: 16 pass / 12 fail, 3.00s, exit1. All twelve casts now paid five mana and exiled four other cards through actual mana activation; complete-body assertions exposed missing entry counters.
- Independent existing four-graveyard PRE control: 2 pass / 2 fail, 1.36s, exit1. Same witness POST control: 2 pass / 2 fail, 1.43s, exit1. Actual stack and entry escaped flags true, empty counter map, one Goat. Thus the count defect already existed in an admitted canonical cast; it was not caused by the witness.
- Count repair unchanged28 + independent4: 32 pass, 3.23s, exit0.
- New bounded8 initial: 6 pass / 2 fail, 0.98s, exit1, solely wrong new-test keyword `source`. Corrected to existing source_card_id; both test versions preserved. Whole8: 8 pass, 1.13s, exit0.
- Non-card count-token boundaries: 21 pass, 0.41s, exit0. Tests use the actual branch regex and existing count parser. Not invented-card gameplay or a complete grammar claim.
- Original whole neighbor launch: four collection errors, 3.11s, exit2; missing declared owned audit-helper import paths. Raw retained. Guard/tests unchanged; owned helper PYTHONPATH and ADMISSION_PHASE supplied on rerun.
- Whole seven-module neighbor230 before marker edit: 228 pass / 2 strict-XPASS, 36.37s, exit1. Only the two original escape bodies strict-XPASS; no semantic failure.
- Final SAME seven whole modules230 plus four new whole modules61: **291 pass, 24.38s, exit0**, no skips/xfails/filters/marker selection. Exact ordered first230 node IDs match the preserved strict-XPASS run. XML suite time24.355 differs slightly from pytest summary time24.38.

Final original modules: backend/tests/test_fixed_spell_cost_witness.py; backend/tests/test_spell_cost_overlap_investigation.py; audit/gate2-march-cost/test_march_paid_v2.py; test_march_pitch_responses.py; test_march_pitch_paid.py; test_march_joint_paid.py; test_exhaustive_reservation_delta.py (last five all under that same audit directory).
New modules: audit/gate2-escape-witness/test_ordered_escape_paid.py; test_preexisting_escape_body.py; test_bounded_escape_witness.py; test_escape_count_tokens.py.

## Declared Evidence And Limits

Both seats, automatic/explicit exact escape selections, Tower-funded/already-funded/free-alternative mana paths: twelve paid complete-body positives. Real source sacrifice, graveyard publication, escape exiles, mana spent, escaped stack flag, cold JSON round-trip, real priority resolution, two counters and Goat verified without preparation actions. Fourteen invalid checked actions reject atomically; two real Leyline replacement controls send sacrificed fuel to exile, not graveyard. No forced winner, opponent-private decision data, AI retuning or simulation runner.

Bounded physical branches share one 4,096-node budget; exhaustion rejects planning, not proof that the action is globally impossible or the card unsupported. Existing physical reservations are excluded from escape fuel; selected future IDs are not manufactured by the predicate. Ordinary planner paths retain default None; whole existing neighbors and March goldens exercise them. This qualification covers the declared producer/payment archetypes, not every possible native escape producer, replacement interaction, mixed additional cost or arbitrary board size.

The separate escaped-count repair reuses _parse_count_token with explicit existing a/an/one..ten/digits vocabulary under the existing __escaped gate. Unknown tokens never reach the parser's fallback. It does not tighten the old unanchored complete-body grammar, certify unknown suffixes, or admit additional cards. No coverage.py changes, cost-parser changes, named branches or warning clearing.

## Native Pure Policy And Provenance

Unchanged runner SHA256: 8a0bbb21371c82473964ca91313d71ca3e887ef60a6c78814b4c8a63a45fca5c.
Before collection, native sqlite connect, socket creation, subprocess.Popen, os.system and fork canaries denied. Native audit stays installed throughout collection/execution. Final receipt has exactly those five denials, zero unexpected denials, 129 owned import hashes equal current bytes, default backend/mtg_lab.db absent. No actual SQL/socket/children permitted or used. This is observed Python-native audit enforcement, not an OS sandbox or arbitrary escaped-child certificate.

Final launcher: unchanged audit/gate2-owned-proof/pure_gate.py, timeout180 plus kill grace5; fresh final-scratch; PYTHONDONTWRITEBYTECODE=1, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, -q -p no:cacheprovider, no filters. Owned helper paths audit/gate2-domain-compiler, audit/gate2-march-proposal, audit/gate2-march-cost; phase escape-final, control-final. Native receipts and raw logs/XML/exit codes remain in evidence.

Seed155 metadata rows byte-unchanged, SHA9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037. Canonical overlap fixture SHAfd6c5a98c5d88557589f6fa5f7b87dcb33a88be5bff76aa6a316595d1aa1f9ec. Canonical death-cycle fixture SHA82a096075b1577480e7c966f1efdb364edda3966c6a5ad9fdc073dcab836f7b5. coverage.py unchanged SHA2b1217d0c5bf41e3e72f64c0e1b7a792d54f52fc92120247ebcbac74a6ee5ae3. No admission/corpus gaps cleared by this packet. No semantic155, all-rules, completed balanced-match metrics or expert-AI certification.

Parent union, full SQL cohorts and unrelated rule blockers require separately owned qualification; this isolated packet cannot certify those moving compositions. All earlier red ledgers remain archived.

## Handoff Verification

AST-only graphify update completed exit0: 16,407 nodes, 79,259 edges, 590 communities, no API extraction. Postgraph source manifest records 4,702 regular files including declared graph/cache outputs. All 129 final imported product hashes remain unchanged after graph refresh; no database artifacts. Both surgical patches applied successfully to a fresh immutable352f archive and every patched file compared byte-identical to the tested root. No whole-source overwrite is authorized.

Product patch SHAfe8208b8105a75fef0626b7b7184ea459ee3fad8953fddee1fb5ddc09bc4efeb.
Separate marker patch SHAb2dc7b595df7d12bfa414c888f4a8e25202357fb531478908133c34f10452e73.
