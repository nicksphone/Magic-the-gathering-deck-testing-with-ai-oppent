# Graph Report - mtg-deck-testing-lab  (2026-07-09)

## Corpus Check
- 141 files · ~370,152 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1626 nodes · 4414 edges · 96 communities (89 shown, 7 thin omitted)
- Extraction: 52% EXTRACTED · 48% INFERRED · 0% AMBIGUOUS · INFERRED: 2100 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a5b7d784`
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
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 82|Community 82]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 179 edges
2. `from_decks()` - 143 edges
3. `from_decks()` - 136 edges
4. `RulesEngine` - 110 edges
5. `AIAgent` - 87 edges
6. `RulesEngine` - 79 edges
7. `Repository` - 61 edges
8. `CardInstance` - 54 edges
9. `DeckService` - 49 edges
10. `Repository` - 49 edges

## Surprising Connections (you probably didn't know these)
- `test_control_ai_prefers_removal_against_evasive_threat()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `deal_damage()` --calls--> `apply_damage_replacements()`  [INFERRED]
  backend/effects/handlers.py → backend/rules_engine/replacement.py
- `test_create_token_assigns_image_uri()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_token_images.py → backend/effects/registry.py
- `test_replacement_gain_life_to_draw_cards()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_new_rules_batch.py → backend/effects/registry.py
- `test_cast_only_during_your_turn_restriction_and_move_hint()` --calls--> `RulesEngine`  [INFERRED]
  backend/tests/test_restrictions.py → backend/rules_engine/engine.py

