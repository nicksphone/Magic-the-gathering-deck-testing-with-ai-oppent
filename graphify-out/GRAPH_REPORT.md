# Graph Report - mtg-deck-testing-lab  (2026-07-19)

## Corpus Check
- 173 files · ~436,732 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2364 nodes · 6143 edges · 125 communities (120 shown, 5 thin omitted)
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 2757 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `99808921`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 111|Community 111]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 240 edges
2. `RulesEngine` - 157 edges
3. `CardInstance` - 156 edges
4. `from_decks()` - 143 edges
5. `from_decks()` - 136 edges
6. `AIAgent` - 87 edges
7. `RulesEngine` - 79 edges
8. `resolve_effect()` - 78 edges
9. `Repository` - 75 edges
10. `emit_event()` - 63 edges

## Surprising Connections (you probably didn't know these)
- `test_ai_combat_uses_granted_keywords_from_static_effects()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_control_ai_prefers_removal_against_evasive_threat()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_best_of_replay_aggregates_games_deterministically()` --calls--> `run_match()`  [INFERRED]
  backend/tests/test_seed_and_replay.py → backend/scripts/regression_matrix_replay.py
- `test_create_token_assigns_image_uri()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_token_images.py → backend/effects/registry.py
- `test_replacement_gain_life_to_draw_cards()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_new_rules_batch.py → backend/effects/registry.py

