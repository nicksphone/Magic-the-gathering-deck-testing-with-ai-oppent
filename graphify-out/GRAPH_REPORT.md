# Graph Report - mtg-deck-testing-lab  (2026-07-10)

## Corpus Check
- 141 files · ~371,643 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1652 nodes · 4462 edges · 89 communities (85 shown, 4 thin omitted)
- Extraction: 53% EXTRACTED · 47% INFERRED · 0% AMBIGUOUS · INFERRED: 2110 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e087a899`
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
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 75|Community 75]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 181 edges
2. `from_decks()` - 143 edges
3. `from_decks()` - 136 edges
4. `RulesEngine` - 110 edges
5. `AIAgent` - 87 edges
6. `RulesEngine` - 79 edges
7. `Repository` - 61 edges
8. `CardInstance` - 57 edges
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

## Communities (89 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (94): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), combat_damage(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), _deal_unblocked_damage(), declare_blockers(), _max_attackers_blockable_by_creature() (+86 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (73): _board_value(), _creature_value(), evaluate_inevitability(), _noncreature_value(), _planeswalker_count(), _combat_damage_step(), _remaining_lethal_damage(), _all_battlefield_ids() (+65 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (50): analyze_deck(), _card_text_matches(), _cmc(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _batch_seed(), _extract_turn_summaries() (+42 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (50): apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands(), count_untapped_lands_by_color() (+42 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (47): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_aggro_cast_bias_values_stronger_modal_face_higher(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_avoids_casting_x_spells_when_only_x_zero_is_possible(), test_ai_avoids_low_value_secure_the_wastes_early() (+39 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (42): AnalyticsService, ActionRequest, analytics_history(), BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest (+34 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (41): check_cost_option_available(), from_decks(), legal_moves(), extract_loyalty_abilities(), can_cast_in_current_timing(), apply_state_based_actions(), from_decks(), test_discard_additional_cost_is_paid() (+33 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (35): ai_diagnostics(), apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves(), get_match(), _hydrate_deck_cards() (+27 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (25): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), lifespan() (+17 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (28): api, BatchSimulationJobStart, BatchSimulationJobStatus, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload, resolveCardMediaUrl(), ResolvedCardMetadata (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (22): AIAgent, _card_looks_like_land(), _step_key(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic(), test_ai_forces_land_drop_even_when_legal_moves_omit_play_land(), test_ai_forces_land_drop_on_own_main_phase() (+14 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (11): copy_ability(), copy_spell(), _copy_stack_object(), create_token(), destroy_all_artifacts(), destroy_all_artifacts_and_enchantments(), destroy_all_enchantments(), _destroy_all_permanents_of_types() (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (16): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, CardCache, DeckRecord (+8 more)

### Community 13 - "Community 13"
Cohesion: 0.1
Nodes (33): resolve_effect(), draw_cards(), gain_life(), resolve_effect(), Zone, Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature. (+25 more)

### Community 14 - "Community 14"
Cohesion: 0.18
Nodes (31): CardInstance, infer_effect_from_oracle(), infer_effect_from_oracle(), CardInstance, test_x_mode_inference_respects_selected_mode_and_x(), test_oracle_add_counters_parsing(), test_oracle_collected_company_style_parsing(), test_oracle_counterspell_parsing() (+23 more)

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (31): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview, Card Data and Images (+23 more)

### Community 16 - "Community 16"
Cohesion: 0.1
Nodes (25): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), _infer_mana_from_land() (+17 more)

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (3): _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (27): 1. Close Rules-Engine Gaps, 1. Expand Rules-Engine Coverage, 2. Deepen AI Decision Quality, 2. Finish BO3 and Sideboard UX, 2. Improve AI Decision Quality, 3. Broaden Training and Diagnostics, 3. Expand Diagnostics and Regression Coverage, 3. Improve AI Tactical Strength (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.2
Nodes (21): autoplay_tick(), MatchController, init_db(), autoplay_tick(), MatchController, _ensure_card_faces_column(), init_db(), main() (+13 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (11): RulesEngine, compute_max_land_plays_this_turn(), draw_card(), MatchState, test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), Creatures present at untap lose summoning sickness; new ones keep it., A creature entering during a player's own turn keeps summoning sickness until th (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.12
Nodes (12): draw_cards(), draw_card(), RulesEngine, replace_draw_cards(), test_london_mulligan_flow_completes_pregame(), test_attack_can_target_planeswalker_and_reduce_loyalty(), test_first_player_skips_first_draw_with_explicit_log(), test_london_mulligan_flow_completes_pregame() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (18): simulate_batch_start(), Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState (+10 more)

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (23): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #15 — Library search stopped after first match (FIXED), #16 — Destroyed permanents kept stale damage/prevention counters (FIXED) (+15 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (9): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.16
Nodes (22): 3) Frontend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+14 more)

### Community 26 - "Community 26"
Cohesion: 0.19
Nodes (18): attach_if_legal(), attached_to(), is_aura(), is_equipment(), StackItem, add_to_stack(), resolve_top_of_stack(), _apply_attachment_state_checks() (+10 more)

### Community 27 - "Community 27"
Cohesion: 0.16
Nodes (19): validate_cast_choice(), PlayerState, validate_cast_choice(), validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets() (+11 more)

### Community 28 - "Community 28"
Cohesion: 0.15
Nodes (20): declare_attackers(), _defender_label(), _valid_defenders(), card_cant_attack(), test_defender_creature_cannot_attack(), test_vigilance_attacker_does_not_tap(), _setup_creature(), test_cant_attack_alone_enforced() (+12 more)

### Community 29 - "Community 29"
Cohesion: 0.14
Nodes (7): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., evaluate_board(), evaluate_board(), test_control_ai_prefers_removal_against_evasive_threat(), test_evaluate_board_penalizes_opponent_planeswalker_pressure(), test_evaluate_board_rewards_evasive_keyword_creatures()

### Community 30 - "Community 30"
Cohesion: 0.18
Nodes (16): classify_first_divergence(), classify_log_line(), first_log_divergence(), normalize_log_line(), compare_replay_logs(), classify_first_divergence(), classify_log_line(), first_log_divergence() (+8 more)

### Community 31 - "Community 31"
Cohesion: 0.2
Nodes (18): destroy_all_creatures(), destroy_permanent(), sacrifice(), emit_event(), destroy_permanent(), sacrifice(), emit_event(), _put_trigger_creature() (+10 more)

### Community 32 - "Community 32"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (16): gain_life(), lose_life(), apply_damage_replacements(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), player_cant_gain_life(), player_cant_lose_life() (+8 more)

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (16): _mark_creature_damage(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), prevent_damage(), _creature_is_lethally_damaged(), deal_damage() (+8 more)

### Community 35 - "Community 35"
Cohesion: 0.14
Nodes (5): AIDecision, AIDecision, _card_looks_like_land(), test_control_ai_mulligan_counts_land_with_missing_types_from_oracle(), test_control_ai_mulligans_land_light_hand()

### Community 36 - "Community 36"
Cohesion: 0.16
Nodes (15): build_cast_hints(), enrich_divide_total(), _has_any_target_options(), _is_land_card(), build_cast_hints(), enrich_divide_total(), _can_cast_spell(), _extract_equip_cost() (+7 more)

### Community 37 - "Community 37"
Cohesion: 0.18
Nodes (7): suggest_card(), DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 38 - "Community 38"
Cohesion: 0.2
Nodes (15): _extract_keywords_from_text(), _first_creature(), _infer_clause_effect(), _infer_topdeck_creature_put_effect(), _parse_count_token(), _split_clauses(), _choose_noncreature_permanent_target(), _extract_keywords_from_text() (+7 more)

### Community 39 - "Community 39"
Cohesion: 0.22
Nodes (5): sync_card(), ScryfallSyncService, _DummyRepo, test_extract_remote_image_uri_falls_back_to_face_images(), test_extract_remote_image_uri_prefers_root_normal()

### Community 40 - "Community 40"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 41 - "Community 41"
Cohesion: 0.19
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 42 - "Community 42"
Cohesion: 0.19
Nodes (6): _auto_bottom_cards(), topdeck_put_creatures_battlefield(), add_generic_to_cost(), parse_mana_cost(), _auto_bottom_cards(), parse_mana_cost()

### Community 43 - "Community 43"
Cohesion: 0.18
Nodes (9): build_priors_from_logs(), load_log_priors(), save_log_priors(), profile_for(), get_ai_priors(), rebuild_ai_priors(), main(), _read_training_run_logs() (+1 more)

### Community 44 - "Community 44"
Cohesion: 0.28
Nodes (12): _extract_modes(), inspect_target_hints(), _extract_modes(), inspect_target_hints(), test_memory_deluge_does_not_require_x_value_for_cast(), test_mode_and_x_hints_exposed(), test_planeswalker_cast_does_not_require_x_value_from_loyalty_text(), test_shark_typhoon_does_not_require_x_value_for_cast() (+4 more)

### Community 46 - "Community 46"
Cohesion: 0.24
Nodes (9): ensure_placeholder_image(), _family(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri(), _search_scryfall_token_image(), test_create_token_assigns_image_uri() (+1 more)

### Community 47 - "Community 47"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 48 - "Community 48"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 49 - "Community 49"
Cohesion: 0.29
Nodes (10): _collect_triggers(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), _collect_triggers(), _first_number(), _maybe_payload() (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.25
Nodes (6): FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), test_compare_replay_logs_reports_first_divergence(), test_scan_log_tracks_stall_and_land_window_anomalies()

### Community 51 - "Community 51"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 52 - "Community 52"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 53 - "Community 53"
Cohesion: 0.29
Nodes (6): card_color_names(), protection_match_reason(), _protection_tokens(), protected_from_source(), protection_match_reason(), _protection_tokens()

### Community 55 - "Community 55"
Cohesion: 0.2
Nodes (9): test_replacement_gain_life_to_draw_cards(), test_ward_tax_blocks_underpaid_targeted_spell(), Bug #8: resolve_effect should gracefully handle non-dict payloads., Bug #8: resolve_effect should gracefully handle non-dict payloads., test_hexproof_blocks_opponent_targeted_spell(), test_replacement_gain_life_to_draw_cards(), test_resolve_effect_rejects_non_dict_payload(), test_timing_restriction_first_main_phase_only() (+1 more)

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (8): _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line(), test_training_example_export_preserves_trace_labels()

### Community 57 - "Community 57"
Cohesion: 0.2
Nodes (9): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+1 more)

### Community 58 - "Community 58"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 59 - "Community 59"
Cohesion: 0.29
Nodes (8): code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import Format, Diagnostics and Simulation, Quick matchup debug, Round-robin anomaly scan, Tournament Data Ingest (Training Corpus)

### Community 60 - "Community 60"
Cohesion: 0.52
Nodes (6): _state(), test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented(), test_controller_scoped_damage_cant_be_prevented_ignores_shield(), test_destroy_permanent_clears_stale_damage_and_prevention_counters(), test_global_damage_cant_be_prevented_ignores_player_shield(), test_replacement_effect_logs_redirection()

### Community 61 - "Community 61"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 62 - "Community 62"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 63 - "Community 63"
Cohesion: 0.53
Nodes (5): _human_priority_pause(), _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

### Community 64 - "Community 64"
Cohesion: 0.6
Nodes (4): _apply_legend_rule(), _is_legendary(), _apply_legend_rule(), _is_legendary()

### Community 65 - "Community 65"
Cohesion: 0.4
Nodes (5): AI, Card Data, Gameplay, Simulation and Diagnostics, What It Does

### Community 66 - "Community 66"
Cohesion: 0.4
Nodes (5): code:text (4 Lightning Bolt), Deck Import, Expansion Top Deck Catalog, Frontend build check, How to Add Decks

### Community 68 - "Community 68"
Cohesion: 0.83
Nodes (3): load_json(), main(), run_cmd()

### Community 69 - "Community 69"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 72 - "Community 72"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

### Community 73 - "Community 73"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

## Knowledge Gaps
- **174 isolated node(s):** `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Push control decks to convert resources instead of over-passing in developed boa`, `Ingest external tournament event payloads into normalized local tables.      Exp`, `When an unblocked attacker targets a PW that leaves the battlefield,     the dam`, `Spell damage should kill creatures — state-based lethal check after damage.` (+169 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 4` to `Community 2`, `Community 35`, `Community 5`, `Community 6`, `Community 7`, `Community 41`, `Community 10`, `Community 43`, `Community 42`, `Community 75`, `Community 17`, `Community 19`, `Community 21`, `Community 22`, `Community 24`, `Community 29`, `Community 30`, `Community 63`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 10`, `Community 13`, `Community 14`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 26`, `Community 27`, `Community 28`, `Community 31`, `Community 34`, `Community 42`, `Community 44`, `Community 63`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 7`, `Community 10`, `Community 13`, `Community 14`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 26`, `Community 28`, `Community 31`, `Community 34`, `Community 42`, `Community 44`, `Community 55`, `Community 63`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 104 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 104 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 99 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 99 INFERRED edges - model-reasoned connections that need verification._