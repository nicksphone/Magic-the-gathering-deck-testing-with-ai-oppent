# Graph Report - mtg-deck-testing-lab  (2026-07-10)

## Corpus Check
- 143 files · ~377,023 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1733 nodes · 4650 edges · 95 communities (90 shown, 5 thin omitted)
- Extraction: 54% EXTRACTED · 46% INFERRED · 0% AMBIGUOUS · INFERRED: 2162 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7c90aa5d`
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
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 192 edges
2. `from_decks()` - 143 edges
3. `from_decks()` - 136 edges
4. `RulesEngine` - 113 edges
5. `AIAgent` - 87 edges
6. `RulesEngine` - 79 edges
7. `CardInstance` - 64 edges
8. `Repository` - 61 edges
9. `DeckService` - 49 edges
10. `Repository` - 49 edges

## Surprising Connections (you probably didn't know these)
- `test_hydrate_deck_cards_uses_fallback_when_cache_unavailable()` --calls--> `_hydrate_deck_cards()`  [INFERRED]
  backend/tests/test_fallback_hydration.py → backend/main.py
- `test_control_ai_prefers_removal_against_evasive_threat()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_create_token_assigns_image_uri()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_token_images.py → backend/effects/registry.py
- `test_replacement_gain_life_to_draw_cards()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_new_rules_batch.py → backend/effects/registry.py
- `test_cast_only_during_your_turn_restriction_and_move_hint()` --calls--> `RulesEngine`  [INFERRED]
  backend/tests/test_restrictions.py → backend/rules_engine/engine.py

## Communities (95 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (88): build_cast_hints(), enrich_divide_total(), validate_cast_choice(), CardInstance, PlayerState, _extract_keywords_from_text(), _extract_modes(), _first_creature() (+80 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (72): _active_card_surface(), _board_value(), _creature_value(), evaluate_board(), evaluate_inevitability(), _noncreature_value(), _planeswalker_count(), _types_from_type_line() (+64 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (47): analyze_deck(), _card_text_matches(), _cmc(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _summarize_card_metadata(), _batch_seed() (+39 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (52): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_aggro_cast_bias_values_stronger_modal_face_higher(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_avoids_casting_x_spells_when_only_x_zero_is_possible(), test_ai_avoids_low_value_secure_the_wastes_early() (+44 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (51): apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands() (+43 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (42): ai_diagnostics(), apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _ensure_builtin_decks(), _ensure_expansion_top_decks(), _force_ai_land_action(), get_legal_moves() (+34 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (30): api, BatchSimulationJobStart, BatchSimulationJobStatus, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload, resolveCardMediaUrl(), ResolvedCardMetadata (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (39): check_cost_option_available(), RulesEngine, from_decks(), MatchState, legal_moves(), extract_loyalty_abilities(), can_cast_in_current_timing(), from_decks() (+31 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (22): AIAgent, _card_looks_like_land(), _step_key(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic(), test_ai_forces_land_drop_even_when_legal_moves_omit_play_land(), test_ai_forces_land_drop_on_own_main_phase() (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (20): get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_expansion_top_decks(), sync_cards_bulk(), DeckService (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (35): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, list_cards(), MatchController (+27 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (20): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, CardCache, DeckRecord (+12 more)

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (39): 3) Frontend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+31 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (5): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 14 - "Community 14"
Cohesion: 0.1
Nodes (34): resolve_effect(), draw_cards(), resolve_effect(), Zone, Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill. (+26 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (27): _classify_divergence_category(), classify_first_divergence(), classify_log_line(), first_log_divergence(), normalize_log_line(), compare_replay_logs(), get_match_replay(), classify_first_divergence() (+19 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (8): copy_ability(), copy_spell(), _copy_stack_object(), destroy_all_artifacts(), destroy_all_artifacts_and_enchantments(), destroy_all_enchantments(), _destroy_all_permanents_of_types(), create_token()

### Community 17 - "Community 17"
Cohesion: 0.06
Nodes (32): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview, Card Data and Images (+24 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (12): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.09
Nodes (17): draw_card(), RulesEngine, extract_loyalty_abilities(), test_discard_additional_cost_is_paid(), test_london_mulligan_flow_completes_pregame(), test_sorcery_speed_not_castable_off_main_timing(), test_attack_can_target_planeswalker_and_reduce_loyalty(), test_planeswalker_loyalty_ability_appears_in_legal_moves() (+9 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (8): AIDecision, AIDecision, _card_looks_like_land(), topdeck_put_creatures_battlefield(), parse_mana_cost(), parse_mana_cost(), test_control_ai_mulligan_counts_land_with_missing_types_from_oracle(), test_control_ai_mulligans_land_light_hand()

### Community 21 - "Community 21"
Cohesion: 0.14
Nodes (27): _setup_creature(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_block_declaration_hands_priority_back_to_active_player(), test_block_window_closes_after_block_assignment(), test_blocker_with_additional_block_capacity_can_block_two_attackers(), test_cannot_be_blocked_except_by_three_or_more_creatures(), test_cant_be_blocked_except_by_two_or_more_oracle_text() (+19 more)

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (27): 1. Close Rules-Engine Gaps, 1. Expand Rules-Engine Coverage, 2. Deepen AI Decision Quality, 2. Finish BO3 and Sideboard UX, 2. Improve AI Decision Quality, 3. Broaden Training and Diagnostics, 3. Expand Diagnostics and Regression Coverage, 3. Improve AI Tactical Strength (+19 more)

### Community 23 - "Community 23"
Cohesion: 0.13
Nodes (16): compute_max_land_plays_this_turn(), apply_state_based_actions(), apply_state_based_actions(), test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), Creatures present at untap lose summoning sickness; new ones keep it., A creature entering during a player's own turn keeps summoning sickness until th, test_summoning_sickness_cleared_only_for_old_creatures() (+8 more)

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (23): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #15 — Library search stopped after first match (FIXED), #16 — Destroyed permanents kept stale damage/prevention counters (FIXED) (+15 more)

### Community 25 - "Community 25"
Cohesion: 0.15
Nodes (22): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _creature_is_lethally_damaged(), _defender_label(), _max_attackers_blockable_by_creature(), _minimum_blockers_required(), _remove_dead_creatures(), _valid_defenders() (+14 more)

### Community 26 - "Community 26"
Cohesion: 0.13
Nodes (21): destroy_all_creatures(), destroy_permanent(), draw_cards(), gain_life(), lose_life(), sacrifice(), gain_life(), replace_draw_cards() (+13 more)

### Community 27 - "Community 27"
Cohesion: 0.13
Nodes (20): simulate_batch_start(), create_token(), topdeck_put_creatures_battlefield(), Enum, assign_static_order_on_battlefield_entry(), _infer_keywords(), _infer_loyalty(), _infer_power() (+12 more)

### Community 28 - "Community 28"
Cohesion: 0.19
Nodes (17): attach_if_legal(), attached_to(), is_aura(), is_equipment(), StackItem, pass_priority(), add_to_stack(), resolve_top_of_stack() (+9 more)

### Community 29 - "Community 29"
Cohesion: 0.22
Nodes (16): autoplay_tick(), init_db(), autoplay_tick(), _default_player_for_state(), get_legal_moves(), _ensure_card_faces_column(), init_db(), main() (+8 more)

### Community 30 - "Community 30"
Cohesion: 0.14
Nodes (18): _has_any_target_options(), _is_land_card(), card_cant_block(), card_must_attack_if_able(), card_must_block_if_able(), declare_attackers(), _defender_label(), _can_cast_spell() (+10 more)

### Community 31 - "Community 31"
Cohesion: 0.17
Nodes (18): declare_attackers(), card_cant_attack(), test_defender_creature_cannot_attack(), test_vigilance_attacker_does_not_tap(), _setup_creature(), test_cant_attack_alone_enforced(), test_cant_attack_creature_is_filtered_from_attackers(), test_must_attack_if_able_auto_added_when_omitted() (+10 more)

### Community 32 - "Community 32"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 33 - "Community 33"
Cohesion: 0.18
Nodes (7): suggest_card(), DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 34 - "Community 34"
Cohesion: 0.16
Nodes (13): card_color_names(), _damage_prevented_by_protection(), protected_from_source(), protection_match_reason(), _protection_tokens(), _damage_prevented_by_protection(), _deal_unblocked_damage(), protected_from_source() (+5 more)

### Community 35 - "Community 35"
Cohesion: 0.22
Nodes (5): sync_card(), ScryfallSyncService, _DummyRepo, test_extract_remote_image_uri_falls_back_to_face_images(), test_extract_remote_image_uri_prefers_root_normal()

### Community 36 - "Community 36"
Cohesion: 0.26
Nodes (15): emit_event(), _order_apnap(), _put_trigger_creature(), test_apnap_trigger_order_on_shared_event(), test_begin_end_step_triggers_only_for_active_player_when_oracle_says_your(), test_begin_upkeep_triggers_apply_apnap_for_each_upkeep_text(), _put_trigger_creature(), test_apnap_trigger_order_on_shared_event() (+7 more)

### Community 37 - "Community 37"
Cohesion: 0.19
Nodes (15): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), apply_additional_costs() (+7 more)

### Community 38 - "Community 38"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 39 - "Community 39"
Cohesion: 0.22
Nodes (14): _collect_triggers(), emit_event(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), destroy_permanent(), sacrifice() (+6 more)

### Community 40 - "Community 40"
Cohesion: 0.24
Nodes (9): AnalyticsService, analytics_history(), simulate_batch(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), test_batch_exposes_first_divergence_report() (+1 more)

### Community 41 - "Community 41"
Cohesion: 0.17
Nodes (13): _deal_unblocked_damage(), _mark_creature_damage(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), _creature_is_lethally_damaged(), deal_damage() (+5 more)

### Community 42 - "Community 42"
Cohesion: 0.38
Nodes (13): combat_damage(), combat_damage(), _setup_creature(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_deathtouch_trample_assigns_one_to_blocker_and_spills_rest(), test_double_strike_deals_damage_in_both_steps(), test_first_strike_kills_before_regular_damage() (+5 more)

### Community 44 - "Community 44"
Cohesion: 0.27
Nodes (10): classify(), main(), classify(), _looks_like_main_phase_pass_loop(), main(), _parse_trace(), test_classify_detects_land_drop_miss(), test_classify_detects_main_phase_pass_loop_from_ai_traces() (+2 more)

### Community 45 - "Community 45"
Cohesion: 0.24
Nodes (9): ensure_placeholder_image(), _family(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri(), _search_scryfall_token_image(), test_create_token_assigns_image_uri() (+1 more)

### Community 46 - "Community 46"
Cohesion: 0.21
Nodes (4): ingest_tournament_json(), tournament_event_summary(), Ingest external tournament event payloads into normalized local tables.      Exp, TournamentIngestService

### Community 47 - "Community 47"
Cohesion: 0.3
Nodes (12): declare_blockers(), declare_blockers(), test_blocker_with_additional_block_capacity_can_block_two_attackers(), test_cannot_be_blocked_except_by_three_or_more_creatures(), test_cant_be_blocked_except_by_two_or_more_oracle_text(), test_default_blocker_cannot_block_two_attackers(), test_flying_attacker_cannot_be_blocked_by_ground_creature(), test_islandwalk_attacker_can_be_blocked_without_island() (+4 more)

### Community 48 - "Community 48"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 49 - "Community 49"
Cohesion: 0.35
Nodes (10): _state(), test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented(), test_controller_scoped_damage_cant_be_prevented_ignores_shield(), test_destroy_permanent_clears_stale_damage_and_prevention_counters(), test_destroy_permanent_respects_another_creature_variant(), test_destroy_permanent_respects_die_to_exile_replacement(), test_destroy_permanent_respects_nontoken_die_replacement_variant(), test_global_damage_cant_be_prevented_ignores_player_shield() (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 51 - "Community 51"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 55 - "Community 55"
Cohesion: 0.22
Nodes (9): _auto_bottom_cards(), _infer_mana_from_land(), _is_land_card(), _auto_bottom_cards(), _extract_equip_cost_text(), _infer_mana_from_land(), _is_land_card(), _land_colors_from_metadata() (+1 more)

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (8): _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line(), test_training_example_export_preserves_trace_labels()

### Community 57 - "Community 57"
Cohesion: 0.2
Nodes (9): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+1 more)

### Community 58 - "Community 58"
Cohesion: 0.31
Nodes (6): build_priors_from_logs(), save_log_priors(), rebuild_ai_priors(), main(), _read_training_run_logs(), test_build_priors_extracts_card_timing()

### Community 59 - "Community 59"
Cohesion: 0.36
Nodes (7): _is_main_phase_window(), main(), parse_args(), _step_key(), summarize_card_play_logic(), _games_jsonl(), test_card_play_analytics_separates_meaningful_main_phase_passes()

### Community 60 - "Community 60"
Cohesion: 0.36
Nodes (7): prevent_damage(), prevent_damage(), add_card_prevention_shield(), add_player_prevention_shield(), test_deal_damage_to_creature_marks_damage_not_toughness(), test_prevent_damage_shield_reduces_creature_damage(), test_prevent_damage_shield_reduces_player_damage()

### Community 61 - "Community 61"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 62 - "Community 62"
Cohesion: 0.25
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 63 - "Community 63"
Cohesion: 0.29
Nodes (8): code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import Format, Diagnostics and Simulation, Quick matchup debug, Round-robin anomaly scan, Tournament Data Ingest (Training Corpus)

### Community 64 - "Community 64"
Cohesion: 0.29
Nodes (5): load_log_priors(), profile_for(), get_ai_priors(), test_matchup_profile_pushes_control_to_hold_up_against_aggro(), test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control()

### Community 65 - "Community 65"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 66 - "Community 66"
Cohesion: 0.29
Nodes (6): test_replacement_gain_life_to_draw_cards(), test_ward_tax_blocks_underpaid_targeted_spell(), test_hexproof_blocks_opponent_targeted_spell(), test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell()

### Community 68 - "Community 68"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 69 - "Community 69"
Cohesion: 0.53
Nodes (5): _human_priority_pause(), _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

### Community 70 - "Community 70"
Cohesion: 0.3
Nodes (5): Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Spell damage should kill creatures — state-based lethal check after damage., Spell damage should kill creatures — state-based lethal check after damage., test_deal_damage_destroys_creature_with_lethal_damage()

### Community 71 - "Community 71"
Cohesion: 0.6
Nodes (4): _apply_legend_rule(), _is_legendary(), _apply_legend_rule(), _is_legendary()

### Community 72 - "Community 72"
Cohesion: 0.4
Nodes (5): AI, Card Data, Gameplay, Simulation and Diagnostics, What It Does

### Community 73 - "Community 73"
Cohesion: 0.4
Nodes (5): code:text (4 Lightning Bolt), Deck Import, Expansion Top Deck Catalog, Frontend build check, How to Add Decks

### Community 75 - "Community 75"
Cohesion: 0.83
Nodes (3): load_json(), main(), run_cmd()

### Community 76 - "Community 76"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 77 - "Community 77"
Cohesion: 0.67
Nodes (3): Bug #8: resolve_effect should gracefully handle non-dict payloads., Bug #8: resolve_effect should gracefully handle non-dict payloads., test_resolve_effect_rejects_non_dict_payload()

### Community 80 - "Community 80"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

### Community 81 - "Community 81"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

## Knowledge Gaps
- **185 isolated node(s):** `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Push control decks to convert resources instead of over-passing in developed boa`, `Ingest external tournament event payloads into normalized local tables.      Exp`, `When an unblocked attacker targets a PW that leaves the battlefield,     the dam`, `Spell damage should kill creatures — state-based lethal check after damage.` (+180 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 3` to `Community 64`, `Community 1`, `Community 2`, `Community 5`, `Community 69`, `Community 7`, `Community 8`, `Community 40`, `Community 10`, `Community 13`, `Community 15`, `Community 18`, `Community 19`, `Community 20`, `Community 53`, `Community 29`, `Community 62`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 19` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 10`, `Community 14`, `Community 15`, `Community 20`, `Community 21`, `Community 23`, `Community 27`, `Community 28`, `Community 29`, `Community 31`, `Community 36`, `Community 40`, `Community 55`, `Community 64`, `Community 66`, `Community 69`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 7` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 69`, `Community 36`, `Community 8`, `Community 42`, `Community 28`, `Community 14`, `Community 47`, `Community 19`, `Community 23`, `Community 27`, `Community 60`, `Community 29`, `Community 31`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 110 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 110 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 103 inferred relationships involving `str` (e.g. with `sync_cards_bulk()` and `ingest_tournament_json()`) actually correct?**
  _`str` has 103 INFERRED edges - model-reasoned connections that need verification._