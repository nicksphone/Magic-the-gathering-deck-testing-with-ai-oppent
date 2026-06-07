# Graph Report - mtg-deck-testing-lab  (2026-06-07)

## Corpus Check
- 130 files · ~361,411 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1399 nodes · 3958 edges · 85 communities (80 shown, 5 thin omitted)
- Extraction: 50% EXTRACTED · 50% INFERRED · 0% AMBIGUOUS · INFERRED: 1964 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8c0420b4`
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
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]

## God Nodes (most connected - your core abstractions)
1. `AIAgent` - 171 edges
2. `from_decks()` - 143 edges
3. `from_decks()` - 136 edges
4. `RulesEngine` - 106 edges
5. `AIAgent` - 87 edges
6. `RulesEngine` - 79 edges
7. `Repository` - 58 edges
8. `DeckService` - 49 edges
9. `Repository` - 49 edges
10. `CardInstance` - 43 edges

## Surprising Connections (you probably didn't know these)
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `suggest_card()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `deal_damage()` --calls--> `damage_cant_be_prevented()`  [INFERRED]
  backend/effects/handlers.py → backend/rules_engine/replacement.py
- `deal_damage()` --calls--> `apply_damage_replacements()`  [INFERRED]
  backend/effects/handlers.py → backend/rules_engine/replacement.py

## Communities (85 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (128): combat_damage(), declare_blockers(), prevent_damage(), from_decks(), prevent_damage(), apply_cost_modifiers(), CostContext, _apply_generic_delta_to_cost() (+120 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (58): build_cast_hints(), enrich_divide_total(), CardInstance, _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle() (+50 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (40): apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves(), get_match(), _hydrate_deck_cards(), _is_full_ai_match() (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (43): analyze_deck(), guess_archetype(), classify(), main(), analyze_deck_payload(), get_match_replay(), fallback_card_payload(), compact_action() (+35 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (44): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_avoids_casting_x_spells_when_only_x_zero_is_possible(), test_ai_avoids_low_value_secure_the_wastes_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available() (+36 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (36): AnalyticsService, ActionRequest, analytics_history(), BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckAnalyzeRequest, DeckImportRequest (+28 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (26): ai_diagnostics(), _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck() (+18 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (23): AIAgent, _card_looks_like_land(), _step_key(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic(), test_ai_forces_land_drop_even_when_legal_moves_omit_play_land(), test_ai_forces_land_drop_on_own_main_phase() (+15 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (19): get_repo(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, CardCache, DeckRecord (+11 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (25): api, BatchSimulationJobStart, BatchSimulationJobStatus, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload, resolveCardMediaUrl(), groupBattlefield() (+17 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (7): copy_spell(), create_token(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), apply_damage_replacements()

### Community 11 - "Community 11"
Cohesion: 0.1
Nodes (10): AIDecision, AIDecision, _card_looks_like_land(), topdeck_put_creatures_battlefield(), add_generic_to_cost(), parse_mana_cost(), add_generic_to_cost(), parse_mana_cost() (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (29): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), declare_attackers(), _defender_label(), _mark_creature_damage(), _max_attackers_blockable_by_creature() (+21 more)

### Community 13 - "Community 13"
Cohesion: 0.13
Nodes (12): RulesEngine, compute_max_land_plays_this_turn(), test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), Creatures present at untap lose summoning sickness; new ones keep it., A creature entering during a player's own turn keeps summoning sickness until th, test_combat_damage_reduces_life(), test_summoning_sickness_cleared_only_for_old_creatures() (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (26): _combat_damage_step(), _remaining_lethal_damage(), effective_power(), effective_toughness(), _base_pt_with_layers(), effective_power(), effective_toughness(), _setup_creature() (+18 more)

### Community 15 - "Community 15"
Cohesion: 0.16
Nodes (3): _step_key(), should_force_closure(), should_force_inevitability_line()

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (23): resolve_effect(), draw_cards(), gain_life(), resolve_effect(), Zone, Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature. (+15 more)

