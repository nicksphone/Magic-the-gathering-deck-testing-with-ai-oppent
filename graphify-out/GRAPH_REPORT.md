# Graph Report - mtg-deck-testing-lab  (2026-05-16)

## Corpus Check
- 117 files · ~327,553 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1208 nodes · 3430 edges · 78 communities (71 shown, 7 thin omitted)
- Extraction: 48% EXTRACTED · 52% INFERRED · 0% AMBIGUOUS · INFERRED: 1775 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5ea0832e`
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
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]

## God Nodes (most connected - your core abstractions)
1. `from_decks()` - 143 edges
2. `from_decks()` - 136 edges
3. `AIAgent` - 128 edges
4. `RulesEngine` - 99 edges
5. `AIAgent` - 87 edges
6. `RulesEngine` - 79 edges
7. `Repository` - 51 edges
8. `DeckService` - 49 edges
9. `Repository` - 49 edges
10. `AnalyticsService` - 41 edges

## Surprising Connections (you probably didn't know these)
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `suggest_card()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `deal_damage()` --calls--> `apply_damage_replacements()`  [INFERRED]
  backend/effects/handlers.py → backend/rules_engine/replacement.py
- `destroy_permanent()` --calls--> `emit_event()`  [INFERRED]
  backend/effects/handlers.py → backend/rules_engine/events.py

## Communities (78 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (99): _human_priority_pause(), combat_damage(), declare_blockers(), check_cost_option_available(), RulesEngine, from_decks(), compute_max_land_plays_this_turn(), _human_priority_pause() (+91 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (54): topdeck_put_creatures_battlefield(), topdeck_put_creatures_battlefield(), apply_cost_modifiers(), CostContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands() (+46 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (28): card_color_names(), _deal_unblocked_damage(), _mark_creature_damage(), create_token(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), destroy_permanent() (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (41): ai_diagnostics(), apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _ensure_builtin_decks(), _ensure_expansion_top_decks(), _force_ai_land_action(), get_legal_moves() (+33 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (32): AIAgent, test_aggro_ai_avoids_suicide_attack_into_larger_blocker(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic() (+24 more)

