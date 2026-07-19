# Graph Report - mtg-deck-testing-lab  (2026-07-19)

## Corpus Check
- 176 files · ~442,281 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2474 nodes · 6368 edges · 124 communities (122 shown, 2 thin omitted)
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 2835 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2e3f48a7`
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
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 241 edges
2. `CardInstance` - 172 edges
3. `RulesEngine` - 159 edges
4. `from_decks()` - 143 edges
5. `from_decks()` - 136 edges
6. `AIAgent` - 87 edges
7. `resolve_effect()` - 81 edges
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
- `test_best_of_replay_aggregates_games_deterministically()` --calls--> `run_match()`  [INFERRED]
  backend/tests/test_seed_and_replay.py → backend/scripts/regression_matrix_replay.py

## Communities (124 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (82): AIAgent, test_ai_materializes_graveyard_spell_target_for_recursion(), test_ai_materializes_required_library_search_choice(), test_master_attack_search_avoids_throwing_small_creature_into_large_blocker(), test_master_block_search_prevents_lethal_damage_when_trade_is_available(), test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_mulligans_hand_without_early_pressure(), test_aggro_ai_prefers_creature_development_over_burn_early() (+74 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (56): decision_reason_code(), has_actionable_move(), has_meaningful_move(), is_actionable_move(), is_meaningful_move(), Shared classification for AI decision-trace diagnostics., Exclude pass and restricted UI placeholders from legal-action diagnostics., Identify actions that change resources, board state, or combat decisions. (+48 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (37): api, BatchSimulationJobStart, BatchSimulationJobStatus, CardCompletenessReport, configuredApi, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (59): _auto_bottom_cards(), topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost() (+51 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (47): _get_attr_or_key(), select_display_image_uri(), fallback_card_payload(), _fallback_name_aliases(), _normalize_card_name(), get_with_backoff(), ensure_placeholder_image(), _family() (+39 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (45): RulesEngine, resolve_top_of_stack(), test_discard_additional_cost_is_paid(), test_additional_land_effect_text_allows_second_land_same_turn(), test_engine_rejects_play_land_when_player_is_not_active(), test_land_named_card_is_not_offered_as_cast_spell_even_if_mistyped(), test_mana_creature_is_not_misclassified_as_land_from_oracle_text(), test_non_active_player_cannot_get_play_land_legal_move() (+37 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (47): ai_diagnostics(), analytics_history(), apply_sideboard(), _card_looks_like_land(), _controller_snapshot(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves() (+39 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (52): from_decks(), _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState, legal_moves() (+44 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (46): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, ingest_tournament_json(), PriorityStopsRequest (+38 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (31): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_decks() (+23 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (27): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIDecision, guess_archetype(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available() (+19 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (51): CardInstance, infer_effect_from_oracle(), infer_effect_from_oracle(), CardInstance, test_x_mode_inference_respects_selected_mode_and_x(), test_oracle_add_counters_parsing(), test_oracle_collected_company_style_parsing(), test_oracle_counterspell_parsing() (+43 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (46): deal_damage(), resolve_effect(), test_copying_a_spell_triggers_magecraft_style_pump(), Indestructible creatures should survive lethal spell damage., Indestructible creatures should survive lethal spell damage., Sub-lethal damage should not kill the creature., Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill. (+38 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (21): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, ParsedDeck, ActiveMatchRecord (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (47): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (FIXED), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (FIXED), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED) (+39 more)

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (20): copy_ability(), copy_spell(), _copy_stack_object(), cycle_search(), destroy_all_artifacts(), destroy_all_artifacts_and_enchantments(), destroy_all_enchantments(), _destroy_all_permanents_of_types() (+12 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (36): add_counters(), deal_damage_multi(), _collect_triggers(), _first_number(), _maybe_payload(), _trigger_from_oracle(), create_token(), _collect_triggers() (+28 more)

### Community 17 - "Community 17"
Cohesion: 0.08
Nodes (42): build_cast_hints(), _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), _infer_topdeck_creature_put_effect(), inspect_target_hints(), _parse_count_token() (+34 more)

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (17): fuzzy_card_lookup(), normalize_card_lookup_name(), DeckParser, ParsedDeck, DeckParser, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions() (+9 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (38): create_shark_token(), create_token(), destroy_permanent(), discard_cards(), emit_event(), add_to_stack(), _put_trigger_creature(), _put_trigger_permanent() (+30 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (37): 3) Frontend, 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview (+29 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (17): check_cost_option_available(), RulesEngine, draw_cards(), compute_max_land_plays_this_turn(), extract_loyalty_abilities(), draw_card(), test_cannot_target_creature_with_protection_from_source_color(), test_invalid_x_target_choice_does_not_spend_mana() (+9 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (37): _setup_creature(), _setup_permanent(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_attack_declared_can_create_token_payoff(), test_attack_declared_triggers_attack_payoff(), test_block_declaration_hands_priority_back_to_active_player(), test_block_declared_triggers_block_payoff() (+29 more)

### Community 23 - "Community 23"
Cohesion: 0.1
Nodes (36): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _deal_unblocked_damage(), _mark_creature_damage(), _max_attackers_blockable_by_creature(), _minimum_blockers_required() (+28 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (3): _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (28): autoplay_tick(), _human_priority_pause(), lifespan(), MatchController, _restore_active_matches(), init_db(), autoplay_tick(), _human_priority_pause() (+20 more)

### Community 26 - "Community 26"
Cohesion: 0.11
Nodes (15): card_completeness(), list_cards(), Report cached metadata and asset gaps for a deck's distinct card names., suggest_card(), CardService, ScryfallSyncService, _BlankCachedCard, _CachedCard (+7 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (33): combat_damage(), declare_blockers(), can_cast_in_current_timing(), card_cant_attack(), card_cant_block(), card_must_block_if_able(), combat_damage(), declare_blockers() (+25 more)

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (31): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+23 more)

### Community 29 - "Community 29"
Cohesion: 0.09
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 30 - "Community 30"
Cohesion: 0.13
Nodes (30): Backend tests, code:bash (cd frontend), Frontend, Frontend, Frontend, Frontend, Frontend, Frontend (+22 more)

### Community 31 - "Community 31"
Cohesion: 0.07
Nodes (29): cast_from_graveyard(), put_land_from_hand(), Resolve an effect that puts a land from hand onto the battlefield.      This is, Resolve an effect that puts a land from hand onto the battlefield.      This is, Put a qualifying spell from the controller's graveyard onto the stack.      The, Resolve an effect that puts a land from hand onto the battlefield.      This is, Put a qualifying spell from the controller's graveyard onto the stack.      The, Return a battlefield permanent to its owner's hand without changing ownership. (+21 more)

### Community 32 - "Community 32"
Cohesion: 0.1
Nodes (25): Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Evaluate small-board blocker assignments by resolving cloned combat., Search small-board attack subsets through the defender's best legal blocks. (+17 more)

### Community 33 - "Community 33"
Cohesion: 0.07
Nodes (28): Backend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+20 more)

### Community 34 - "Community 34"
Cohesion: 0.15
Nodes (19): _board_role_hint(), build_priors_from_examples(), build_priors_from_logs(), _build_priors_payload(), _count_creatures(), load_log_priors(), _record_card_timing(), save_log_priors() (+11 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (22): _move_creature_to_graveyard(), sacrifice(), gain_life(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), apply_permanent_damage_replacements(), _battlefield_oracle_texts() (+14 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (22): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), activated_cost_available() (+14 more)

### Community 37 - "Community 37"
Cohesion: 0.15
Nodes (20): validate_cast_choice(), PlayerState, validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets(), test_choose_two_validator() (+12 more)

### Community 38 - "Community 38"
Cohesion: 0.19
Nodes (19): enrich_divide_total(), build_cast_hints(), enrich_divide_total(), validate_cast_choice(), test_non_divide_x_spell_does_not_auto_set_divide_total(), _state_with_target(), test_bounce_ability_spec_is_not_marked_as_oracle_fallback(), test_bounce_inference_exposes_nonland_permanent_targets() (+11 more)

### Community 39 - "Community 39"
Cohesion: 0.16
Nodes (7): _card_looks_like_land(), _cmc(), _auto_bottom_cards(), add_generic_to_cost(), mana_value(), parse_mana_cost(), _target_id_matches_restrictions()

### Community 40 - "Community 40"
Cohesion: 0.25
Nodes (21): effective_power(), effective_toughness(), test_counters_affect_effective_stats_dynamically(), test_other_creatures_you_control_get_bonus_excludes_source(), test_bushido_boosts_attacker_when_blocked(), test_rampage_scales_with_each_blocker_beyond_the_first(), +1/+1 and -1/-1 counters should affect effective_power/toughness without mutatin, +1/+1 and -1/-1 counters should affect effective_power/toughness without mutatin (+13 more)

### Community 41 - "Community 41"
Cohesion: 0.26
Nodes (21): _all_battlefield_ids(), _base_pt_with_layers(), _battlefield_card_matches_selector(), _battlefield_position_map(), _continuous_pt_delta(), effective_keywords(), _extract_pt_set_groups(), _graveyard_card_matches_selector() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.14
Nodes (18): _classify_divergence_category(), classify_first_divergence(), classify_log_line(), classify_timeout_state(), _parse_ai_trace_payload(), _trace_context_summary(), get_match_replay(), classify_first_divergence() (+10 more)

### Community 43 - "Community 43"
Cohesion: 0.2
Nodes (14): AnalyticsService, FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), test_compare_replay_logs_labels_cast_resolution_error(), test_compare_replay_logs_labels_face_choice_mismatch(), test_compare_replay_logs_labels_mode_choice_mismatch() (+6 more)

### Community 44 - "Community 44"
Cohesion: 0.15
Nodes (20): declare_attackers(), _defender_label(), _valid_defenders(), card_must_attack_if_able(), test_defender_creature_cannot_attack(), test_vigilance_attacker_does_not_tap(), _setup_creature(), test_cant_attack_alone_enforced() (+12 more)

### Community 45 - "Community 45"
Cohesion: 0.14
Nodes (18): emit_event(), _order_apnap(), destroy_permanent(), sacrifice(), add_to_stack(), resolve_top_of_stack(), StackItem, _put_static_permanent_with_oracle() (+10 more)

### Community 46 - "Community 46"
Cohesion: 0.16
Nodes (13): prevent_damage(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), prevent_damage(), add_card_prevention_shield(), add_player_prevention_shield() (+5 more)

### Community 47 - "Community 47"
Cohesion: 0.15
Nodes (14): AbilitySpec, build_ability_spec(), EffectSpec, Stable application-level representation of a card action.      The parser remain, test_ability_model_exposes_effect_targets_modes_and_choices(), test_ability_model_marks_unparsed_action_text_as_fallback(), test_planeswalker_static_and_loyalty_text_is_not_cast_time_fallback(), _state() (+6 more)

### Community 48 - "Community 48"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 49 - "Community 49"
Cohesion: 0.17
Nodes (15): apply_state_based_actions(), apply_state_based_actions(), _setup_creature(), _setup_permanent(), test_creatures_you_control_have_reach_allows_blocking_flyers(), test_indestructible_grant_prevents_combat_lethal_death(), test_opponent_static_minus_kills_x1_creature(), test_tribal_static_buff_applies_to_subtype() (+7 more)

### Community 50 - "Community 50"
Cohesion: 0.2
Nodes (14): deserialize_match_snapshot(), Serialize all mutable rules state needed to resume a match., serialize_match(), serialize_match_snapshot(), _tupleize(), Zone, _state(), test_day_night_change_triggers_use_the_stack() (+6 more)

### Community 51 - "Community 51"
Cohesion: 0.15
Nodes (14): StackItem, extract_saga_chapters(), Parse chapter lines into ordered lore-counter triggers., Parse chapter lines into ordered lore-counter triggers., Parse chapter lines into ordered lore-counter triggers., Parse chapter lines into ordered lore-counter triggers., Parse chapter lines into ordered lore-counter triggers., Parse chapter lines into ordered lore-counter triggers. (+6 more)

### Community 52 - "Community 52"
Cohesion: 0.25
Nodes (14): analyze_deck(), _card_text_matches(), _derive_face_based_mana_cost(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _summarize_card_metadata(), analyze_deck_payload() (+6 more)

### Community 53 - "Community 53"
Cohesion: 0.12
Nodes (15): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+7 more)

### Community 54 - "Community 54"
Cohesion: 0.2
Nodes (12): attach_if_legal(), card_color_names(), _damage_prevented_by_protection(), protected_from_source(), protection_match_reason(), _protection_tokens(), _attacker_has_active_landwalk_with_state(), _can_block_attacker() (+4 more)

### Community 55 - "Community 55"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (15): extract_activated_abilities(), Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface., Extract simple mana-cost activated abilities from a card surface. (+7 more)

### Community 57 - "Community 57"
Cohesion: 0.25
Nodes (12): _board_role_hint(), _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line() (+4 more)

### Community 58 - "Community 58"
Cohesion: 0.24
Nodes (8): first_log_divergence(), normalize_log_line(), _balance_alerts(), _batch_seed(), compare_replay_logs(), _extract_turn_summaries(), _first_divergence_excerpt(), _wilson_interval()

### Community 59 - "Community 59"
Cohesion: 0.15
Nodes (14): code:bash (cd backend), code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import, Deck Import Format, Diagnostics, Diagnostics and Simulation (+6 more)

### Community 60 - "Community 60"
Cohesion: 0.21
Nodes (13): _all_battlefield_ids(), _continuous_pt_delta(), _counter_pt_delta(), effective_keywords(), effective_power(), effective_toughness(), _has_subtype(), _is_battlefield() (+5 more)

### Community 61 - "Community 61"
Cohesion: 0.26
Nodes (3): sync_card(), sync_card(), ScryfallSyncService

### Community 62 - "Community 62"
Cohesion: 0.26
Nodes (8): _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), test_batch_exposes_first_divergence_excerpt(), test_batch_exposes_first_divergence_report(), test_batch_first_divergence_excerpt_includes_trace_context(), test_batch_is_deterministic_for_same_inputs()

### Community 63 - "Community 63"
Cohesion: 0.23
Nodes (11): crew_vehicle(), _has_any_target_options(), _is_land_card(), _can_cast_spell(), _extract_equip_cost(), _has_any_target_options(), _is_land_card(), legal_moves() (+3 more)

### Community 64 - "Community 64"
Cohesion: 0.33
Nodes (11): attached_to(), is_aura(), is_equipment(), attach_if_legal(), attached_to(), attachment_target_is_legal(), is_aura(), is_equipment() (+3 more)

### Community 65 - "Community 65"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 66 - "Community 66"
Cohesion: 0.29
Nodes (11): continuous_layer_trace(), Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., Return a deterministic trace of continuous effect application for diagnostics., _state(), test_continuous_layer_trace_includes_ordered_applied_layers(), test_continuous_layer_trace_orders_base_pt_setters_by_static_order() (+3 more)

### Community 67 - "Community 67"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 68 - "Community 68"
Cohesion: 0.18
Nodes (11): Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes., Reveal the top card and transform the source when its type condition passes. (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.27
Nodes (10): _count_controlled_type(), gain_life(), lose_life(), player_cant_gain_life(), player_cant_lose_life(), _basic_state(), test_keyword_layer_grant_then_remove(), test_players_cant_gain_life_lock() (+2 more)

### Community 70 - "Community 70"
Cohesion: 0.18
Nodes (11): Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent., Apply a selected face to a battlefield double-faced permanent. (+3 more)

### Community 71 - "Community 71"
Cohesion: 0.25
Nodes (8): _infer_mana_from_land(), _is_land_card(), pass_priority(), _extract_equip_cost_text(), _infer_mana_from_land(), _is_land_card(), _land_colors_from_metadata(), _select_face_for_cast()

### Community 72 - "Community 72"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 73 - "Community 73"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 74 - "Community 74"
Cohesion: 0.18
Nodes (11): 0. Fix runtime and deployment blockers, 1. Make match and simulator state durable, 2. Replace regex-only Oracle growth with structured abilities, 3. Complete high-value rules fidelity, 4. Raise AI from scoring to tactical planning, 5. Build a serious regression and balance matrix, 6. Finish card data and asset reliability, 7. Complete the testing UI and release hardening (+3 more)

### Community 76 - "Community 76"
Cohesion: 0.2
Nodes (10): look_top_choose(), Resolve a three-pile top-card choice using deterministic value ordering., Resolve a three-pile top-card choice using deterministic value ordering., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback., Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback. (+2 more)

### Community 77 - "Community 77"
Cohesion: 0.2
Nodes (10): 2. Finish BO3 and Sideboard UX, 3. Improve AI Tactical Strength, 4. Build a Better Training Pipeline, 5. Expand Simulator Diagnostics, 6. Polish the Competitive UI, 7. Final Release Hardening, Execution Order, Known Remaining Bugs and Gaps (+2 more)

### Community 78 - "Community 78"
Cohesion: 0.22
Nodes (9): Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter., Return whether a card satisfies a structured library-search filter. (+1 more)

### Community 79 - "Community 79"
Cohesion: 0.44
Nodes (8): _drift_excerpt(), first_log_divergence(), main(), _normalize_log_line(), Run a seeded match while preserving each game's independent replay seed., run_game(), run_match(), _stable_seed()

### Community 80 - "Community 80"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 81 - "Community 81"
Cohesion: 0.22
Nodes (9): Audit Decision Rules, Audit Status (2026-07-16), Audit Status (2026-07-18), Audit Status (2026-07-19), Current release assessment, MTG Deck Testing Lab Finish Plan, Priority Order, Verification Gates (+1 more)

### Community 82 - "Community 82"
Cohesion: 0.25
Nodes (6): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active.

### Community 83 - "Community 83"
Cohesion: 0.25
Nodes (7): cycling_cost(), cycling_is_variable(), cycling_variant(), Return a cycling cost, optionally including a validated X/Y symbol., Return a cycling cost, optionally including a validated X/Y symbol., Return a normalized search kind for alternate cycling, if present., test_alternate_cycling_variant_is_detected()

### Community 84 - "Community 84"
Cohesion: 0.25
Nodes (8): _counter_pt_delta(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card.

### Community 85 - "Community 85"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 86 - "Community 86"
Cohesion: 0.29
Nodes (5): Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep., Apply the core day/night turn-count rule at the beginning of upkeep.

### Community 87 - "Community 87"
Cohesion: 0.62
Nodes (6): _put_opponent_card(), _state(), test_controlled_type_restriction_uses_current_battlefield_count(), test_modal_counter_mode_is_structured_before_stack_target_exists(), test_nonartifact_restriction_filters_creature_targets(), test_static_mana_value_restriction_filters_targets()

### Community 88 - "Community 88"
Cohesion: 0.43
Nodes (7): AI, Card Data, Current Features, Gameplay, Simulation and Diagnostics, UI, What It Does

### Community 89 - "Community 89"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 90 - "Community 90"
Cohesion: 0.4
Nodes (5): destroy_all_creatures(), exile_permanent(), test_mass_destroy_emits_leaves_battlefield_event_before_moving_creature(), test_mass_leave_trigger_with_one_or_more_fires_once_for_the_batch(), test_permanent_leaving_battlefield_trigger_uses_event_path()

### Community 91 - "Community 91"
Cohesion: 0.4
Nodes (6): cycle_draw(), draw_cards(), Resolve the draw portion of a fixed-cost cycling ability., Resolve the draw portion of a fixed-cost cycling ability., Resolve the draw portion of a fixed-cost cycling ability., draw_card()

### Community 92 - "Community 92"
Cohesion: 0.6
Nodes (5): _state(), test_combat_only_override_applies_to_combat_damage(), test_named_source_override_does_not_unlock_other_sources(), test_target_permanent_can_have_damage_prevention_override(), test_target_player_can_have_damage_prevention_override()

### Community 93 - "Community 93"
Cohesion: 0.33
Nodes (6): 1. Close Rules-Engine Gaps, 2. Improve AI Decision Quality, 3. Expand Diagnostics and Regression Coverage, 4. Tune Balance and Deck Corpora, 5. Finish UI and Release Hardening, Step-by-Step Plan To Finish

### Community 94 - "Community 94"
Cohesion: 0.33
Nodes (6): 1. Expand Rules-Engine Coverage, 2. Deepen AI Decision Quality, 3. Broaden Training and Diagnostics, 4. Polish Competitive UI, 5. Finish Release Hardening, Remaining Work

### Community 95 - "Community 95"
Cohesion: 0.4
Nodes (5): exile_all_creatures(), Exile every creature, preserving ownership and leave events., Exile every creature, preserving ownership and leave events., Exile every creature, preserving ownership and leave events., Exile every creature, preserving ownership and leave events.

### Community 96 - "Community 96"
Cohesion: 0.4
Nodes (4): Current State, Definition of Done, MTG Deck Testing Lab Plan, Suggested Execution Order

### Community 97 - "Community 97"
Cohesion: 0.4
Nodes (5): AI quality, Remaining Gaps, Rules coverage, Simulation and diagnostics, UI and docs

### Community 98 - "Community 98"
Cohesion: 0.4
Nodes (4): profile_for(), test_matchup_profile_pushes_combo_lite_to_proactive_conversion_against_control(), test_matchup_profile_pushes_control_to_hold_up_against_aggro(), test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control()

### Community 100 - "Community 100"
Cohesion: 0.83
Nodes (3): test_ai_materializes_legal_crew_selection(), test_crew_turns_vehicle_into_tapped_creature_until_cleanup(), _vehicle_state()

### Community 102 - "Community 102"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 103 - "Community 103"
Cohesion: 0.5
Nodes (3): Choose a bounded tactical horizon without making every turn expensive., Choose a bounded tactical horizon without making every turn expensive., Choose a bounded tactical horizon without making every turn expensive.

### Community 104 - "Community 104"
Cohesion: 0.83
Nodes (3): _saga_state(), test_saga_adds_lore_and_places_chapter_on_stack(), test_saga_is_sacrificed_after_final_chapter_resolves()

### Community 106 - "Community 106"
Cohesion: 0.67
Nodes (3): counter_spell(), test_counter_spell_respects_cannot_be_countered_and_keeps_target_on_stack(), test_counter_spell_uses_spell_owner_for_countered_stolen_spell()

### Community 107 - "Community 107"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

### Community 108 - "Community 108"
Cohesion: 0.67
Nodes (3): Anthem-like buffs must not permanently modify card.power/toughness., Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats()

### Community 109 - "Community 109"
Cohesion: 0.67
Nodes (3): When an unblocked attacker targets a PW that leaves the battlefield,     the dam, When an unblocked attacker targets a PW that leaves the battlefield,     the dam, test_unblocked_damage_to_removed_planeswalker_disappears()

## Knowledge Gaps
- **399 isolated node(s):** `Report cached metadata and asset gaps for a deck's distinct card names.`, `Choose a bounded tactical horizon without making every turn expensive.`, `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Evaluate small-board blocker assignments by resolving cloned combat.`, `Search small-board attack subsets through the defender's best legal blocks.` (+394 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 0` to `Community 1`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 21`, `Community 24`, `Community 25`, `Community 28`, `Community 29`, `Community 32`, `Community 34`, `Community 39`, `Community 42`, `Community 43`, `Community 49`, `Community 50`, `Community 58`, `Community 63`, `Community 75`, `Community 79`, `Community 82`, `Community 99`, `Community 100`, `Community 103`?**
  _High betweenness centrality (0.196) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 5` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 12`, `Community 19`, `Community 21`, `Community 22`, `Community 25`, `Community 27`, `Community 34`, `Community 40`, `Community 42`, `Community 43`, `Community 44`, `Community 45`, `Community 47`, `Community 49`, `Community 50`, `Community 51`, `Community 63`, `Community 71`, `Community 79`, `Community 86`, `Community 100`, `Community 104`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `CardInstance` connect `Community 11` to `Community 0`, `Community 4`, `Community 5`, `Community 7`, `Community 12`, `Community 17`, `Community 19`, `Community 35`, `Community 37`, `Community 38`, `Community 47`, `Community 49`, `Community 50`, `Community 64`, `Community 66`, `Community 69`, `Community 87`, `Community 90`, `Community 92`, `Community 100`, `Community 104`, `Community 106`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 146 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 146 INFERRED edges - model-reasoned connections that need verification._
- **Are the 170 inferred relationships involving `CardInstance` (e.g. with `EffectSpec` and `AbilitySpec`) actually correct?**
  _`CardInstance` has 170 INFERRED edges - model-reasoned connections that need verification._
- **Are the 154 inferred relationships involving `str` (e.g. with `_controller_snapshot()` and `_restore_active_matches()`) actually correct?**
  _`str` has 154 INFERRED edges - model-reasoned connections that need verification._
- **Are the 143 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 143 INFERRED edges - model-reasoned connections that need verification._