### Community 17 - "Community 17"
Cohesion: 0.17
Nodes (24): _all_battlefield_ids(), _continuous_pt_delta(), _counter_pt_delta(), effective_keywords(), _has_subtype(), _is_battlefield(), _iter_keyword_grants(), _iter_pt_modifiers() (+16 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (23): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Card Data + Image Cache, Contribution/Workflow Rule (+15 more)

### Community 19 - "Community 19"
Cohesion: 0.23
Nodes (19): autoplay_tick(), _human_priority_pause(), MatchController, _post_step_finalize(), take_action(), init_db(), autoplay_tick(), _human_priority_pause() (+11 more)

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (10): extract_loyalty_abilities(), test_discard_additional_cost_is_paid(), test_cast_uses_available_alternate_cost_when_no_cost_choice_provided(), test_engine_rejects_play_land_when_player_is_not_active(), test_mana_pool_empties_on_step_transition(), test_tap_lands_bulk_adds_mana_and_taps_requested_count(), test_pregame_priority_passes_to_other_player_after_keep(), test_casting_player_retains_priority_for_additional_spell() (+2 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (13): RulesEngine, test_cannot_target_creature_with_protection_from_source_color(), test_invalid_x_target_choice_does_not_spend_mana(), test_land_named_card_cannot_be_cast_as_spell(), test_london_mulligan_flow_completes_pregame(), test_attack_can_target_planeswalker_and_reduce_loyalty(), test_planeswalker_loyalty_ability_appears_in_legal_moves(), test_cast_spell_rejects_if_cost_unpaid() (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.13
Nodes (19): _has_any_target_options(), _is_land_card(), card_cant_block(), card_must_block_if_able(), declare_attackers(), _defender_label(), _valid_defenders(), _can_cast_spell() (+11 more)

### Community 23 - "Community 23"
Cohesion: 0.13
Nodes (17): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState, Zone (+9 more)

### Community 24 - "Community 24"
Cohesion: 0.18
Nodes (16): validate_cast_choice(), PlayerState, validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets(), test_choose_two_validator() (+8 more)

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (16): create_token(), destroy_permanent(), sacrifice(), topdeck_put_creatures_battlefield(), assign_static_order_on_battlefield_entry(), StackItem, emit_event(), add_to_stack() (+8 more)

### Community 26 - "Community 26"
Cohesion: 0.12
Nodes (16): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #1 — Damage doesn't destroy creatures (FIXED), #2 — Summoning sickness cleared at wrong time (FIXED), #3 — Turn advancement skips phases (CRITICAL) (+8 more)

### Community 27 - "Community 27"
Cohesion: 0.19
Nodes (6): Depth-limited stack planner for counter wars; only runs while stack is active., Depth-limited stack planner for counter wars; only runs while stack is active., evaluate_board(), evaluate_inevitability(), _planeswalker_count(), evaluate_board()

### Community 28 - "Community 28"
Cohesion: 0.17
Nodes (5): Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa, Push control decks to convert resources instead of over-passing in developed boa

### Community 29 - "Community 29"
Cohesion: 0.16
Nodes (12): _infer_mana_from_land(), _is_land_card(), pass_priority(), can_cast_in_current_timing(), check_cost_option_available(), normalize_cost_choice(), _extract_equip_cost_text(), _infer_mana_from_land() (+4 more)

### Community 30 - "Community 30"
Cohesion: 0.19
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 31 - "Community 31"
Cohesion: 0.14
Nodes (14): draw_cards(), gain_life(), lose_life(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), damage_cant_be_prevented(), player_cant_gain_life() (+6 more)

### Community 32 - "Community 32"
Cohesion: 0.21
Nodes (14): _collect_triggers(), emit_event(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), destroy_permanent(), sacrifice() (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.18
Nodes (9): build_priors_from_logs(), load_log_priors(), save_log_priors(), profile_for(), get_ai_priors(), rebuild_ai_priors(), main(), _read_training_run_logs() (+1 more)

### Community 34 - "Community 34"
Cohesion: 0.23
Nodes (6): DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 35 - "Community 35"
Cohesion: 0.22
Nodes (13): apply_additional_costs(), check_cost_option_available(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice() (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.26
Nodes (5): sync_card(), ScryfallSyncService, _DummyRepo, test_extract_remote_image_uri_falls_back_to_face_images(), test_extract_remote_image_uri_prefers_root_normal()

### Community 38 - "Community 38"
Cohesion: 0.22
Nodes (9): ensure_placeholder_image(), _family(), _svg_for(), _cache_remote_token_image(), _extract_image_uri(), resolve_token_image_uri(), _search_scryfall_token_image(), test_create_token_assigns_image_uri() (+1 more)

### Community 39 - "Community 39"
Cohesion: 0.21
Nodes (9): _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), apply_replacement_effects(), ReplacementContext, _state(), test_controller_scoped_damage_cant_be_prevented_ignores_shield() (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.21
Nodes (7): ingest_tournament_json(), tournament_event_summary(), Ingest external tournament event payloads into normalized local tables.      Exp, TournamentIngestService, _sample_payload(), test_ingest_rejects_short_mainboard(), test_ingest_tournament_event_and_summary()

### Community 41 - "Community 41"
Cohesion: 0.27
Nodes (10): legal_moves(), test_attack_is_declared_once_per_combat_step(), test_additional_land_effect_text_allows_second_land_same_turn(), test_generates_basic_legal_moves(), test_land_named_card_is_not_offered_as_cast_spell_even_if_mistyped(), test_mana_ability_oracle_marks_land_playable_when_type_metadata_missing(), test_mana_creature_is_not_misclassified_as_land_from_oracle_text(), test_no_second_land_move_same_turn_even_if_land_counter_desynced() (+2 more)

### Community 42 - "Community 42"
Cohesion: 0.29
Nodes (9): _apply_legend_rule(), apply_state_based_actions(), _is_legendary(), _apply_legend_rule(), apply_state_based_actions(), _is_legendary(), test_legend_rule_is_per_controller_not_global(), test_legend_rule_moves_duplicate_legendary_to_graveyard() (+1 more)

### Community 43 - "Community 43"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 44 - "Community 44"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.29
Nodes (6): card_color_names(), protection_match_reason(), _protection_tokens(), protected_from_source(), protection_match_reason(), _protection_tokens()

### Community 47 - "Community 47"
Cohesion: 0.31
Nodes (3): simulate_batch_start(), _infer_toughness(), str

### Community 48 - "Community 48"
Cohesion: 0.31
Nodes (5): FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), test_scan_log_tracks_stall_and_land_window_anomalies()

### Community 49 - "Community 49"
Cohesion: 0.28
Nodes (4): _auto_bottom_cards(), draw_card(), _auto_bottom_cards(), draw_card()

### Community 50 - "Community 50"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 51 - "Community 51"
Cohesion: 0.25
Nodes (9): 2) Backend, 3) Frontend, Backend, code:bash (cd backend), code:bash (cd ../frontend), Frontend, Setup, Storage (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.25
Nodes (7): test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell(), test_hexproof_blocks_opponent_targeted_spell(), test_replacement_gain_life_to_draw_cards(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell()

### Community 53 - "Community 53"
Cohesion: 0.25
Nodes (8): Backend tests, code:bash (cd backend), code:bash (cd frontend), Expansion Top Deck Catalog, Frontend build check, How to Add Cards, How to Add Decks, Testing

### Community 54 - "Community 54"
Cohesion: 0.29
Nodes (8): code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import Format, Diagnostics and Simulation, Quick matchup debug, Round-robin anomaly scan, Tournament Data Ingest (Training Corpus)

### Community 55 - "Community 55"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 56 - "Community 56"
Cohesion: 0.52
Nodes (6): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _apply_attachment_state_checks(), _apply_attachment_state_checks()

### Community 57 - "Community 57"
Cohesion: 0.52
Nodes (6): _put_trigger_creature(), test_apnap_trigger_order_on_shared_event(), test_begin_end_step_triggers_only_for_active_player_when_oracle_says_your(), test_begin_upkeep_triggers_apply_apnap_for_each_upkeep_text(), test_engine_upkeep_start_enqueues_begin_step_triggers(), test_spell_cast_trigger_from_permanent()

### Community 58 - "Community 58"
Cohesion: 0.5
Nodes (5): _deal_unblocked_damage(), consume_player_prevention_shield(), _deal_unblocked_damage(), When an unblocked attacker targets a PW that leaves the battlefield,     the dam, test_unblocked_damage_to_removed_planeswalker_disappears()

### Community 60 - "Community 60"
Cohesion: 0.83
Nodes (3): load_json(), main(), run_cmd()

### Community 61 - "Community 61"
Cohesion: 0.5
Nodes (4): _counter_pt_delta(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card.

### Community 62 - "Community 62"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 65 - "Community 65"
Cohesion: 0.67
Nodes (3): 1) Clone, code:bash (git clone git@github.com:nicksphone/Magic-the-gathering-deck), Project Structure

### Community 66 - "Community 66"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

### Community 67 - "Community 67"
Cohesion: 0.67
Nodes (3): Bug #8: resolve_effect should gracefully handle non-dict payloads., Bug #8: resolve_effect should gracefully handle non-dict payloads., test_resolve_effect_rejects_non_dict_payload()

## Knowledge Gaps
- **99 isolated node(s):** `Depth-limited stack planner for counter wars; only runs while stack is active.`, `Push control decks to convert resources instead of over-passing in developed boa`, `Ingest external tournament event payloads into normalized local tables.      Exp`, `Anthem-like buffs must not permanently modify card.power/toughness.`, `+1/+1 and -1/-1 counters should affect effective_power/toughness without mutatin` (+94 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIAgent` connect `Community 4` to `Community 33`, `Community 2`, `Community 3`, `Community 5`, `Community 7`, `Community 11`, `Community 15`, `Community 47`, `Community 19`, `Community 21`, `Community 23`, `Community 27`, `Community 28`, `Community 30`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 21` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 11`, `Community 13`, `Community 14`, `Community 16`, `Community 19`, `Community 20`, `Community 23`, `Community 29`, `Community 33`, `Community 41`, `Community 49`, `Community 52`, `Community 57`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 0` to `Community 1`, `Community 3`, `Community 7`, `Community 41`, `Community 42`, `Community 13`, `Community 14`, `Community 47`, `Community 16`, `Community 49`, `Community 19`, `Community 20`, `Community 21`, `Community 23`, `Community 24`, `Community 25`, `Community 58`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 100 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 95 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 95 INFERRED edges - model-reasoned connections that need verification._