## Communities (96 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (55): topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost() (+47 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (44): analyze_deck(), _card_text_matches(), _cmc(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _batch_seed(), _extract_turn_summaries() (+36 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (46): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_aggro_cast_bias_values_stronger_modal_face_higher(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_avoids_casting_x_spells_when_only_x_zero_is_possible(), test_ai_avoids_low_value_secure_the_wastes_early() (+38 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (49): attach_if_legal(), attached_to(), is_aura(), is_equipment(), destroy_all_creatures(), destroy_permanent(), sacrifice(), _collect_triggers() (+41 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (32): check_cost_option_available(), _auto_bottom_cards(), RulesEngine, legal_moves(), extract_loyalty_abilities(), can_cast_in_current_timing(), draw_card(), test_discard_additional_cost_is_paid() (+24 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (36): ai_diagnostics(), apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves(), get_match(), _hydrate_deck_cards() (+28 more)

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (39): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, ingest_tournament_json(), list_cards() (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (26): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIDecision, test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic() (+18 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (24): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), lifespan() (+16 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (28): api, BatchSimulationJobStart, BatchSimulationJobStatus, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload, resolveCardMediaUrl(), ResolvedCardMetadata (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.1
Nodes (16): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, CardCache, DeckRecord (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (21): draw_card(), _auto_bottom_cards(), RulesEngine, test_cast_spell_rejects_if_cost_unpaid(), test_london_mulligan_flow_completes_pregame(), test_sorcery_speed_not_castable_off_main_timing(), test_replacement_gain_life_to_draw_cards(), test_ward_tax_blocks_underpaid_targeted_spell() (+13 more)

### Community 12 - "Community 12"
Cohesion: 0.2
Nodes (36): combat_damage(), declare_blockers(), from_decks(), combat_damage(), declare_blockers(), from_decks(), _setup_creature(), test_anthem_effect_allows_creature_to_survive_marked_damage() (+28 more)

### Community 13 - "Community 13"
Cohesion: 0.1
Nodes (33): resolve_effect(), resolve_effect(), Zone, Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Spell damage should kill creatures — state-based lethal check after damage. (+25 more)

### Community 14 - "Community 14"
Cohesion: 0.07
Nodes (7): copy_ability(), copy_spell(), _copy_stack_object(), create_token(), topdeck_put_creatures_battlefield(), assign_static_order_on_battlefield_entry(), create_token()

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (31): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview, Card Data and Images (+23 more)

### Community 16 - "Community 16"
Cohesion: 0.1
Nodes (28): _creature_is_lethally_damaged(), _defender_label(), _max_attackers_blockable_by_creature(), _remove_dead_creatures(), _valid_defenders(), card_cant_attack_alone(), card_cant_block(), card_must_attack_if_able() (+20 more)

### Community 17 - "Community 17"
Cohesion: 0.18
Nodes (28): _all_battlefield_ids(), _continuous_pt_delta(), effective_keywords(), _has_subtype(), _is_battlefield(), _iter_keyword_grants(), _iter_pt_modifiers(), _scope_controller() (+20 more)

### Community 18 - "Community 18"
Cohesion: 0.2
Nodes (28): CardInstance, infer_effect_from_oracle(), infer_effect_from_oracle(), CardInstance, test_x_mode_inference_respects_selected_mode_and_x(), test_oracle_add_counters_parsing(), test_oracle_collected_company_style_parsing(), test_oracle_counterspell_parsing() (+20 more)

### Community 19 - "Community 19"
Cohesion: 0.14
Nodes (27): _setup_creature(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_block_declaration_hands_priority_back_to_active_player(), test_block_window_closes_after_block_assignment(), test_blocker_with_additional_block_capacity_can_block_two_attackers(), test_cannot_be_blocked_except_by_three_or_more_creatures(), test_cant_be_blocked_except_by_two_or_more_oracle_text() (+19 more)

### Community 20 - "Community 20"
Cohesion: 0.2
Nodes (21): autoplay_tick(), MatchController, init_db(), autoplay_tick(), MatchController, _ensure_card_faces_column(), init_db(), main() (+13 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (10): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+2 more)

### Community 23 - "Community 23"
Cohesion: 0.2
Nodes (24): _combat_damage_step(), _remaining_lethal_damage(), _counter_pt_delta(), effective_power(), effective_toughness(), Return PT bonus from +1/+1 and -1/-1 counters on a card., effective_power(), effective_toughness() (+16 more)

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (23): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #15 — Library search stopped after first match (FIXED), #16 — Destroyed permanents kept stale damage/prevention counters (FIXED) (+15 more)

### Community 25 - "Community 25"
Cohesion: 0.13
Nodes (14): compute_max_land_plays_this_turn(), apply_state_based_actions(), apply_state_based_actions(), test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), Creatures present at untap lose summoning sickness; new ones keep it., A creature entering during a player's own turn keeps summoning sickness until th, test_combat_damage_reduces_life() (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.13
Nodes (19): enrich_divide_total(), validate_cast_choice(), _infer_mana_from_land(), _is_land_card(), pass_priority(), build_cast_hints(), enrich_divide_total(), validate_cast_choice() (+11 more)

### Community 27 - "Community 27"
Cohesion: 0.18
Nodes (16): classify_first_divergence(), classify_log_line(), first_log_divergence(), normalize_log_line(), compare_replay_logs(), classify_first_divergence(), classify_log_line(), first_log_divergence() (+8 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (18): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState, Zone (+10 more)

### Community 29 - "Community 29"
Cohesion: 0.16
Nodes (18): _deal_unblocked_damage(), _mark_creature_damage(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), prevent_damage(), _creature_is_lethally_damaged() (+10 more)

### Community 30 - "Community 30"
Cohesion: 0.14
Nodes (7): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., evaluate_board(), evaluate_board(), test_control_ai_prefers_removal_against_evasive_threat(), test_evaluate_board_penalizes_opponent_planeswalker_pressure(), test_evaluate_board_rewards_evasive_keyword_creatures()

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (7): suggest_card(), DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (18): 1. Close Rules-Engine Gaps, 1. Expand Rules-Engine Coverage, 2. Deepen AI Decision Quality, 2. Finish BO3 and Sideboard UX, 3. Broaden Training and Diagnostics, 3. Improve AI Tactical Strength, 4. Build a Better Training Pipeline, 4. Polish Competitive UI (+10 more)

### Community 33 - "Community 33"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 34 - "Community 34"
Cohesion: 0.18
Nodes (17): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _minimum_blockers_required(), has_keyword(), _can_cast_spell(), _has_any_target_options(), _is_land_card(), _attacker_has_active_landwalk_with_state() (+9 more)

### Community 35 - "Community 35"
Cohesion: 0.18
Nodes (18): 3) Frontend, Backend, Backend, Backend, Backend, Backend, Backend, Backend tests (+10 more)

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (16): draw_cards(), gain_life(), lose_life(), draw_cards(), gain_life(), apply_damage_replacements(), replace_draw_cards(), replace_gain_life() (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.18
Nodes (16): _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), _infer_topdeck_creature_put_effect(), _parse_count_token(), _split_clauses(), _extract_keywords_from_text() (+8 more)

### Community 38 - "Community 38"
Cohesion: 0.22
Nodes (5): sync_card(), ScryfallSyncService, _DummyRepo, test_extract_remote_image_uri_falls_back_to_face_images(), test_extract_remote_image_uri_prefers_root_normal()

### Community 39 - "Community 39"
Cohesion: 0.21
Nodes (15): declare_attackers(), card_cant_attack(), _setup_creature(), test_cant_attack_alone_enforced(), test_cant_attack_creature_is_filtered_from_attackers(), test_must_attack_if_able_auto_added_when_omitted(), test_static_you_cant_cast_spells_during_combat_enforced(), _setup_creature() (+7 more)

### Community 40 - "Community 40"
Cohesion: 0.2
Nodes (8): build_priors_from_logs(), save_log_priors(), rebuild_ai_priors(), simulate_batch_start(), main(), _read_training_run_logs(), str, test_build_priors_extracts_card_timing()

### Community 41 - "Community 41"
Cohesion: 0.21
Nodes (14): PlayerState, validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets(), test_choose_two_validator(), test_divide_validator() (+6 more)

### Community 42 - "Community 42"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 43 - "Community 43"
Cohesion: 0.2
Nodes (14): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), apply_additional_costs() (+6 more)

### Community 45 - "Community 45"
Cohesion: 0.27
Nodes (8): AnalyticsService, analytics_history(), simulate_batch(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), test_batch_is_deterministic_for_same_inputs()

### Community 46 - "Community 46"
Cohesion: 0.24
Nodes (9): ensure_placeholder_image(), _family(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri(), _search_scryfall_token_image(), test_create_token_assigns_image_uri() (+1 more)

### Community 47 - "Community 47"
Cohesion: 0.24
Nodes (8): card_color_names(), _damage_prevented_by_protection(), protected_from_source(), protection_match_reason(), _protection_tokens(), protected_from_source(), protection_match_reason(), _protection_tokens()

### Community 48 - "Community 48"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 49 - "Community 49"
Cohesion: 0.33
Nodes (11): build_cast_hints(), inspect_target_hints(), inspect_target_hints(), test_memory_deluge_does_not_require_x_value_for_cast(), test_mode_and_x_hints_exposed(), test_planeswalker_cast_does_not_require_x_value_from_loyalty_text(), test_shark_typhoon_does_not_require_x_value_for_cast(), test_memory_deluge_does_not_require_x_value_for_cast() (+3 more)

### Community 50 - "Community 50"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 51 - "Community 51"
Cohesion: 0.25
Nodes (6): FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), test_compare_replay_logs_reports_first_divergence(), test_scan_log_tracks_stall_and_land_window_anomalies()

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 53 - "Community 53"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (8): _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line(), test_training_example_export_preserves_trace_labels()

### Community 57 - "Community 57"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 58 - "Community 58"
Cohesion: 0.22
Nodes (8): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, Changelog

### Community 59 - "Community 59"
Cohesion: 0.22
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 60 - "Community 60"
Cohesion: 0.29
Nodes (8): code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import Format, Diagnostics and Simulation, Quick matchup debug, Round-robin anomaly scan, Tournament Data Ingest (Training Corpus)

### Community 61 - "Community 61"
Cohesion: 0.46
Nodes (7): _state(), test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented(), test_controller_scoped_damage_cant_be_prevented_ignores_shield(), test_destroy_permanent_clears_stale_damage_and_prevention_counters(), test_global_damage_cant_be_prevented_ignores_player_shield(), test_optional_stack_effect_can_be_declined(), test_replacement_effect_logs_redirection()

### Community 62 - "Community 62"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 63 - "Community 63"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 64 - "Community 64"
Cohesion: 0.53
Nodes (5): _human_priority_pause(), _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

### Community 65 - "Community 65"
Cohesion: 0.53
Nodes (5): _board_value(), _creature_value(), evaluate_inevitability(), _noncreature_value(), _planeswalker_count()

### Community 66 - "Community 66"
Cohesion: 0.33
Nodes (6): _counter_pt_delta(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card.

### Community 67 - "Community 67"
Cohesion: 0.4
Nodes (3): load_log_priors(), profile_for(), get_ai_priors()

### Community 68 - "Community 68"
Cohesion: 0.7
Nodes (4): _state(), test_continuous_layer_trace_includes_ordered_applied_layers(), test_continuous_layer_trace_reports_ordered_sources(), test_continuous_uses_static_order_for_grant_remove()

### Community 69 - "Community 69"
Cohesion: 0.4
Nodes (5): AI, Card Data, Gameplay, Simulation and Diagnostics, What It Does

### Community 70 - "Community 70"
Cohesion: 0.4
Nodes (5): code:text (4 Lightning Bolt), Deck Import, Expansion Top Deck Catalog, Frontend build check, How to Add Decks

### Community 71 - "Community 71"
Cohesion: 0.7
Nodes (4): _basic_state(), test_keyword_layer_grant_then_remove(), test_players_cant_gain_life_lock(), test_players_cant_lose_life_lock()

### Community 73 - "Community 73"
Cohesion: 0.83
Nodes (3): load_json(), main(), run_cmd()

### Community 74 - "Community 74"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 77 - "Community 77"
Cohesion: 0.67
Nodes (3): Bug #8: resolve_effect should gracefully handle non-dict payloads., Bug #8: resolve_effect should gracefully handle non-dict payloads., test_resolve_effect_rejects_non_dict_payload()

### Community 78 - "Community 78"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

### Community 79 - "Community 79"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

## Knowledge Gaps
- **165 isolated node(s):** `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Push control decks to convert resources instead of over-passing in developed boa`, `Ingest external tournament event payloads into normalized local tables.      Exp`, `When an unblocked attacker targets a PW that leaves the battlefield,     the dam`, `Spell damage should kill creatures — state-based lethal check after damage.` (+160 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 2` to `Community 64`, `Community 1`, `Community 67`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 59`, `Community 11`, `Community 45`, `Community 82`, `Community 20`, `Community 21`, `Community 54`, `Community 22`, `Community 27`, `Community 28`, `Community 30`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 11` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 12`, `Community 13`, `Community 19`, `Community 20`, `Community 23`, `Community 25`, `Community 26`, `Community 27`, `Community 28`, `Community 39`, `Community 45`, `Community 64`, `Community 67`, `Community 82`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 12` to `Community 64`, `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 39`, `Community 40`, `Community 41`, `Community 7`, `Community 11`, `Community 13`, `Community 49`, `Community 18`, `Community 20`, `Community 23`, `Community 25`, `Community 28`, `Community 29`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 103 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 103 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 99 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 99 INFERRED edges - model-reasoned connections that need verification._