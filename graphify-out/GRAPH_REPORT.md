# Graph Report - mtg-deck-testing-lab  (2026-07-19)

## Corpus Check
- 176 files · ~442,640 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2480 nodes · 6382 edges · 119 communities (116 shown, 3 thin omitted)
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 2841 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9c3c929c`
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
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 241 edges
2. `CardInstance` - 174 edges
3. `RulesEngine` - 159 edges
4. `from_decks()` - 143 edges
5. `from_decks()` - 136 edges
6. `AIAgent` - 87 edges
7. `resolve_effect()` - 82 edges
8. `RulesEngine` - 79 edges
9. `Repository` - 76 edges
10. `emit_event()` - 66 edges

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

## Communities (119 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (73): _board_role_hint(), build_priors_from_examples(), build_priors_from_logs(), _build_priors_payload(), _count_creatures(), _record_card_timing(), save_log_priors(), _sum_power() (+65 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (82): AIAgent, test_ai_materializes_graveyard_spell_target_for_recursion(), test_ai_materializes_required_library_search_choice(), test_master_attack_search_avoids_throwing_small_creature_into_large_blocker(), test_master_block_search_prevents_lethal_damage_when_trade_is_available(), test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_mulligans_hand_without_early_pressure(), test_aggro_ai_prefers_creature_development_over_burn_early() (+74 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (37): api, BatchSimulationJobStart, BatchSimulationJobStatus, CardCompletenessReport, configuredApi, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (57): apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands() (+49 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (50): analyze_deck(), _card_text_matches(), _cmc(), _derive_face_based_mana_cost(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _summarize_card_metadata() (+42 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (52): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), _infer_mana_from_land() (+44 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (31): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_decks() (+23 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (35): _auto_bottom_cards(), RulesEngine, compute_max_land_plays_this_turn(), from_decks(), test_discard_additional_cost_is_paid(), test_cannot_target_creature_with_protection_from_source_color(), test_invalid_x_target_choice_does_not_spend_mana(), test_land_named_card_cannot_be_cast_as_spell() (+27 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (28): add_counters(), copy_ability(), copy_spell(), _copy_stack_object(), cycle_search(), deal_damage_multi(), destroy_all_artifacts(), destroy_all_artifacts_and_enchantments() (+20 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (42): ai_diagnostics(), apply_sideboard(), autoplay_tick(), _card_looks_like_land(), _controller_snapshot(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves() (+34 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (40): check_cost_option_available(), legal_moves(), extract_loyalty_abilities(), RulesEngine, extract_loyalty_abilities(), test_additional_land_effect_text_allows_second_land_same_turn(), test_generates_basic_legal_moves(), test_land_named_card_is_not_offered_as_cast_spell_even_if_mistyped() (+32 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (51): CardInstance, infer_effect_from_oracle(), infer_effect_from_oracle(), CardInstance, test_x_mode_inference_respects_selected_mode_and_x(), test_oracle_add_counters_parsing(), test_oracle_collected_company_style_parsing(), test_oracle_counterspell_parsing() (+43 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (38): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, ingest_tournament_json(), PriorityStopsRequest (+30 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (47): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (FIXED), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (FIXED), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED) (+39 more)

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (44): deal_damage(), resolve_effect(), Indestructible creatures should survive lethal spell damage., Indestructible creatures should survive lethal spell damage., Sub-lethal damage should not kill the creature., Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Multiple damage instances should accumulate and kill. (+36 more)

### Community 15 - "Community 15"
Cohesion: 0.1
Nodes (21): AIAgent, _step_key(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic(), test_ai_forces_land_drop_even_when_legal_moves_omit_play_land(), test_ai_forces_land_drop_on_own_main_phase(), test_ai_forces_legal_land_drop_even_if_land_counter_is_desynced() (+13 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (44): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), _deal_unblocked_damage(), _defender_label(), _mark_creature_damage() (+36 more)

### Community 17 - "Community 17"
Cohesion: 0.08
Nodes (19): card_completeness(), list_cards(), Report cached metadata and asset gaps for a deck's distinct card names., suggest_card(), sync_card(), _get_attr_or_key(), select_display_image_uri(), CardService (+11 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (21): CardCache, DeckRecord, MatchRecord, StatsSnapshot, ActiveMatchRecord, CardCache, DeckRecord, MatchRecord (+13 more)

### Community 19 - "Community 19"
Cohesion: 0.1
Nodes (32): get_repo(), _human_priority_pause(), lifespan(), MatchController, _restore_active_matches(), init_db(), autoplay_tick(), get_repo() (+24 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (40): create_shark_token(), create_token(), destroy_permanent(), discard_cards(), StackItem, emit_event(), add_to_stack(), _put_trigger_creature() (+32 more)

### Community 21 - "Community 21"
Cohesion: 0.1
Nodes (39): _setup_creature(), _setup_permanent(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_attack_declared_can_create_token_payoff(), test_attack_declared_triggers_attack_payoff(), test_block_declaration_hands_priority_back_to_active_player(), test_block_declared_triggers_block_payoff() (+31 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (32): attached_to(), is_aura(), is_equipment(), attach_if_legal(), attached_to(), attachment_target_is_legal(), is_aura(), is_equipment() (+24 more)

### Community 23 - "Community 23"
Cohesion: 0.05
Nodes (37): 3) Frontend, 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture (+29 more)

### Community 24 - "Community 24"
Cohesion: 0.1
Nodes (16): fuzzy_card_lookup(), normalize_card_lookup_name(), DeckParser, ParsedDeck, DeckParser, FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests() (+8 more)

### Community 25 - "Community 25"
Cohesion: 0.09
Nodes (35): crew_vehicle(), _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), _infer_topdeck_creature_put_effect(), inspect_target_hints(), _parse_count_token() (+27 more)

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (33): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+25 more)

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (11): AIDecision, _card_looks_like_land(), AIDecision, _card_looks_like_land(), topdeck_put_creatures_battlefield(), parse_mana_cost(), _auto_bottom_cards(), mana_value() (+3 more)

### Community 28 - "Community 28"
Cohesion: 0.15
Nodes (33): _all_battlefield_ids(), _continuous_pt_delta(), _counter_pt_delta(), effective_keywords(), effective_power(), _has_subtype(), _is_battlefield(), _iter_keyword_grants() (+25 more)

### Community 29 - "Community 29"
Cohesion: 0.1
Nodes (25): classify(), main(), classify(), _looks_like_main_phase_pass_loop(), _looks_like_repeated_x_spell_error(), main(), _parse_trace(), FakeRepo (+17 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (27): Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat. (+19 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (30): Backend tests, code:bash (cd frontend), Frontend, Frontend, Frontend, Frontend, Frontend, Frontend (+22 more)

### Community 32 - "Community 32"
Cohesion: 0.14
Nodes (3): _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 33 - "Community 33"
Cohesion: 0.22
Nodes (29): combat_damage(), declare_blockers(), from_decks(), combat_damage(), declare_blockers(), _setup_creature(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output() (+21 more)

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (24): destroy_all_creatures(), exile_permanent(), resolve_top_of_stack(), add_to_stack(), resolve_top_of_stack(), _put_static_permanent_with_oracle(), test_sheoldred_opponent_draw_trigger_loses_life(), test_sheoldred_you_draw_trigger_gains_life_not_draw() (+16 more)

### Community 35 - "Community 35"
Cohesion: 0.07
Nodes (28): Backend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+20 more)

### Community 36 - "Community 36"
Cohesion: 0.22
Nodes (24): effective_power(), effective_toughness(), _setup_creature(), _setup_permanent(), test_counters_affect_effective_stats_dynamically(), test_creatures_you_control_have_reach_allows_blocking_flyers(), test_opponent_static_minus_kills_x1_creature(), test_other_creatures_you_control_get_bonus_excludes_source() (+16 more)

### Community 37 - "Community 37"
Cohesion: 0.12
Nodes (23): declare_attackers(), can_cast_in_current_timing(), card_cant_attack(), card_cant_block(), card_must_attack_if_able(), card_must_block_if_able(), can_cast_in_current_timing(), card_cant_block() (+15 more)

### Community 38 - "Community 38"
Cohesion: 0.12
Nodes (23): _move_creature_to_graveyard(), sacrifice(), draw_cards(), gain_life(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), apply_permanent_damage_replacements() (+15 more)

### Community 39 - "Community 39"
Cohesion: 0.12
Nodes (15): get_with_backoff(), ensure_placeholder_image(), _family(), _slug(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri() (+7 more)

### Community 41 - "Community 41"
Cohesion: 0.09
Nodes (21): resolve_effect(), Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Spell damage should kill creatures — state-based lethal check after damage., Indestructible creatures should survive lethal spell damage., test_create_token_respects_amount_and_keywords() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.11
Nodes (21): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState, Zone (+13 more)

### Community 43 - "Community 43"
Cohesion: 0.12
Nodes (17): AbilitySpec, build_ability_spec(), EffectSpec, Stable application-level representation of a card action.      The parser remain, test_ability_model_exposes_effect_targets_modes_and_choices(), test_ability_model_marks_unparsed_action_text_as_fallback(), test_planeswalker_static_and_loyalty_text_is_not_cast_time_fallback(), _state() (+9 more)

### Community 44 - "Community 44"
Cohesion: 0.14
Nodes (19): compact_action(), hand_snapshot(), now_utc(), parse_args(), run(), battlefield_snapshot(), _cluster_labels(), compact_action() (+11 more)

### Community 45 - "Community 45"
Cohesion: 0.14
Nodes (18): build_cast_hints(), enrich_divide_total(), validate_cast_choice(), enrich_divide_total(), test_non_divide_x_spell_does_not_auto_set_divide_total(), _state(), test_build_cast_hints_exposes_face_selection_schema(), test_bullet_and_choose_two_modes_are_exposed_as_explicit_choices() (+10 more)

### Community 46 - "Community 46"
Cohesion: 0.14
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 47 - "Community 47"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 48 - "Community 48"
Cohesion: 0.11
Nodes (18): cast_from_graveyard(), Put a qualifying spell from the controller's graveyard onto the stack.      The, Put a qualifying spell from the controller's graveyard onto the stack.      The, Return a battlefield permanent to its owner's hand without changing ownership., Put a qualifying spell from the controller's graveyard onto the stack.      The, Return a battlefield permanent to its owner's hand without changing ownership., Return a battlefield permanent to its owner's hand without changing ownership., Return a battlefield permanent to its owner's hand without changing ownership. (+10 more)

### Community 49 - "Community 49"
Cohesion: 0.21
Nodes (14): deserialize_match_snapshot(), Serialize all mutable rules state needed to resume a match., serialize_match(), serialize_match_snapshot(), _tupleize(), _state(), test_day_night_change_triggers_use_the_stack(), test_day_night_starts_at_upkeep_after_no_spells() (+6 more)

### Community 50 - "Community 50"
Cohesion: 0.26
Nodes (15): build_cast_hints(), validate_cast_choice(), _state_with_target(), test_bounce_ability_spec_is_not_marked_as_oracle_fallback(), test_bounce_inference_exposes_nonland_permanent_targets(), test_bounce_rejects_card_outside_current_target_candidates(), test_bounce_returns_stolen_permanent_to_owner_hand_and_clears_control(), _state_with_searcher() (+7 more)

### Community 51 - "Community 51"
Cohesion: 0.23
Nodes (11): AnalyticsService, analytics_history(), simulate_batch(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), test_batch_exposes_first_divergence_excerpt() (+3 more)

### Community 52 - "Community 52"
Cohesion: 0.12
Nodes (15): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+7 more)

### Community 53 - "Community 53"
Cohesion: 0.25
Nodes (14): compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main(), now_utc(), parse_args(), battlefield_snapshot() (+6 more)

### Community 54 - "Community 54"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 55 - "Community 55"
Cohesion: 0.13
Nodes (15): extract_activated_abilities(), Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface. (+7 more)

### Community 56 - "Community 56"
Cohesion: 0.24
Nodes (10): attach_if_legal(), card_color_names(), protected_from_source(), protection_match_reason(), _protection_tokens(), _can_block_attacker(), _damage_prevented_by_protection(), protected_from_source() (+2 more)

### Community 57 - "Community 57"
Cohesion: 0.15
Nodes (14): code:bash (cd backend), code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import, Deck Import Format, Diagnostics, Diagnostics and Simulation (+6 more)

### Community 58 - "Community 58"
Cohesion: 0.26
Nodes (9): _row_get(), select_representative_decks(), _row(), test_select_representative_decks_accepts_dict_rows(), test_select_representative_decks_spreads_across_archetypes_before_filling(), test_select_representative_decks_uses_guess_for_unknown_rows(), _row(), test_regression_matrix_falls_back_to_guess_archetype_for_unknown_rows() (+1 more)

### Community 59 - "Community 59"
Cohesion: 0.19
Nodes (7): cycle_draw(), draw_cards(), Resolve the draw portion of a fixed-cost cycling ability., Resolve the draw portion of a fixed-cost cycling ability., Resolve the draw portion of a fixed-cost cycling ability., draw_card(), draw_card()

### Community 60 - "Community 60"
Cohesion: 0.27
Nodes (10): fallback_card_payload(), _fallback_name_aliases(), _normalize_card_name(), fallback_card_payload(), hydrate_deck(), test_control_ramp_fallback_catalog_contains_core_fields(), test_control_ramp_fallback_catalog_contains_core_fields(), test_hydrate_deck_cards_merges_partial_cache_rows_with_fallback() (+2 more)

### Community 61 - "Community 61"
Cohesion: 0.29
Nodes (10): has_actionable_move(), has_meaningful_move(), is_actionable_move(), is_meaningful_move(), Shared classification for AI decision-trace diagnostics., Exclude pass and restricted UI placeholders from legal-action diagnostics., Identify actions that change resources, board state, or combat decisions., test_activated_and_cycling_actions_are_meaningful() (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.29
Nodes (11): continuous_layer_trace(), Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., _state(), test_continuous_layer_trace_includes_ordered_applied_layers(), test_continuous_layer_trace_orders_base_pt_setters_by_static_order() (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 64 - "Community 64"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 66 - "Community 66"
Cohesion: 0.18
Nodes (11): Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent. (+3 more)

### Community 67 - "Community 67"
Cohesion: 0.18
Nodes (11): Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes. (+3 more)

### Community 68 - "Community 68"
Cohesion: 0.18
Nodes (11): put_land_from_hand(), Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.27
Nodes (10): _count_controlled_type(), gain_life(), lose_life(), player_cant_gain_life(), player_cant_lose_life(), _basic_state(), test_keyword_layer_grant_then_remove(), test_players_cant_gain_life_lock() (+2 more)

### Community 70 - "Community 70"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 71 - "Community 71"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 72 - "Community 72"
Cohesion: 0.18
Nodes (11): 0. Fix runtime and deployment blockers, 1. Make match and simulator state durable, 2. Replace regex-only Oracle growth with structured abilities, 3. Complete high-value rules fidelity, 4. Raise AI from scoring to tactical planning, 5. Build a serious regression and balance matrix, 6. Finish card data and asset reliability, 7. Complete the testing UI and release hardening (+3 more)

### Community 74 - "Community 74"
Cohesion: 0.2
Nodes (10): look_top_choose(), Resolve a three-pile top-card choice using deterministic value ordering., Resolve a three-pile top-card choice using deterministic value ordering., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback. (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.36
Nodes (7): prevent_damage(), prevent_damage(), add_card_prevention_shield(), add_player_prevention_shield(), test_deal_damage_to_creature_marks_damage_not_toughness(), test_prevent_damage_shield_reduces_creature_damage(), test_prevent_damage_shield_reduces_player_damage()

### Community 76 - "Community 76"
Cohesion: 0.2
Nodes (10): 2. Finish BO3 and Sideboard UX, 3. Improve AI Tactical Strength, 4. Build a Better Training Pipeline, 5. Expand Simulator Diagnostics, 6. Polish the Competitive UI, 7. Final Release Hardening, Execution Order, Known Remaining Bugs and Gaps (+2 more)

### Community 77 - "Community 77"
Cohesion: 0.25
Nodes (6): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active.

### Community 78 - "Community 78"
Cohesion: 0.22
Nodes (9): Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter. (+1 more)

### Community 79 - "Community 79"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 80 - "Community 80"
Cohesion: 0.22
Nodes (9): Audit Decision Rules, Audit Status (2026-07-16), Audit Status (2026-07-18), Audit Status (2026-07-19), Current release assessment, MTG Deck Testing Lab Finish Plan, Priority Order, Verification Gates (+1 more)

### Community 81 - "Community 81"
Cohesion: 0.25
Nodes (6): load_log_priors(), profile_for(), get_ai_priors(), test_matchup_profile_pushes_combo_lite_to_proactive_conversion_against_control(), test_matchup_profile_pushes_control_to_hold_up_against_aggro(), test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control()

### Community 82 - "Community 82"
Cohesion: 0.25
Nodes (8): _counter_pt_delta(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card.

### Community 83 - "Community 83"
Cohesion: 0.39
Nodes (7): _has_any_target_options(), _is_land_card(), _can_cast_spell(), _extract_equip_cost(), _has_any_target_options(), _is_land_card(), legal_moves()

### Community 84 - "Community 84"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 85 - "Community 85"
Cohesion: 0.43
Nodes (6): decision_reason_code(), Normalize free-form AI reasoning into stable analytics labels.      The text rem, _reason(), test_common_ai_reasons_are_stable_labels(), test_main_phase_hold_up_is_distinguished_from_unexplained_pass(), test_pass_labels_cover_no_action_and_response_windows()

### Community 86 - "Community 86"
Cohesion: 0.29
Nodes (5): Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep.

### Community 87 - "Community 87"
Cohesion: 0.33
Nodes (6): counter_spell(), test_casting_player_retains_priority_for_additional_spell(), test_counter_spell_respects_cannot_be_countered_and_keeps_target_on_stack(), test_counter_spell_uses_spell_owner_for_countered_stolen_spell(), test_stack_resolution_puts_instant_into_owners_graveyard(), test_stack_resolves_after_priority_passes()

### Community 88 - "Community 88"
Cohesion: 0.62
Nodes (6): _put_opponent_card(), _state(), test_controlled_type_restriction_uses_current_battlefield_count(), test_modal_counter_mode_is_structured_before_stack_target_exists(), test_nonartifact_restriction_filters_creature_targets(), test_static_mana_value_restriction_filters_targets()

### Community 89 - "Community 89"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 90 - "Community 90"
Cohesion: 0.43
Nodes (7): AI, Card Data, Current Features, Gameplay, Simulation and Diagnostics, UI, What It Does

### Community 91 - "Community 91"
Cohesion: 0.6
Nodes (5): _state(), test_combat_only_override_applies_to_combat_damage(), test_named_source_override_does_not_unlock_other_sources(), test_target_permanent_can_have_damage_prevention_override(), test_target_player_can_have_damage_prevention_override()

### Community 92 - "Community 92"
Cohesion: 0.33
Nodes (6): 1. Expand Rules-Engine Coverage, 2. Deepen AI Decision Quality, 3. Broaden Training and Diagnostics, 4. Polish Competitive UI, 5. Finish Release Hardening, Remaining Work

### Community 93 - "Community 93"
Cohesion: 0.33
Nodes (6): 1. Close Rules-Engine Gaps, 2. Improve AI Decision Quality, 3. Expand Diagnostics and Regression Coverage, 4. Tune Balance and Deck Corpora, 5. Finish UI and Release Hardening, Step-by-Step Plan To Finish

### Community 94 - "Community 94"
Cohesion: 0.4
Nodes (5): exile_all_creatures(), Exile every creature, preserving ownership and leave events., Exile every creature, preserving ownership and leave events., Exile every creature, preserving ownership and leave events., Exile every creature, preserving ownership and leave events.

### Community 95 - "Community 95"
Cohesion: 0.4
Nodes (5): AI quality, Remaining Gaps, Rules coverage, Simulation and diagnostics, UI and docs

### Community 96 - "Community 96"
Cohesion: 0.4
Nodes (4): Current State, Definition of Done, MTG Deck Testing Lab Plan, Suggested Execution Order

### Community 97 - "Community 97"
Cohesion: 0.83
Nodes (3): test_ai_materializes_legal_crew_selection(), test_crew_turns_vehicle_into_tapped_creature_until_cleanup(), _vehicle_state()

### Community 100 - "Community 100"
Cohesion: 0.5
Nodes (3): Choose a bounded tactical horizon without making every turn expensive., Choose a bounded tactical horizon without making every turn expensive., Choose a bounded tactical horizon without making every turn expensive.

### Community 101 - "Community 101"
Cohesion: 0.83
Nodes (3): _saga_state(), test_saga_adds_lore_and_places_chapter_on_stack(), test_saga_is_sacrificed_after_final_chapter_resolves()

### Community 102 - "Community 102"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 103 - "Community 103"
Cohesion: 0.67
Nodes (3): Anthem-like buffs must not permanently modify card.power/toughness., Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats()

### Community 104 - "Community 104"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

## Knowledge Gaps
- **403 isolated node(s):** `Report cached metadata and asset gaps for a deck's distinct card names.`, `Choose a bounded tactical horizon without making every turn expensive.`, `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Evaluate small-board blocker assignments by resolving cloned combat.`, `Search small-board attack subsets through the defender's best legal blocks.` (+398 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 1` to `Community 4`, `Community 9`, `Community 10`, `Community 12`, `Community 15`, `Community 19`, `Community 22`, `Community 26`, `Community 27`, `Community 30`, `Community 32`, `Community 34`, `Community 40`, `Community 42`, `Community 44`, `Community 46`, `Community 51`, `Community 53`, `Community 65`, `Community 77`, `Community 81`, `Community 97`, `Community 100`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 10` to `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 9`, `Community 12`, `Community 14`, `Community 15`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 27`, `Community 33`, `Community 34`, `Community 36`, `Community 37`, `Community 41`, `Community 42`, `Community 43`, `Community 44`, `Community 49`, `Community 51`, `Community 53`, `Community 59`, `Community 81`, `Community 86`, `Community 87`, `Community 97`, `Community 101`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `CardInstance` connect `Community 11` to `Community 0`, `Community 1`, `Community 5`, `Community 10`, `Community 14`, `Community 20`, `Community 22`, `Community 25`, `Community 33`, `Community 34`, `Community 38`, `Community 42`, `Community 43`, `Community 45`, `Community 49`, `Community 50`, `Community 62`, `Community 69`, `Community 87`, `Community 88`, `Community 91`, `Community 97`, `Community 101`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 146 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 146 INFERRED edges - model-reasoned connections that need verification._
- **Are the 172 inferred relationships involving `CardInstance` (e.g. with `EffectSpec` and `AbilitySpec`) actually correct?**
  _`CardInstance` has 172 INFERRED edges - model-reasoned connections that need verification._
- **Are the 154 inferred relationships involving `str` (e.g. with `_controller_snapshot()` and `_restore_active_matches()`) actually correct?**
  _`str` has 154 INFERRED edges - model-reasoned connections that need verification._
- **Are the 143 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 143 INFERRED edges - model-reasoned connections that need verification._