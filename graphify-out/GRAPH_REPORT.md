# Graph Report - mtg-deck-testing-lab  (2026-07-16)

## Corpus Check
- 162 files · ~421,371 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2168 nodes · 5729 edges · 103 communities (97 shown, 6 thin omitted)
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 2603 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bbbe148f`
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
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 231 edges
2. `from_decks()` - 143 edges
3. `RulesEngine` - 138 edges
4. `from_decks()` - 136 edges
5. `CardInstance` - 127 edges
6. `AIAgent` - 87 edges
7. `RulesEngine` - 79 edges
8. `Repository` - 75 edges
9. `resolve_effect()` - 66 edges
10. `emit_event()` - 56 edges

## Surprising Connections (you probably didn't know these)
- `test_ai_combat_uses_granted_keywords_from_static_effects()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_control_ai_prefers_removal_against_evasive_threat()` --calls--> `AIAgent`  [INFERRED]
  backend/tests/test_ai_heuristics.py → backend/ai/agent.py
- `test_create_token_assigns_image_uri()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_token_images.py → backend/effects/registry.py
- `test_effect_sequence_resolves_all_clauses()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_interactions_expanded.py → backend/effects/registry.py
- `test_discard_effect_targets_specified_player()` --calls--> `resolve_effect()`  [INFERRED]
  backend/tests/test_interactions_expanded.py → backend/effects/registry.py

## Communities (103 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (59): check_cost_option_available(), RulesEngine, legal_moves(), extract_loyalty_abilities(), can_cast_in_current_timing(), RulesEngine, test_discard_additional_cost_is_paid(), test_cannot_target_creature_with_protection_from_source_color() (+51 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (77): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_mulligans_hand_without_early_pressure(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_aggro_cast_bias_values_stronger_modal_face_higher(), test_aggro_modal_face_prefers_creature_face_when_board_is_empty(), test_aggro_prefers_token_mode_over_draw_when_board_is_empty(), test_aggro_selects_token_mode_when_board_is_empty() (+69 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (37): api, BatchSimulationJobStart, BatchSimulationJobStatus, CardCompletenessReport, configuredApi, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (59): _auto_bottom_cards(), topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost() (+51 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (50): ai_diagnostics(), apply_sideboard(), card_completeness(), _card_looks_like_land(), _controller_snapshot(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves() (+42 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (48): analyze_deck(), _card_text_matches(), _derive_face_based_mana_cost(), guess_archetype(), _looks_like_creature_name(), _looks_like_land(), _summarize_card_metadata(), _classify_divergence_category() (+40 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (49): has_actionable_move(), has_meaningful_move(), is_actionable_move(), is_meaningful_move(), Shared classification for AI decision-trace diagnostics., Exclude pass and restricted UI placeholders from legal-action diagnostics., Identify actions that change resources, board state, or combat decisions., classify() (+41 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (28): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIDecision, start_match(), guess_archetype(), test_aggro_ai_prefers_creature_development_over_burn_early() (+20 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (24): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, ActiveMatchRecord, CardCache (+16 more)

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (43): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest, ingest_tournament_json(), list_cards() (+35 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (48): combat_damage(), declare_blockers(), from_decks(), resolve_effect(), combat_damage(), declare_blockers(), from_decks(), _setup_creature() (+40 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (40): _hydrate_deck_cards(), _get_attr_or_key(), select_display_image_uri(), fallback_card_payload(), _fallback_name_aliases(), _normalize_card_name(), ensure_placeholder_image(), _family() (+32 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (48): resolve_effect(), CardInstance, infer_effect_from_oracle(), _infer_topdeck_creature_put_effect(), _infer_topdeck_permanent_put_effect(), inspect_target_hints(), _parse_count_token(), test_memory_deluge_does_not_require_x_value_for_cast() (+40 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (23): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_expansion_top_decks() (+15 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (47): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (FIXED), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (FIXED), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (FIXED), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED) (+39 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (46): 0. Fix runtime and deployment blockers, 1. Close Rules-Engine Gaps, 1. Expand Rules-Engine Coverage, 1. Make match and simulator state durable, 2. Deepen AI Decision Quality, 2. Finish BO3 and Sideboard UX, 2. Improve AI Decision Quality, 2. Replace regex-only Oracle growth with structured abilities (+38 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (41): create_shark_token(), create_token(), destroy_permanent(), discard_cards(), sacrifice(), emit_event(), _put_trigger_creature(), test_apnap_trigger_order_on_shared_event() (+33 more)

### Community 17 - "Community 17"
Cohesion: 0.08
Nodes (36): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), _infer_mana_from_land() (+28 more)

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (41): 3) Frontend, Backend, Backend, Backend, Backend, Backend, Backend, Backend (+33 more)

### Community 19 - "Community 19"
Cohesion: 0.09
Nodes (18): fuzzy_card_lookup(), normalize_card_lookup_name(), DeckParser, ParsedDeck, DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (36): _setup_creature(), _setup_permanent(), test_anthem_effect_allows_creature_to_survive_marked_damage(), test_anthem_effect_increases_combat_damage_output(), test_attack_declared_can_create_token_payoff(), test_attack_declared_triggers_attack_payoff(), test_block_declaration_hands_priority_back_to_active_player(), test_block_declared_triggers_block_payoff() (+28 more)

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (14): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa (+6 more)

### Community 22 - "Community 22"
Cohesion: 0.14
Nodes (35): _all_battlefield_ids(), _continuous_pt_delta(), _counter_pt_delta(), effective_keywords(), effective_toughness(), _has_subtype(), _is_battlefield(), _iter_keyword_grants() (+27 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (24): AnalyticsService, analytics_history(), simulate_batch(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a(), FakeRepo (+16 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (6): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (33): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), _mark_creature_damage(), _max_attackers_blockable_by_creature(), _minimum_blockers_required() (+25 more)

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (33): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Architecture Overview, Card Data and Images (+25 more)

### Community 27 - "Community 27"
Cohesion: 0.06
Nodes (6): add_counters(), copy_ability(), copy_spell(), _copy_stack_object(), deal_damage_multi(), create_token()

### Community 28 - "Community 28"
Cohesion: 0.12
Nodes (11): get_with_backoff(), ScryfallSyncService, _BlankCachedCard, _CachedCard, _CompleteCachedCard, _DummyRepo, test_completeness_report_identifies_cached_and_missing_card_data(), test_extract_remote_image_uri_falls_back_to_face_images() (+3 more)

### Community 29 - "Community 29"
Cohesion: 0.12
Nodes (28): build_cast_hints(), enrich_divide_total(), validate_cast_choice(), infer_effect_from_oracle(), inspect_target_hints(), _split_clauses(), build_cast_hints(), enrich_divide_total() (+20 more)

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (21): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState, Zone (+13 more)

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (24): _collect_triggers(), emit_event(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), destroy_permanent(), sacrifice() (+16 more)

### Community 32 - "Community 32"
Cohesion: 0.22
Nodes (24): effective_power(), effective_power(), effective_toughness(), _setup_creature(), _setup_permanent(), test_counters_affect_effective_stats_dynamically(), test_creatures_you_control_have_reach_allows_blocking_flyers(), test_opponent_static_minus_kills_x1_creature() (+16 more)

### Community 33 - "Community 33"
Cohesion: 0.17
Nodes (22): deal_damage(), _state(), test_combat_only_override_applies_to_combat_damage(), test_named_source_override_does_not_unlock_other_sources(), test_target_permanent_can_have_damage_prevention_override(), test_target_player_can_have_damage_prevention_override(), _state(), test_combat_damage_ignores_prevention_when_source_says_cant_be_prevented() (+14 more)

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (22): Indestructible creatures should survive lethal spell damage., Indestructible creatures should survive lethal spell damage., Sub-lethal damage should not kill the creature., Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Multiple damage instances should accumulate and kill., Spell damage should kill creatures — state-based lethal check after damage., Spell damage should kill creatures — state-based lethal check after damage. (+14 more)

### Community 35 - "Community 35"
Cohesion: 0.14
Nodes (6): _card_looks_like_land(), _cmc(), _auto_bottom_cards(), add_generic_to_cost(), mana_value(), parse_mana_cost()

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (19): _board_role_hint(), build_priors_from_examples(), build_priors_from_logs(), _build_priors_payload(), _count_creatures(), load_log_priors(), _record_card_timing(), save_log_priors() (+11 more)

### Community 37 - "Community 37"
Cohesion: 0.12
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 38 - "Community 38"
Cohesion: 0.22
Nodes (16): autoplay_tick(), init_db(), autoplay_tick(), _ensure_card_cache_columns(), _ensure_card_faces_column(), init_db(), main(), test_autoplay_advances_to_next_game_for_full_ai_match() (+8 more)

### Community 39 - "Community 39"
Cohesion: 0.18
Nodes (17): PlayerState, validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), MatchState, PlayerState, validate_cast_targets(), validate_protection_targets() (+9 more)

### Community 40 - "Community 40"
Cohesion: 0.15
Nodes (17): _has_any_target_options(), _is_land_card(), card_cant_block(), card_must_attack_if_able(), card_must_block_if_able(), declare_attackers(), _can_cast_spell(), _extract_equip_cost() (+9 more)

### Community 41 - "Community 41"
Cohesion: 0.11
Nodes (18): code:python (from card_data.models import CardFace), code:python (def test_ai_holds_modal_card_until_face_is_live():), code:markdown (- Modal and split cards carry face metadata through cache, g), code:bash (git add README.md backend/tests/test_oracle_effects.py backe), code:python (# backend/card_data/models.py), code:bash (git add backend/card_data/models.py backend/card_data/sync.p), code:python (from game_state.state import CardInstance, MatchFactory, Zon), code:python (# backend/rules_engine/oracle_effects.py) (+10 more)

### Community 42 - "Community 42"
Cohesion: 0.19
Nodes (16): StackItem, add_to_stack(), resolve_top_of_stack(), add_to_stack(), _state_with_cycler(), test_cycling_pays_cost_discards_then_draws_on_resolution(), test_cycling_trigger_is_matched_by_card_name_and_put_above_ability(), test_fixed_cycling_is_a_legal_hand_action() (+8 more)

### Community 43 - "Community 43"
Cohesion: 0.16
Nodes (10): compute_max_land_plays_this_turn(), apply_state_based_actions(), test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), Creatures present at untap lose summoning sickness; new ones keep it., A creature entering during a player's own turn keeps summoning sickness until th, test_summoning_sickness_cleared_only_for_old_creatures(), test_summoning_sickness_kept_for_creature_entering_this_turn() (+2 more)

### Community 44 - "Community 44"
Cohesion: 0.21
Nodes (15): _active_card_surface(), _board_value(), _creature_value(), evaluate_board(), evaluate_inevitability(), _noncreature_value(), _planeswalker_count(), _types_from_type_line() (+7 more)

### Community 45 - "Community 45"
Cohesion: 0.18
Nodes (16): _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), _infer_topdeck_creature_put_effect(), _parse_count_token(), choose_mana_color_for_player(), _choose_any_permanent_target() (+8 more)

### Community 46 - "Community 46"
Cohesion: 0.19
Nodes (16): declare_attackers(), _defender_label(), _valid_defenders(), card_cant_attack(), _setup_creature(), test_cant_attack_alone_enforced(), test_cant_attack_creature_is_filtered_from_attackers(), test_must_attack_if_able_auto_added_when_omitted() (+8 more)

### Community 47 - "Community 47"
Cohesion: 0.17
Nodes (5): _DeckRow, _FakeRecord, _FakeRepo, _FakeSession, test_builtin_refresh_reimports_updated_builtin_decks()

### Community 48 - "Community 48"
Cohesion: 0.18
Nodes (12): resolve_top_of_stack(), _put_static_permanent_with_oracle(), test_sheoldred_opponent_draw_trigger_loses_life(), test_sheoldred_you_draw_trigger_gains_life_not_draw(), test_aura_without_target_goes_to_graveyard(), test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell() (+4 more)

### Community 49 - "Community 49"
Cohesion: 0.25
Nodes (12): _board_role_hint(), _board_snapshot(), _count_types(), extract_examples_from_games_jsonl(), _feature_row(), main(), parse_args(), _parse_trace_line() (+4 more)

### Community 50 - "Community 50"
Cohesion: 0.14
Nodes (13): 2026-05-16, 2026-05-17, 2026-05-18, 2026-06-06, 2026-06-07, 2026-06-11, 2026-07-09, 2026-07-10 (+5 more)

### Community 51 - "Community 51"
Cohesion: 0.15
Nodes (14): code:bash (cd backend), code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import, Deck Import Format, Diagnostics, Diagnostics and Simulation (+6 more)

### Community 53 - "Community 53"
Cohesion: 0.24
Nodes (12): draw_cards(), gain_life(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), apply_permanent_damage_replacements(), _battlefield_oracle_texts(), _battlefield_position_map() (+4 more)

### Community 54 - "Community 54"
Cohesion: 0.28
Nodes (11): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _apply_attachment_state_checks(), _apply_legend_rule(), apply_state_based_actions(), _is_legendary() (+3 more)

### Community 55 - "Community 55"
Cohesion: 0.26
Nodes (3): sync_card(), sync_card(), ScryfallSyncService

### Community 56 - "Community 56"
Cohesion: 0.17
Nodes (12): destroy_all_artifacts(), destroy_all_artifacts_and_enchantments(), destroy_all_creatures(), destroy_all_enchantments(), _destroy_all_permanents_of_types(), _move_creature_to_graveyard(), Return destination zone for a dying permanent: 'graveyard' or 'exile'., Return destination zone for a dying permanent: 'graveyard' or 'exile'. (+4 more)

### Community 57 - "Community 57"
Cohesion: 0.24
Nodes (10): get_match(), _serialize_match_controller(), deserialize_match_snapshot(), Serialize all mutable rules state needed to resume a match., serialize_match(), serialize_match_snapshot(), _tupleize(), serialize_match() (+2 more)

### Community 58 - "Community 58"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 59 - "Community 59"
Cohesion: 0.24
Nodes (4): _FakeCard, _FakeRecord, _FakeRepo, test_import_deck_text_exposes_resolved_card_metadata()

### Community 60 - "Community 60"
Cohesion: 0.25
Nodes (9): cast_from_graveyard(), Put a qualifying spell from the controller's graveyard onto the stack.      The, AbilitySpec, build_ability_spec(), EffectSpec, Stable application-level representation of a card action.      The parser remain, test_ability_model_exposes_effect_targets_modes_and_choices(), test_ability_model_marks_unparsed_action_text_as_fallback() (+1 more)

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.22
Nodes (11): 1) Clone, 2) Backend, Backend, code:bash (cd backend), code:bash (cd frontend), Frontend, Open the App, Project Structure (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.31
Nodes (9): gain_life(), lose_life(), player_cant_gain_life(), player_cant_lose_life(), _basic_state(), test_keyword_layer_grant_then_remove(), test_players_cant_gain_life_lock(), test_players_cant_lose_life_lock() (+1 more)

### Community 64 - "Community 64"
Cohesion: 0.29
Nodes (6): card_color_names(), protection_match_reason(), _protection_tokens(), protected_from_source(), protection_match_reason(), _protection_tokens()

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (7): extract_loyalty_abilities(), When an unblocked attacker targets a PW that leaves the battlefield,     the dam, test_attack_can_target_planeswalker_and_reduce_loyalty(), test_unblocked_damage_to_removed_planeswalker_disappears(), test_attack_can_target_planeswalker_and_reduce_loyalty(), test_planeswalker_loyalty_ability_appears_in_legal_moves(), test_planeswalker_x_loyalty_ability_requires_x_value_and_materializes()

### Community 66 - "Community 66"
Cohesion: 0.28
Nodes (3): draw_card(), draw_cards(), draw_card()

### Community 67 - "Community 67"
Cohesion: 0.36
Nodes (7): _is_main_phase_window(), main(), parse_args(), _step_key(), summarize_card_play_logic(), _games_jsonl(), test_card_play_analytics_separates_meaningful_main_phase_passes()

### Community 68 - "Community 68"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 69 - "Community 69"
Cohesion: 0.25
Nodes (8): _place_searched_card(), put_green_creature_from_hand(), return_creature_from_graveyard_to_battlefield(), return_permanent_from_graveyard_to_battlefield(), search_library(), topdeck_put_creatures_battlefield(), topdeck_put_permanents_battlefield(), assign_static_order_on_battlefield_entry()

### Community 70 - "Community 70"
Cohesion: 0.43
Nodes (5): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones(), test_sideboard_swap_moves_cards_between_zones()

### Community 71 - "Community 71"
Cohesion: 0.29
Nodes (7): _deal_unblocked_damage(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), consume_player_prevention_shield(), apply_damage_replacements()

### Community 72 - "Community 72"
Cohesion: 0.52
Nodes (6): _state(), test_continuous_layer_trace_includes_ordered_applied_layers(), test_continuous_layer_trace_orders_base_pt_setters_by_static_order(), test_continuous_layer_trace_reports_ordered_sources(), test_continuous_layer_trace_uses_battlefield_order_as_tiebreak(), test_continuous_uses_static_order_for_grant_remove()

### Community 73 - "Community 73"
Cohesion: 0.29
Nodes (7): _counter_pt_delta(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card.

### Community 74 - "Community 74"
Cohesion: 0.43
Nodes (7): AI, Card Data, Current Features, Gameplay, Simulation and Diagnostics, UI, What It Does

### Community 75 - "Community 75"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 76 - "Community 76"
Cohesion: 0.53
Nodes (5): _human_priority_pause(), _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

### Community 77 - "Community 77"
Cohesion: 0.4
Nodes (4): profile_for(), test_matchup_profile_pushes_combo_lite_to_proactive_conversion_against_control(), test_matchup_profile_pushes_control_to_hold_up_against_aggro(), test_matchup_profile_pushes_tempo_to_be_more_proactive_against_control()

### Community 78 - "Community 78"
Cohesion: 0.6
Nodes (4): prevent_damage(), prevent_damage(), add_card_prevention_shield(), add_player_prevention_shield()

### Community 82 - "Community 82"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 84 - "Community 84"
Cohesion: 0.67
Nodes (3): Anthem-like buffs must not permanently modify card.power/toughness., Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats()

### Community 85 - "Community 85"
Cohesion: 0.67
Nodes (3): Architecture, Backend Layers, Layers

### Community 86 - "Community 86"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

## Knowledge Gaps
- **258 isolated node(s):** `Report cached metadata and asset gaps for a deck's distinct card names.`, `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Resolve simulated abilities only when the opponent has no response.`, `Push control decks to convert resources instead of over-passing in developed boa`, `Run a seeded match while preserving each game's independent replay seed.` (+253 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 1` to `Community 0`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 11`, `Community 21`, `Community 23`, `Community 24`, `Community 30`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 42`, `Community 44`, `Community 52`, `Community 65`, `Community 76`?**
  _High betweenness centrality (0.149) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 0` to `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 10`, `Community 11`, `Community 16`, `Community 17`, `Community 20`, `Community 23`, `Community 30`, `Community 32`, `Community 36`, `Community 38`, `Community 39`, `Community 42`, `Community 43`, `Community 46`, `Community 48`, `Community 65`, `Community 66`, `Community 76`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 10` to `Community 0`, `Community 65`, `Community 66`, `Community 3`, `Community 32`, `Community 38`, `Community 39`, `Community 7`, `Community 43`, `Community 12`, `Community 76`, `Community 11`, `Community 46`, `Community 48`, `Community 16`, `Community 29`, `Community 30`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 139 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 139 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 129 inferred relationships involving `str` (e.g. with `_controller_snapshot()` and `_restore_active_matches()`) actually correct?**
  _`str` has 129 INFERRED edges - model-reasoned connections that need verification._
- **Are the 127 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 127 INFERRED edges - model-reasoned connections that need verification._