## Communities (125 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (86): _active_card_surface(), _board_value(), _creature_value(), evaluate_inevitability(), _noncreature_value(), _planeswalker_count(), _types_from_type_line(), _all_battlefield_ids() (+78 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (82): AIAgent, test_ai_materializes_graveyard_spell_target_for_recursion(), test_ai_materializes_required_library_search_choice(), test_master_attack_search_avoids_throwing_small_creature_into_large_blocker(), test_master_block_search_prevents_lethal_damage_when_trade_is_available(), test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_mulligans_hand_without_early_pressure(), test_aggro_ai_prefers_creature_development_over_burn_early() (+74 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (58): decision_reason_code(), has_actionable_move(), has_meaningful_move(), is_actionable_move(), is_meaningful_move(), Shared classification for AI decision-trace diagnostics., Exclude pass and restricted UI placeholders from legal-action diagnostics., Identify actions that change resources, board state, or combat decisions. (+50 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (37): api, BatchSimulationJobStart, BatchSimulationJobStatus, CardCompletenessReport, configuredApi, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (56): _auto_bottom_cards(), topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost() (+48 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (57): resolve_effect(), infer_effect_from_oracle(), _split_clauses(), infer_effect_from_oracle(), CardInstance, test_x_mode_inference_respects_selected_mode_and_x(), test_oracle_add_counters_parsing(), test_oracle_collected_company_style_parsing() (+49 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (30): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIDecision, test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board() (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (44): analytics_history(), apply_sideboard(), autoplay_tick(), card_completeness(), _card_looks_like_land(), _controller_snapshot(), _default_player_for_state(), _force_ai_land_action() (+36 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (49): attach_if_legal(), attached_to(), is_aura(), is_equipment(), emit_event(), _order_apnap(), destroy_permanent(), sacrifice() (+41 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (47): Enum, from_decks(), _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState (+39 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (3): _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 11 - "Community 11"
Cohesion: 0.15
Nodes (42): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, ingest_tournament_json(), list_cards() (+34 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (36): Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., RulesEngine, test_discard_additional_cost_is_paid(), test_engine_rejects_play_land_when_player_is_not_active(), test_generates_basic_legal_moves() (+28 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (21): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, ParsedDeck, ActiveMatchRecord (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (48): 0. Fix runtime and deployment blockers, 1. Close Rules-Engine Gaps, 1. Expand Rules-Engine Coverage, 1. Make match and simulator state durable, 2. Deepen AI Decision Quality, 2. Finish BO3 and Sideboard UX, 2. Improve AI Decision Quality, 2. Replace regex-only Oracle growth with structured abilities (+40 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (47): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (FIXED), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (FIXED), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED) (+39 more)

### Community 16 - "Community 16"
Cohesion: 0.1
Nodes (43): destroy_permanent(), discard_cards(), sacrifice(), StackItem, emit_event(), add_to_stack(), _put_trigger_creature(), test_apnap_trigger_order_on_shared_event() (+35 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (17): fuzzy_card_lookup(), normalize_card_lookup_name(), DeckParser, ParsedDeck, DeckParser, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions() (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (24): check_cost_option_available(), guess_archetype(), RulesEngine, compute_max_land_plays_this_turn(), start_match(), legal_moves(), extract_loyalty_abilities(), can_cast_in_current_timing() (+16 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (38): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview, Card Data and Images (+30 more)

### Community 20 - "Community 20"
Cohesion: 0.06
Nodes (11): add_counters(), copy_ability(), copy_spell(), _copy_stack_object(), _creature_is_lethally_damaged(), deal_damage_multi(), destroy_all_artifacts(), destroy_all_artifacts_and_enchantments() (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (36): _setup_creature(), _setup_permanent(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_attack_declared_can_create_token_payoff(), test_attack_declared_triggers_attack_payoff(), test_block_declaration_hands_priority_back_to_active_player(), test_block_declared_triggers_block_payoff() (+28 more)

### Community 22 - "Community 22"
Cohesion: 0.1
Nodes (28): AbilitySpec, build_ability_spec(), EffectSpec, Stable application-level representation of a card action.      The parser remain, build_cast_hints(), validate_cast_choice(), test_ability_model_exposes_effect_targets_modes_and_choices(), test_ability_model_marks_unparsed_action_text_as_fallback() (+20 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (32): build_cast_hints(), enrich_divide_total(), create_shark_token(), create_token(), CardInstance, _extract_modes(), inspect_target_hints(), enrich_divide_total() (+24 more)

### Community 24 - "Community 24"
Cohesion: 0.09
Nodes (19): ai_diagnostics(), _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck() (+11 more)

### Community 25 - "Community 25"
Cohesion: 0.13
Nodes (31): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), _deal_unblocked_damage(), declare_attackers(), _defender_label() (+23 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (29): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+21 more)

### Community 27 - "Community 27"
Cohesion: 0.12
Nodes (11): sync_card(), ScryfallSyncService, _BlankCachedCard, _CachedCard, _CompleteCachedCard, _DummyRepo, test_completeness_report_identifies_cached_and_missing_card_data(), test_extract_remote_image_uri_falls_back_to_face_images() (+3 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (15): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., evaluate_board(), evaluate_board() (+7 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (29): Backend tests, code:bash (cd frontend), Frontend, Frontend, Frontend, Frontend, Frontend, Frontend (+21 more)

### Community 30 - "Community 30"
Cohesion: 0.18
Nodes (22): lifespan(), MatchController, _restore_active_matches(), init_db(), autoplay_tick(), MatchController, _ensure_card_cache_columns(), _ensure_card_faces_column() (+14 more)

### Community 31 - "Community 31"
Cohesion: 0.07
Nodes (28): 3) Frontend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+20 more)

### Community 32 - "Community 32"
Cohesion: 0.16
Nodes (24): deal_damage(), _state(), test_combat_only_override_applies_to_combat_damage(), test_named_source_override_does_not_unlock_other_sources(), test_target_permanent_can_have_damage_prevention_override(), test_target_player_can_have_damage_prevention_override(), _state(), test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented() (+16 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (13): ai_diagnostics(), _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck() (+5 more)

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (22): _collect_triggers(), _first_number(), _maybe_payload(), _trigger_from_oracle(), _collect_triggers(), _first_number(), _has_artifact_or_enchantment_type(), _matches_attack_trigger() (+14 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (15): get_with_backoff(), ensure_placeholder_image(), _family(), _slug(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri() (+7 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (6): _card_looks_like_land(), _auto_bottom_cards(), mana_value(), parse_mana_cost(), test_control_ai_mulligan_counts_land_with_missing_types_from_oracle(), test_control_ai_mulligans_land_light_hand()

### Community 37 - "Community 37"
Cohesion: 0.2
Nodes (14): AnalyticsService, FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), test_compare_replay_logs_labels_cast_resolution_error(), test_compare_replay_logs_labels_face_choice_mismatch(), test_compare_replay_logs_labels_mode_choice_mismatch() (+6 more)

### Community 38 - "Community 38"
Cohesion: 0.17
Nodes (20): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), activated_cost_available() (+12 more)

### Community 39 - "Community 39"
Cohesion: 0.12
Nodes (19): crew_vehicle(), _can_cast_spell(), _has_any_target_options(), _is_land_card(), cycling_cost(), cycling_is_variable(), cycling_variant(), Return a cycling cost, optionally including a validated X/Y symbol. (+11 more)

### Community 40 - "Community 40"
Cohesion: 0.18
Nodes (14): _hydrate_deck_cards(), _get_attr_or_key(), select_display_image_uri(), fallback_card_payload(), _fallback_name_aliases(), _normalize_card_name(), fallback_card_payload(), hydrate_deck() (+6 more)

### Community 41 - "Community 41"
Cohesion: 0.16
Nodes (19): _extract_keywords_from_text(), _first_creature(), _infer_clause_effect(), _infer_topdeck_creature_put_effect(), _parse_count_token(), choose_mana_color_for_player(), _choose_any_permanent_target(), _choose_noncreature_permanent_target() (+11 more)

### Community 42 - "Community 42"
Cohesion: 0.15
Nodes (17): _classify_divergence_category(), classify_first_divergence(), classify_log_line(), classify_timeout_state(), normalize_log_line(), _parse_ai_trace_payload(), _trace_context_summary(), get_match_replay() (+9 more)

### Community 43 - "Community 43"
Cohesion: 0.16
Nodes (18): destroy_all_creatures(), _move_creature_to_graveyard(), gain_life(), replace_gain_life(), apply_damage_replacements(), apply_permanent_damage_replacements(), _battlefield_oracle_texts(), _battlefield_position_map() (+10 more)

### Community 44 - "Community 44"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 45 - "Community 45"
Cohesion: 0.18
Nodes (16): validate_cast_choice(), PlayerState, validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets(), test_choose_two_validator() (+8 more)

### Community 46 - "Community 46"
Cohesion: 0.19
Nodes (14): _board_role_hint(), build_priors_from_examples(), build_priors_from_logs(), _build_priors_payload(), _count_creatures(), load_log_priors(), _record_card_timing(), save_log_priors() (+6 more)

### Community 47 - "Community 47"
Cohesion: 0.12
Nodes (8): Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Search small-board attack subsets through the defender's best legal blocks., Search small-board attack subsets through the defender's best legal blocks.

### Community 48 - "Community 48"
Cohesion: 0.24
Nodes (15): analyze_deck(), _card_text_matches(), _cmc(), _derive_face_based_mana_cost(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _summarize_card_metadata() (+7 more)

### Community 49 - "Community 49"
Cohesion: 0.22
Nodes (13): deserialize_match_snapshot(), Serialize all mutable rules state needed to resume a match., serialize_match(), serialize_match_snapshot(), _tupleize(), _state(), test_day_night_change_triggers_use_the_stack(), test_day_night_starts_at_upkeep_after_no_spells() (+5 more)

### Community 50 - "Community 50"
Cohesion: 0.2
Nodes (15): _setup_creature(), test_cant_attack_alone_enforced(), test_cant_attack_creature_is_filtered_from_attackers(), test_cast_only_during_your_turn_restriction_and_move_hint(), test_must_attack_if_able_auto_added_when_omitted(), test_must_block_if_able_auto_assignment(), test_static_you_cant_cast_spells_during_combat_enforced(), _setup_creature() (+7 more)

### Community 51 - "Community 51"
Cohesion: 0.12
Nodes (16): cycle_search(), _place_searched_card(), put_green_creature_from_hand(), Resolve an alternate-cycling search and shuffle the remaining library., return_creature_from_graveyard_to_battlefield(), return_permanent_from_graveyard_to_battlefield(), search_library(), topdeck_put_creatures_battlefield() (+8 more)

### Community 52 - "Community 52"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 53 - "Community 53"
Cohesion: 0.13
Nodes (14): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+6 more)

### Community 54 - "Community 54"
Cohesion: 0.25
Nodes (12): _board_role_hint(), _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line() (+4 more)

### Community 55 - "Community 55"
Cohesion: 0.36
Nodes (14): declare_blockers(), declare_blockers(), _setup_creature(), test_blocker_with_additional_block_capacity_can_block_two_attackers(), test_cannot_be_blocked_except_by_three_or_more_creatures(), test_cant_be_blocked_except_by_two_or_more_oracle_text(), test_default_blocker_cannot_block_two_attackers(), test_flying_attacker_cannot_be_blocked_by_ground_creature() (+6 more)

### Community 56 - "Community 56"
Cohesion: 0.16
Nodes (13): card_cant_attack(), card_cant_block(), card_must_attack_if_able(), card_must_block_if_able(), declare_attackers(), _defender_label(), _valid_defenders(), can_cast_in_current_timing() (+5 more)

### Community 57 - "Community 57"
Cohesion: 0.23
Nodes (12): classify(), main(), classify(), _looks_like_main_phase_pass_loop(), _looks_like_repeated_x_spell_error(), main(), _parse_trace(), test_anomaly_cluster_labels_x_value_and_stack_signals() (+4 more)

### Community 58 - "Community 58"
Cohesion: 0.22
Nodes (8): prevent_damage(), prevent_damage(), add_card_prevention_shield(), add_player_prevention_shield(), test_expansion_top_entries_have_deck_text(), test_deal_damage_to_creature_marks_damage_not_toughness(), test_prevent_damage_shield_reduces_creature_damage(), test_prevent_damage_shield_reduces_player_damage()

### Community 59 - "Community 59"
Cohesion: 0.27
Nodes (7): first_log_divergence(), _balance_alerts(), _batch_seed(), compare_replay_logs(), _extract_turn_summaries(), _first_divergence_excerpt(), _wilson_interval()

### Community 60 - "Community 60"
Cohesion: 0.21
Nodes (10): _infer_mana_from_land(), _is_land_card(), pass_priority(), normalize_cost_choice(), _extract_equip_cost_text(), _infer_mana_from_land(), _is_land_card(), _land_colors_from_metadata() (+2 more)

### Community 61 - "Community 61"
Cohesion: 0.26
Nodes (8): _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), test_batch_exposes_first_divergence_excerpt(), test_batch_exposes_first_divergence_report(), test_batch_first_divergence_excerpt_includes_trace_context(), test_batch_is_deterministic_for_same_inputs()

### Community 62 - "Community 62"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.31
Nodes (3): _hydrate_deck_cards(), sync_card(), ScryfallSyncService

### Community 64 - "Community 64"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 65 - "Community 65"
Cohesion: 0.33
Nodes (11): combat_damage(), combat_damage(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_deathtouch_trample_assigns_one_to_blocker_and_spills_rest(), test_double_strike_deals_damage_in_both_steps(), test_first_strike_kills_before_regular_damage(), test_lifelink_gains_life_on_combat_damage() (+3 more)

### Community 66 - "Community 66"
Cohesion: 0.25
Nodes (5): apply_state_based_actions(), test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), test_legend_rule_is_per_controller_not_global(), test_legend_rule_moves_duplicate_legendary_to_graveyard()

### Community 67 - "Community 67"
Cohesion: 0.36
Nodes (10): classify_first_divergence(), classify_log_line(), _drift_excerpt(), first_log_divergence(), main(), _normalize_log_line(), Run a seeded match while preserving each game's independent replay seed., run_game() (+2 more)

### Community 68 - "Community 68"
Cohesion: 0.18
Nodes (11): extract_activated_abilities(), Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface. (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 70 - "Community 70"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 71 - "Community 71"
Cohesion: 0.36
Nodes (7): _is_main_phase_window(), main(), parse_args(), _step_key(), summarize_card_play_logic(), _games_jsonl(), test_card_play_analytics_separates_meaningful_main_phase_passes()

### Community 72 - "Community 72"
Cohesion: 0.31
Nodes (5): card_color_names(), protection_match_reason(), _protection_tokens(), protection_match_reason(), _protection_tokens()

### Community 73 - "Community 73"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 74 - "Community 74"
Cohesion: 0.36
Nodes (6): apply_sideboard(), apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 75 - "Community 75"
Cohesion: 0.43
Nodes (7): gain_life(), player_cant_gain_life(), _basic_state(), test_keyword_layer_grant_then_remove(), test_players_cant_gain_life_lock(), test_players_cant_lose_life_lock(), test_you_cant_gain_life_lock()

### Community 76 - "Community 76"
Cohesion: 0.25
Nodes (7): test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell(), test_hexproof_blocks_opponent_targeted_spell(), test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell()

### Community 77 - "Community 77"
Cohesion: 0.29
Nodes (3): draw_cards(), replace_draw_cards(), draw_card()

### Community 78 - "Community 78"
Cohesion: 0.25
Nodes (6): When an unblocked attacker targets a PW that leaves the battlefield,     the dam, test_attack_can_target_planeswalker_and_reduce_loyalty(), test_planeswalker_loyalty_ability_appears_in_legal_moves(), test_unblocked_damage_to_removed_planeswalker_disappears(), test_attack_can_target_planeswalker_and_reduce_loyalty(), test_planeswalker_loyalty_ability_appears_in_legal_moves()

### Community 79 - "Community 79"
Cohesion: 0.29
Nodes (5): test_london_mulligan_flow_completes_pregame(), test_sorcery_speed_not_castable_off_main_timing(), test_first_player_skips_first_draw_with_explicit_log(), test_london_mulligan_flow_completes_pregame(), test_players_draw_on_later_turns_with_hand_count_change_log()

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (7): cast_from_graveyard(), Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The

### Community 81 - "Community 81"
Cohesion: 0.29
Nodes (7): put_land_from_hand(), Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is

### Community 82 - "Community 82"
Cohesion: 0.43
Nodes (7): AI, Card Data, Current Features, Gameplay, Simulation and Diagnostics, UI, What It Does

### Community 83 - "Community 83"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 84 - "Community 84"
Cohesion: 0.6
Nodes (5): main(), _merge_card_rows(), _merge_priors(), _read_training_run_examples(), _read_training_run_logs()

### Community 85 - "Community 85"
Cohesion: 0.53
Nodes (5): _human_priority_pause(), _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

### Community 86 - "Community 86"
Cohesion: 0.33
Nodes (6): Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., transform_card()

### Community 87 - "Community 87"
Cohesion: 0.33
Nodes (6): Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., transform_if_top_matches()

### Community 89 - "Community 89"
Cohesion: 0.4
Nodes (4): profile_for(), test_matchup_profile_pushes_combo_lite_to_proactive_conversion_against_control(), test_matchup_profile_pushes_control_to_hold_up_against_aggro(), test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control()

### Community 90 - "Community 90"
Cohesion: 0.4
Nodes (5): _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), apply_damage_replacements()

### Community 91 - "Community 91"
Cohesion: 0.5
Nodes (5): cycle_draw(), draw_cards(), Resolve the draw portion of a fixed-cost cycling ability., Resolve the draw portion of a fixed-cost cycling ability., draw_card()

### Community 92 - "Community 92"
Cohesion: 0.4
Nodes (5): look_top_choose(), Resolve a three-pile top-card choice using deterministic value ordering., Resolve a three-pile top-card choice using deterministic value ordering., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback.

### Community 93 - "Community 93"
Cohesion: 0.4
Nodes (5): code:bash (cd backend), Diagnostics, Expansion Top Deck Catalog, Frontend build check, How to Add Decks

### Community 94 - "Community 94"
Cohesion: 0.83
Nodes (3): test_ai_materializes_legal_crew_selection(), test_crew_turns_vehicle_into_tapped_creature_until_cleanup(), _vehicle_state()

### Community 96 - "Community 96"
Cohesion: 0.83
Nodes (3): _saga_state(), test_saga_adds_lore_and_places_chapter_on_stack(), test_saga_is_sacrificed_after_final_chapter_resolves()

### Community 98 - "Community 98"
Cohesion: 0.5
Nodes (3): Choose a bounded tactical horizon without making every turn expensive., Choose a bounded tactical horizon without making every turn expensive., Choose a bounded tactical horizon without making every turn expensive.

### Community 99 - "Community 99"
Cohesion: 0.67
Nodes (4): code:json ({), code:bash (cd backend), Round-robin anomaly scan, Tournament Data Ingest (Training Corpus)

### Community 100 - "Community 100"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 102 - "Community 102"
Cohesion: 0.67
Nodes (3): When an unblocked attacker targets a PW that leaves the battlefield,     the dam, When an unblocked attacker targets a PW that leaves the battlefield,     the dam, test_unblocked_damage_to_removed_planeswalker_disappears()

### Community 103 - "Community 103"
Cohesion: 0.67
Nodes (3): Indestructible creatures should survive lethal spell damage., Indestructible creatures should survive lethal spell damage., test_deal_damage_respects_indestructible()

### Community 105 - "Community 105"
Cohesion: 0.67
Nodes (3): Sub-lethal damage should not kill the creature., Sub-lethal damage should not kill the creature., test_deal_damage_non_lethal_doesnt_kill()

### Community 106 - "Community 106"
Cohesion: 0.67
Nodes (3): _count_controlled_type(), lose_life(), player_cant_lose_life()

### Community 108 - "Community 108"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

### Community 109 - "Community 109"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

## Knowledge Gaps
- **341 isolated node(s):** `Report cached metadata and asset gaps for a deck's distinct card names.`, `Choose a bounded tactical horizon without making every turn expensive.`, `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Evaluate small-board blocker assignments by resolving cloned combat.`, `Search small-board attack subsets through the defender's best legal blocks.` (+336 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 1` to `Community 2`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 12`, `Community 18`, `Community 26`, `Community 28`, `Community 30`, `Community 36`, `Community 37`, `Community 39`, `Community 42`, `Community 46`, `Community 47`, `Community 59`, `Community 67`, `Community 85`, `Community 94`, `Community 97`, `Community 98`?**
  _High betweenness centrality (0.177) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 12` to `Community 0`, `Community 1`, `Community 2`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 11`, `Community 16`, `Community 18`, `Community 21`, `Community 22`, `Community 30`, `Community 37`, `Community 39`, `Community 42`, `Community 46`, `Community 49`, `Community 50`, `Community 60`, `Community 66`, `Community 67`, `Community 76`, `Community 77`, `Community 78`, `Community 79`, `Community 85`, `Community 94`, `Community 96`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `CardInstance` connect `Community 23` to `Community 32`, `Community 96`, `Community 0`, `Community 1`, `Community 5`, `Community 8`, `Community 9`, `Community 104`, `Community 75`, `Community 12`, `Community 45`, `Community 16`, `Community 49`, `Community 22`, `Community 94`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 145 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 145 INFERRED edges - model-reasoned connections that need verification._
- **Are the 146 inferred relationships involving `str` (e.g. with `_controller_snapshot()` and `_restore_active_matches()`) actually correct?**
  _`str` has 146 INFERRED edges - model-reasoned connections that need verification._
- **Are the 141 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 141 INFERRED edges - model-reasoned connections that need verification._
- **Are the 154 inferred relationships involving `CardInstance` (e.g. with `EffectSpec` and `AbilitySpec`) actually correct?**
  _`CardInstance` has 154 INFERRED edges - model-reasoned connections that need verification._