# Graph Report - mtg-deck-testing-lab  (2026-07-16)

## Corpus Check
- 164 files · ~423,223 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2199 nodes · 5801 edges · 109 communities (103 shown, 6 thin omitted)
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 2629 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4124a547`
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
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 95|Community 95]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 231 edges
2. `from_decks()` - 143 edges
3. `RulesEngine` - 142 edges
4. `from_decks()` - 136 edges
5. `CardInstance` - 132 edges
6. `AIAgent` - 87 edges
7. `RulesEngine` - 79 edges
8. `Repository` - 75 edges
9. `resolve_effect()` - 68 edges
10. `emit_event()` - 56 edges

## Surprising Connections (you probably didn't know these)
- `test_hydrate_deck_cards_uses_fallback_when_cache_unavailable()` --calls--> `_hydrate_deck_cards()`  [INFERRED]
  backend/tests/test_fallback_hydration.py → backend/main.py
- `test_hydrate_deck_cards_uses_face_image_when_root_image_missing()` --calls--> `_hydrate_deck_cards()`  [INFERRED]
  backend/tests/test_fallback_hydration.py → backend/main.py
- `test_ai_combat_uses_granted_keywords_from_static_effects()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_control_ai_prefers_removal_against_evasive_threat()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_create_token_assigns_image_uri()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_token_images.py → backend/effects/registry.py

## Communities (109 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (77): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_mulligans_hand_without_early_pressure(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_aggro_cast_bias_values_stronger_modal_face_higher(), test_aggro_modal_face_prefers_creature_face_when_board_is_empty(), test_aggro_prefers_token_mode_over_draw_when_board_is_empty(), test_aggro_selects_token_mode_when_board_is_empty() (+69 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (60): _auto_bottom_cards(), topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost() (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (37): api, BatchSimulationJobStart, BatchSimulationJobStatus, CardCompletenessReport, configuredApi, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (55): ai_diagnostics(), apply_sideboard(), autoplay_tick(), card_completeness(), _card_looks_like_land(), _controller_snapshot(), _default_player_for_state(), _force_ai_land_action() (+47 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (49): analyze_deck(), _card_text_matches(), _cmc(), _derive_face_based_mana_cost(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _summarize_card_metadata() (+41 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (49): apply_additional_costs(), _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), _infer_mana_from_land(), _is_land_card(), _has_any_target_options() (+41 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (41): legal_moves(), RulesEngine, draw_card(), test_discard_additional_cost_is_paid(), test_additional_land_effect_text_allows_second_land_same_turn(), test_engine_rejects_play_land_when_player_is_not_active(), test_generates_basic_legal_moves(), test_land_named_card_is_not_offered_as_cast_spell_even_if_mistyped() (+33 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (26): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIDecision, test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic() (+18 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (28): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_expansion_top_decks() (+20 more)