### Community 5 - "Community 5"
Cohesion: 0.21
Nodes (33): ActionRequest, BatchSimulationJobStartResponse, BatchSimulationJobStatusResponse, BulkSyncRequest, DeckImportRequest, PriorityStopsRequest, SideboardRequest, StartMatchRequest (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (22): AIAgent, _card_looks_like_land(), _step_key(), test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_does_not_treat_mana_creature_as_land_in_forced_land_logic(), test_ai_forces_land_drop_even_when_legal_moves_omit_play_land(), test_ai_forces_land_drop_on_own_main_phase() (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (25): api, BatchSimulationJobStart, BatchSimulationJobStatus, DeckImportResponse, ExpansionTopDeckMeta, ExpansionTopDeckPayload, resolveCardMediaUrl(), groupBattlefield() (+17 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (35): build_cast_hints(), CardInstance, _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle(), _infer_topdeck_creature_put_effect() (+27 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (29): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _damage_prevented_by_protection(), declare_attackers(), _defender_label(), _max_attackers_blockable_by_creature(), _minimum_blockers_required() (+21 more)

### Community 10 - "Community 10"
Cohesion: 0.1
Nodes (19): get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_expansion_top_decks(), sync_cards_bulk(), _ensure_builtin_decks() (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (13): CardCache, DeckRecord, MatchRecord, StatsSnapshot, CardCache, DeckRecord, MatchRecord, StatsSnapshot (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.17
Nodes (17): autoplay_tick(), get_repo(), MatchController, init_db(), analytics_history(), autoplay_tick(), get_repo(), MatchController (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.2
Nodes (24): effective_power(), _counter_pt_delta(), effective_power(), effective_toughness(), Return PT bonus from +1/+1 and -1/-1 counters on a card., Return PT bonus from +1/+1 and -1/-1 counters on a card., _setup_creature(), _setup_permanent() (+16 more)

### Community 14 - "Community 14"
Cohesion: 0.2
Nodes (22): _all_battlefield_ids(), _continuous_pt_delta(), effective_keywords(), _has_subtype(), _is_battlefield(), _iter_keyword_grants(), _iter_pt_modifiers(), _scope_controller() (+14 more)

### Community 15 - "Community 15"
Cohesion: 0.16
Nodes (20): resolve_effect(), draw_cards(), gain_life(), resolve_effect(), test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill., Spell damage should kill creatures — state-based lethal check after damage. (+12 more)

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (17): compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main(), now_utc(), parse_args(), fallback_card_payload() (+9 more)

### Community 17 - "Community 17"
Cohesion: 0.16
Nodes (15): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), MatchState, Zone, CostOption (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.13
Nodes (19): _has_any_target_options(), _is_land_card(), card_cant_block(), card_must_block_if_able(), declare_attackers(), _defender_label(), _valid_defenders(), _can_cast_spell() (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.1
Nodes (19): 4) Open UI, Adding Cards, Adding Decks, AI Notes, API Overview, API Summary, Card Data + Image Cache, Contribution/Workflow Rule (+11 more)

### Community 20 - "Community 20"
Cohesion: 0.22
Nodes (15): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _apply_attachment_state_checks(), _apply_legend_rule(), apply_state_based_actions(), _is_legendary() (+7 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (4): evaluate_board(), evaluate_inevitability(), _planeswalker_count(), evaluate_board()

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (16): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #1 — Damage doesn't destroy creatures (FIXED), #2 — Summoning sickness cleared at wrong time (FIXED), #3 — Turn advancement skips phases (CRITICAL) (+8 more)

### Community 23 - "Community 23"
Cohesion: 0.21
Nodes (13): classify(), main(), compact_action(), hand_snapshot(), now_utc(), parse_args(), run(), compact_action() (+5 more)

### Community 25 - "Community 25"
Cohesion: 0.18
Nodes (6): test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board(), test_ai_blocks_with_stronger_creature_to_prevent_damage(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_block_assignments(), test_ai_materializes_x_value_for_x_spells()

### Community 26 - "Community 26"
Cohesion: 0.21
Nodes (13): PlayerState, validate_cast_targets(), validate_hexproof_shroud_targets(), validate_protection_targets(), validate_cast_targets(), validate_protection_targets(), test_choose_two_validator(), test_divide_validator() (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.2
Nodes (5): AnalyticsService, analytics_history(), simulate_batch(), _DummyRepo, test_batch_does_not_auto_award_unresolved_games_to_deck_a()

### Community 28 - "Community 28"
Cohesion: 0.22
Nodes (13): apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice(), apply_additional_costs() (+5 more)

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (13): _remove_dead_creatures(), emit_event(), StackItem, _put_trigger_creature(), test_apnap_trigger_order_on_shared_event(), test_begin_end_step_triggers_only_for_active_player_when_oracle_says_your(), test_begin_upkeep_triggers_apply_apnap_for_each_upkeep_text(), _put_trigger_creature() (+5 more)

### Community 30 - "Community 30"
Cohesion: 0.26
Nodes (6): DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 31 - "Community 31"
Cohesion: 0.35
Nodes (11): StackItem, emit_event(), add_to_stack(), resolve_top_of_stack(), add_to_stack(), resolve_top_of_stack(), _put_static_permanent_with_oracle(), test_sheoldred_opponent_draw_trigger_loses_life() (+3 more)

### Community 33 - "Community 33"
Cohesion: 0.26
Nodes (3): sync_card(), sync_card(), ScryfallSyncService

### Community 34 - "Community 34"
Cohesion: 0.21
Nodes (7): ingest_tournament_json(), tournament_event_summary(), Ingest external tournament event payloads into normalized local tables.      Exp, TournamentIngestService, _sample_payload(), test_ingest_rejects_short_mainboard(), test_ingest_tournament_event_and_summary()

### Community 35 - "Community 35"
Cohesion: 0.21
Nodes (5): AIDecision, AIDecision, _card_looks_like_land(), test_control_ai_mulligan_counts_land_with_missing_types_from_oracle(), test_control_ai_mulligans_land_light_hand()

### Community 37 - "Community 37"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 38 - "Community 38"
Cohesion: 0.29
Nodes (10): _collect_triggers(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), _collect_triggers(), _first_number(), _maybe_payload() (+2 more)

### Community 39 - "Community 39"
Cohesion: 0.18
Nodes (10): draw_cards(), gain_life(), apply_damage_replacements(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), Return destination zone for a dying creature: 'graveyard' or 'exile'., replace_die_zone() (+2 more)

### Community 40 - "Community 40"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 41 - "Community 41"
Cohesion: 0.24
Nodes (6): enrich_divide_total(), validate_cast_choice(), pass_priority(), normalize_cost_choice(), ward_generic_tax(), ward_tax_for_targets()

### Community 42 - "Community 42"
Cohesion: 0.31
Nodes (5): FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), FakeRepo, test_ai_diagnostics_reports_matchup_metrics(), test_scan_log_tracks_stall_and_land_window_anomalies()

### Community 43 - "Community 43"
Cohesion: 0.25
Nodes (8): _auto_bottom_cards(), _infer_mana_from_land(), _is_land_card(), _auto_bottom_cards(), _extract_equip_cost_text(), _infer_mana_from_land(), _is_land_card(), _land_colors_from_metadata()

### Community 44 - "Community 44"
Cohesion: 0.22
Nodes (8): test_replacement_gain_life_to_draw_cards(), Bug #8: resolve_effect should gracefully handle non-dict payloads., Bug #8: resolve_effect should gracefully handle non-dict payloads., test_hexproof_blocks_opponent_targeted_spell(), test_replacement_gain_life_to_draw_cards(), test_resolve_effect_rejects_non_dict_payload(), test_timing_restriction_first_main_phase_only(), test_ward_tax_blocks_underpaid_targeted_spell()

### Community 45 - "Community 45"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 46 - "Community 46"
Cohesion: 0.25
Nodes (9): 2) Backend, 3) Frontend, Backend, code:bash (cd backend), code:bash (cd ../frontend), Frontend, Setup, Storage (+1 more)

### Community 47 - "Community 47"
Cohesion: 0.25
Nodes (8): Backend tests, code:bash (cd backend), code:bash (cd frontend), Expansion Top Deck Catalog, Frontend build check, How to Add Cards, How to Add Decks, Testing

### Community 48 - "Community 48"
Cohesion: 0.29
Nodes (8): code:text (4 Lightning Bolt), code:json ({), code:bash (cd backend), Deck Import Format, Diagnostics and Simulation, Quick matchup debug, Round-robin anomaly scan, Tournament Data Ingest (Training Corpus)

### Community 49 - "Community 49"
Cohesion: 0.29
Nodes (7): AI System, Current Feature Set, Deck Workflows, Diagnostics / Simulation, Gameplay Engine, Oracle/Effect Interpretation, UI Workflows

### Community 50 - "Community 50"
Cohesion: 0.47
Nodes (4): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones()

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (3): start_match(), guess_archetype(), start_match()

### Community 52 - "Community 52"
Cohesion: 0.4
Nodes (5): _creature_is_lethally_damaged(), _counter_pt_delta(), effective_toughness(), Return PT bonus from +1/+1 and -1/-1 counters on a card., card_cant_attack_alone()

### Community 55 - "Community 55"
Cohesion: 0.5
Nodes (3): _infer_types(), _infer_types(), test_control_ramp_name_fallback_types_are_not_misclassified_as_creatures()

### Community 56 - "Community 56"
Cohesion: 0.5
Nodes (4): AI diagnostics, Batch simulation, Overnight verbose runs, Simulator + Diagnostics

### Community 59 - "Community 59"
Cohesion: 0.67
Nodes (3): Current Status (April 26, 2026), Recently stabilized, Working now

### Community 60 - "Community 60"
Cohesion: 0.67
Nodes (3): 1) Clone, code:bash (git clone git@github.com:nicksphone/Magic-the-gathering-deck), Project Structure

## Knowledge Gaps
- **86 isolated node(s):** `Ingest external tournament event payloads into normalized local tables.      Exp`, `Anthem-like buffs must not permanently modify card.power/toughness.`, `+1/+1 and -1/-1 counters should affect effective_power/toughness without mutatin`, `Bug #8: resolve_effect should gracefully handle non-dict payloads.`, `Return destination zone for a dying creature: 'graveyard' or 'exile'.` (+81 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `from_decks()` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 36`, `Community 6`, `Community 8`, `Community 12`, `Community 13`, `Community 44`, `Community 15`, `Community 16`, `Community 17`, `Community 51`, `Community 20`, `Community 55`, `Community 23`, `Community 29`, `Community 31`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `AIAgent` connect `Community 4` to `Community 0`, `Community 35`, `Community 5`, `Community 6`, `Community 12`, `Community 16`, `Community 17`, `Community 51`, `Community 21`, `Community 54`, `Community 23`, `Community 24`, `Community 57`, `Community 27`, `Community 25`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 0` to `Community 1`, `Community 4`, `Community 5`, `Community 6`, `Community 12`, `Community 13`, `Community 16`, `Community 17`, `Community 23`, `Community 27`, `Community 29`, `Community 35`, `Community 36`, `Community 41`, `Community 43`, `Community 44`, `Community 51`, `Community 54`, `Community 57`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `main()` and `_build_match()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `_build_match()` and `test_human_priority_pause_always_stops_for_land_drop_window()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Are the 88 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 88 INFERRED edges - model-reasoned connections that need verification._