### Community 9 - "Community 9"
Cohesion: 0.15
Nodes (42): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, ingest_tournament_json(), list_cards() (+34 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (24): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, ActiveMatchRecord, CardCache (+16 more)

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (25): add_counters(), copy_ability(), copy_spell(), _copy_stack_object(), cycle_search(), deal_damage_multi(), destroy_all_artifacts(), destroy_all_artifacts_and_enchantments() (+17 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (28): check_cost_option_available(), collect_cost_options(), CostOption, RulesEngine, compute_max_land_plays_this_turn(), extract_loyalty_abilities(), can_cast_in_current_timing(), MatchState (+20 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (47): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (FIXED), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (FIXED), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED) (+39 more)

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (46): CardInstance, infer_effect_from_oracle(), test_oracle_add_counters_parsing(), test_oracle_collected_company_style_parsing(), test_oracle_counterspell_parsing(), test_oracle_damage_parsing(), test_oracle_multiclause_sequence_parsing(), test_oracle_prevent_next_damage_parsing() (+38 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (46): 0. Fix runtime and deployment blockers, 1. Close Rules-Engine Gaps, 1. Expand Rules-Engine Coverage, 1. Make match and simulator state durable, 2. Deepen AI Decision Quality, 2. Finish BO3 and Sideboard UX, 2. Improve AI Decision Quality, 2. Replace regex-only Oracle growth with structured abilities (+38 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (45): 3) Frontend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+37 more)

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (42): combat_damage(), declare_blockers(), from_decks(), combat_damage(), declare_blockers(), apply_state_based_actions(), from_decks(), _setup_creature() (+34 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (39): deal_damage(), resolve_effect(), Indestructible creatures should survive lethal spell damage., Indestructible creatures should survive lethal spell damage., Sub-lethal damage should not kill the creature., Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Multiple damage instances should accumulate and kill. (+31 more)

### Community 19 - "Community 19"
Cohesion: 0.09
Nodes (18): fuzzy_card_lookup(), normalize_card_lookup_name(), DeckParser, ParsedDeck, DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (36): _setup_creature(), _setup_permanent(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_attack_declared_can_create_token_payoff(), test_attack_declared_triggers_attack_payoff(), test_block_declaration_hands_priority_back_to_active_player(), test_block_declared_triggers_block_payoff() (+28 more)

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (35): create_shark_token(), create_token(), destroy_permanent(), discard_cards(), emit_event(), _put_trigger_creature(), _put_trigger_permanent(), test_apnap_trigger_order_on_shared_event() (+27 more)

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (14): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (24): AnalyticsService, analytics_history(), simulate_batch(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), FakeRepo (+16 more)

### Community 24 - "Community 24"
Cohesion: 0.06
Nodes (33): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview, Card Data and Images (+25 more)

### Community 25 - "Community 25"
Cohesion: 0.12
Nodes (6): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 26 - "Community 26"
Cohesion: 0.12
Nodes (11): sync_card(), ScryfallSyncService, _BlankCachedCard, _CachedCard, _CompleteCachedCard, _DummyRepo, test_completeness_report_identifies_cached_and_missing_card_data(), test_extract_remote_image_uri_falls_back_to_face_images() (+3 more)

### Community 27 - "Community 27"
Cohesion: 0.12
Nodes (29): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), _deal_unblocked_damage(), _defender_label(), _mark_creature_damage() (+21 more)

### Community 28 - "Community 28"
Cohesion: 0.19
Nodes (28): _all_battlefield_ids(), _continuous_pt_delta(), effective_keywords(), _has_subtype(), _is_battlefield(), _iter_keyword_grants(), _iter_pt_modifiers(), _scope_controller() (+20 more)

### Community 29 - "Community 29"
Cohesion: 0.19
Nodes (27): effective_power(), effective_power(), effective_toughness(), apply_state_based_actions(), _setup_creature(), _setup_permanent(), test_counters_affect_effective_stats_dynamically(), test_creatures_you_control_have_reach_allows_blocking_flyers() (+19 more)

### Community 30 - "Community 30"
Cohesion: 0.15
Nodes (24): _collect_triggers(), emit_event(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), destroy_permanent(), sacrifice() (+16 more)

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (23): build_cast_hints(), enrich_divide_total(), inspect_target_hints(), build_cast_hints(), enrich_divide_total(), _extract_modes(), inspect_target_hints(), CardInstance (+15 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (23): destroy_all_creatures(), _move_creature_to_graveyard(), sacrifice(), draw_cards(), gain_life(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements() (+15 more)

### Community 33 - "Community 33"
Cohesion: 0.13
Nodes (4): _card_looks_like_land(), _auto_bottom_cards(), mana_value(), parse_mana_cost()

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (15): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), Zone, _infer_keywords() (+7 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (15): get_with_backoff(), ensure_placeholder_image(), _family(), _slug(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri() (+7 more)

### Community 36 - "Community 36"
Cohesion: 0.13
Nodes (20): guess_archetype(), compact_action(), hand_snapshot(), now_utc(), parse_args(), run(), battlefield_snapshot(), _cluster_labels() (+12 more)

### Community 37 - "Community 37"
Cohesion: 0.16
Nodes (21): _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle(), _infer_topdeck_creature_put_effect(), _parse_count_token(), _split_clauses() (+13 more)

### Community 38 - "Community 38"
Cohesion: 0.16
Nodes (19): validate_cast_choice(), PlayerState, validate_cast_choice(), validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets() (+11 more)

### Community 39 - "Community 39"
Cohesion: 0.14
Nodes (19): resolve_effect(), Zone, Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Spell damage should kill creatures — state-based lethal check after damage., Indestructible creatures should survive lethal spell damage. (+11 more)

### Community 40 - "Community 40"
Cohesion: 0.14
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 41 - "Community 41"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 42 - "Community 42"
Cohesion: 0.21
Nodes (15): _active_card_surface(), _board_value(), _creature_value(), evaluate_board(), evaluate_inevitability(), _noncreature_value(), _planeswalker_count(), _types_from_type_line() (+7 more)

### Community 43 - "Community 43"
Cohesion: 0.19
Nodes (14): _board_role_hint(), build_priors_from_examples(), build_priors_from_logs(), _build_priors_payload(), _count_creatures(), load_log_priors(), _record_card_timing(), save_log_priors() (+6 more)

### Community 44 - "Community 44"
Cohesion: 0.2
Nodes (12): _get_attr_or_key(), select_display_image_uri(), fallback_card_payload(), _fallback_name_aliases(), _normalize_card_name(), fallback_card_payload(), hydrate_deck(), test_control_ramp_fallback_catalog_contains_core_fields() (+4 more)

### Community 45 - "Community 45"
Cohesion: 0.21
Nodes (15): declare_attackers(), card_cant_attack(), _setup_creature(), test_cant_attack_alone_enforced(), test_cant_attack_creature_is_filtered_from_attackers(), test_must_attack_if_able_auto_added_when_omitted(), test_static_you_cant_cast_spells_during_combat_enforced(), _setup_creature() (+7 more)

### Community 46 - "Community 46"
Cohesion: 0.17
Nodes (12): card_color_names(), protected_from_source(), protection_match_reason(), _protection_tokens(), _damage_prevented_by_protection(), _deal_unblocked_damage(), protected_from_source(), protection_match_reason() (+4 more)

### Community 47 - "Community 47"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 48 - "Community 48"
Cohesion: 0.25
Nodes (14): compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main(), now_utc(), parse_args(), battlefield_snapshot() (+6 more)

### Community 49 - "Community 49"
Cohesion: 0.25
Nodes (12): _board_role_hint(), _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line() (+4 more)

### Community 50 - "Community 50"
Cohesion: 0.23
Nodes (12): classify(), main(), classify(), _looks_like_main_phase_pass_loop(), _looks_like_repeated_x_spell_error(), main(), _parse_trace(), test_anomaly_cluster_labels_x_value_and_stack_signals() (+4 more)

### Community 51 - "Community 51"
Cohesion: 0.23
Nodes (11): MatchState, AbilitySpec, build_ability_spec(), EffectSpec, Stable application-level representation of a card action.      The parser remain, test_ability_model_exposes_effect_targets_modes_and_choices(), test_ability_model_marks_unparsed_action_text_as_fallback(), test_planeswalker_static_and_loyalty_text_is_not_cast_time_fallback() (+3 more)

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (12): cast_from_graveyard(), Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The, StackItem, add_to_stack(), add_to_stack(), resolve_top_of_stack(), _put_static_permanent_with_oracle() (+4 more)

### Community 53 - "Community 53"
Cohesion: 0.35
Nodes (12): init_db(), autoplay_tick(), init_db(), main(), test_autoplay_advances_to_next_game_for_full_ai_match(), test_autoplay_forces_ai_land_drop_on_own_main_phase(), test_autoplay_land_guard_ignores_stale_land_counter_drift(), test_autoplay_land_guard_overrides_ai_cast_when_land_is_legal() (+4 more)

### Community 54 - "Community 54"
Cohesion: 0.15
Nodes (14): code:bash (cd backend), code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import, Deck Import Format, Diagnostics, Diagnostics and Simulation (+6 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (13): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+5 more)

### Community 56 - "Community 56"
Cohesion: 0.32
Nodes (12): resolve_top_of_stack(), _state_with_cycler(), test_cycling_discard_cost_emits_discard_trigger_before_cycle_draw(), test_cycling_draw_uses_draw_replacement_effects(), test_cycling_pays_cost_discards_then_draws_on_resolution(), test_cycling_trigger_is_matched_by_card_name_and_put_above_ability(), test_fixed_cycling_is_a_legal_hand_action(), test_master_lookahead_resolves_unanswered_cycle_stack() (+4 more)

### Community 57 - "Community 57"
Cohesion: 0.26
Nodes (9): _row_get(), select_representative_decks(), _row(), test_select_representative_decks_accepts_dict_rows(), test_select_representative_decks_spreads_across_archetypes_before_filling(), test_select_representative_decks_uses_guess_for_unknown_rows(), _row(), test_regression_matrix_falls_back_to_guess_archetype_for_unknown_rows() (+1 more)

### Community 58 - "Community 58"
Cohesion: 0.26
Nodes (9): prevent_damage(), prevent_damage(), add_card_prevention_shield(), add_player_prevention_shield(), consume_card_prevention_shield(), test_attack_is_declared_once_per_combat_step(), test_deal_damage_to_creature_marks_damage_not_toughness(), test_prevent_damage_shield_reduces_creature_damage() (+1 more)

### Community 60 - "Community 60"
Cohesion: 0.18
Nodes (12): card_cant_block(), card_must_attack_if_able(), card_must_block_if_able(), declare_attackers(), _defender_label(), _valid_defenders(), can_cast_in_current_timing(), card_cant_attack() (+4 more)

### Community 61 - "Community 61"
Cohesion: 0.29
Nodes (10): has_actionable_move(), has_meaningful_move(), is_actionable_move(), is_meaningful_move(), Shared classification for AI decision-trace diagnostics., Exclude pass and restricted UI placeholders from legal-action diagnostics., Identify actions that change resources, board state, or combat decisions., test_activated_and_cycling_actions_are_meaningful() (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 64 - "Community 64"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 65 - "Community 65"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 66 - "Community 66"
Cohesion: 0.33
Nodes (10): continuous_layer_trace(), Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., _state(), test_continuous_layer_trace_includes_ordered_applied_layers(), test_continuous_layer_trace_orders_base_pt_setters_by_static_order(), test_continuous_layer_trace_reports_ordered_sources() (+2 more)

### Community 68 - "Community 68"
Cohesion: 0.31
Nodes (9): gain_life(), lose_life(), player_cant_gain_life(), player_cant_lose_life(), _basic_state(), test_keyword_layer_grant_then_remove(), test_players_cant_gain_life_lock(), test_players_cant_lose_life_lock() (+1 more)

### Community 69 - "Community 69"
Cohesion: 0.33
Nodes (7): deserialize_match_snapshot(), Serialize all mutable rules state needed to resume a match., serialize_match(), serialize_match_snapshot(), _tupleize(), test_match_snapshot_round_trip_preserves_rng_sequence(), test_match_snapshot_round_trip_preserves_rules_state()

### Community 70 - "Community 70"
Cohesion: 0.36
Nodes (7): _is_main_phase_window(), main(), parse_args(), _step_key(), summarize_card_play_logic(), _games_jsonl(), test_card_play_analytics_separates_meaningful_main_phase_passes()

### Community 71 - "Community 71"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 72 - "Community 72"
Cohesion: 0.25
Nodes (7): test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell(), test_hexproof_blocks_opponent_targeted_spell(), test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell()

### Community 73 - "Community 73"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 74 - "Community 74"
Cohesion: 0.52
Nodes (6): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _apply_attachment_state_checks(), _apply_attachment_state_checks()

### Community 75 - "Community 75"
Cohesion: 0.43
Nodes (6): decision_reason_code(), Normalize free-form AI reasoning into stable analytics labels.      The text rem, _reason(), test_common_ai_reasons_are_stable_labels(), test_main_phase_hold_up_is_distinguished_from_unexplained_pass(), test_pass_labels_cover_no_action_and_response_windows()

### Community 76 - "Community 76"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 77 - "Community 77"
Cohesion: 0.43
Nodes (7): AI, Card Data, Current Features, Gameplay, Simulation and Diagnostics, UI, What It Does

### Community 78 - "Community 78"
Cohesion: 0.29
Nodes (7): _counter_pt_delta(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card.

### Community 79 - "Community 79"
Cohesion: 0.6
Nodes (5): main(), _merge_card_rows(), _merge_priors(), _read_training_run_examples(), _read_training_run_logs()

### Community 80 - "Community 80"
Cohesion: 0.6
Nodes (5): _state(), test_combat_only_override_applies_to_combat_damage(), test_named_source_override_does_not_unlock_other_sources(), test_target_permanent_can_have_damage_prevention_override(), test_target_player_can_have_damage_prevention_override()

### Community 82 - "Community 82"
Cohesion: 0.6
Nodes (4): _apply_legend_rule(), _is_legendary(), _apply_legend_rule(), _is_legendary()

### Community 83 - "Community 83"
Cohesion: 0.5
Nodes (5): cycle_draw(), draw_cards(), Resolve the draw portion of a fixed-cost cycling ability., Resolve the draw portion of a fixed-cost cycling ability., draw_card()

### Community 84 - "Community 84"
Cohesion: 0.6
Nodes (4): _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

### Community 85 - "Community 85"
Cohesion: 0.4
Nodes (4): profile_for(), test_matchup_profile_pushes_combo_lite_to_proactive_conversion_against_control(), test_matchup_profile_pushes_control_to_hold_up_against_aggro(), test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control()

### Community 88 - "Community 88"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 90 - "Community 90"
Cohesion: 0.67
Nodes (3): put_land_from_hand(), Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is

### Community 91 - "Community 91"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

### Community 92 - "Community 92"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

### Community 93 - "Community 93"
Cohesion: 0.67
Nodes (3): Anthem-like buffs must not permanently modify card.power/toughness., Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats()

## Knowledge Gaps
- **267 isolated node(s):** `Report cached metadata and asset gaps for a deck's distinct card names.`, `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Resolve simulated abilities only when the opponent has no response.`, `Push control decks to convert resources instead of over-passing in developed boa`, `Run a seeded match while preserving each game's independent replay seed.` (+262 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 0` to `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 22`, `Community 23`, `Community 25`, `Community 33`, `Community 34`, `Community 36`, `Community 40`, `Community 42`, `Community 43`, `Community 48`, `Community 51`, `Community 53`, `Community 56`, `Community 59`, `Community 84`?**
  _High betweenness centrality (0.149) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 6` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 9`, `Community 12`, `Community 17`, `Community 20`, `Community 21`, `Community 23`, `Community 29`, `Community 34`, `Community 36`, `Community 39`, `Community 43`, `Community 45`, `Community 48`, `Community 51`, `Community 53`, `Community 56`, `Community 58`, `Community 72`, `Community 84`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 17` to `Community 1`, `Community 34`, `Community 38`, `Community 6`, `Community 39`, `Community 7`, `Community 12`, `Community 45`, `Community 14`, `Community 48`, `Community 83`, `Community 51`, `Community 84`, `Community 52`, `Community 53`, `Community 58`, `Community 29`, `Community 31`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 139 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 139 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 130 inferred relationships involving `str` (e.g. with `_controller_snapshot()` and `_restore_active_matches()`) actually correct?**
  _`str` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Are the 131 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 131 INFERRED edges - model-reasoned connections that need verification._