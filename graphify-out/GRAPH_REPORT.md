# Graph Report - mtg-deck-testing-lab  (2026-05-15)

## Corpus Check
- 109 files · ~291,447 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 830 nodes · 2193 edges · 52 communities (50 shown, 2 thin omitted)
- Extraction: 49% EXTRACTED · 51% INFERRED · 0% AMBIGUOUS · INFERRED: 1121 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `673c9f17`
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
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `from_decks()` - 143 edges
2. `AIAgent` - 87 edges
3. `RulesEngine` - 79 edges
4. `RulesEngine` - 74 edges
5. `Repository` - 47 edges
6. `DeckService` - 45 edges
7. `AnalyticsService` - 38 edges
8. `legal_moves()` - 38 edges
9. `ScryfallSyncService` - 29 edges
10. `Step` - 26 edges

## Surprising Connections (you probably didn't know these)
- `simulate_batch()` --calls--> `AnalyticsService`  [INFERRED]
  backend/main.py → backend/analytics/service.py
- `analytics_history()` --calls--> `AnalyticsService`  [INFERRED]
  backend/main.py → backend/analytics/service.py
- `deal_damage()` --calls--> `apply_damage_replacements()`  [INFERRED]
  backend/effects/handlers.py → backend/rules_engine/replacement.py
- `test_ward_tax_blocks_underpaid_targeted_spell()` --calls--> `RulesEngine`  [INFERRED]
  backend/tests/test_new_rules_batch.py → backend/rules_engine/engine.py
- `test_timing_restriction_first_main_phase_only()` --calls--> `RulesEngine`  [INFERRED]
  backend/tests/test_new_rules_batch.py → backend/rules_engine/engine.py

## Communities (52 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (33): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), evaluate_board(), str, test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_assigns_two_blockers_against_menace_attacker() (+25 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (54): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), combat_damage(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), _deal_unblocked_damage(), declare_attackers() (+46 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (45): topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost() (+37 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (29): _mark_creature_damage(), _collect_triggers(), emit_event(), _first_number(), _maybe_payload(), _order_apnap(), _trigger_from_oracle(), create_token() (+21 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (36): ai_diagnostics(), analytics_history(), apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _ensure_builtin_decks(), _ensure_expansion_top_decks(), _force_ai_land_action() (+28 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (35): attach_if_legal(), attached_to(), is_aura(), is_equipment(), card_color_names(), _all_battlefield_ids(), _continuous_pt_delta(), _counter_pt_delta() (+27 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (36): build_cast_hints(), enrich_divide_total(), validate_cast_choice(), _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle() (+28 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (33): resolve_effect(), draw_cards(), gain_life(), resolve_effect(), apply_damage_replacements(), replace_draw_cards(), replace_gain_life(), add_to_stack() (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (21): classify(), main(), compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main(), now_utc() (+13 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (30): API Summary, Architecture Overview, Backend, code:text (mtg-deck-testing-lab/), code:bash (cd /home/nick/mtg-deck-testing-lab/backend), code:bash (cd /home/nick/mtg-deck-testing-lab/frontend), code:bash (curl -X POST "http://127.0.0.1:8000/cards/sync?name=Lightnin), code:text (4 Lightning Bolt) (+22 more)

### Community 10 - "Community 10"
Cohesion: 0.24
Nodes (26): ActionRequest, BulkSyncRequest, DeckImportRequest, PriorityStopsRequest, SideboardRequest, StartMatchRequest, BaseModel, Exception (+18 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (20): get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_expansion_top_decks(), sync_cards_bulk(), ai_diagnostics() (+12 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (9): get_repo(), analytics_history(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, Repository (+1 more)

### Community 13 - "Community 13"
Cohesion: 0.26
Nodes (19): autoplay_tick(), _human_priority_pause(), MatchController, _post_step_finalize(), take_action(), init_db(), autoplay_tick(), _human_priority_pause() (+11 more)

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (8): RulesEngine, compute_max_land_plays_this_turn(), draw_card(), test_cleanup_discards_down_to_seven_by_default(), test_cleanup_keeps_over_seven_with_no_max_hand_size_effect(), test_combat_damage_reduces_life(), test_summoning_sickness_cleared_only_for_old_creatures(), test_summoning_sickness_kept_for_creature_entering_this_turn()

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (14): extract_loyalty_abilities(), test_discard_additional_cost_is_paid(), test_cannot_target_creature_with_protection_from_source_color(), test_invalid_x_target_choice_does_not_spend_mana(), test_land_named_card_cannot_be_cast_as_spell(), test_engine_upkeep_start_enqueues_begin_step_triggers(), test_engine_rejects_play_land_when_player_is_not_active(), test_cast_spell_rejects_if_cost_unpaid() (+6 more)

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (7): RulesEngine, test_cast_uses_available_alternate_cost_when_no_cost_choice_provided(), test_ai_prefers_attack_on_open_board(), test_attack_can_target_planeswalker_and_reduce_loyalty(), test_planeswalker_loyalty_ability_appears_in_legal_moves(), test_pregame_priority_passes_to_other_player_after_keep(), test_cast_only_during_your_turn_restriction_and_move_hint()

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (15): Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), MatchState, PlayerState (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.19
Nodes (14): _can_cast_spell(), _has_any_target_options(), _is_land_card(), legal_moves(), test_attack_is_declared_once_per_combat_step(), test_additional_land_effect_text_allows_second_land_same_turn(), test_generates_basic_legal_moves(), test_land_named_card_is_not_offered_as_cast_spell_even_if_mistyped() (+6 more)

### Community 19 - "Community 19"
Cohesion: 0.14
Nodes (12): _auto_bottom_cards(), _infer_mana_from_land(), _is_land_card(), pass_priority(), can_cast_in_current_timing(), check_cost_option_available(), normalize_cost_choice(), _auto_bottom_cards() (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (16): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #1 — Damage doesn't destroy creatures (FIXED), #2 — Summoning sickness cleared at wrong time (FIXED), #3 — Turn advancement skips phases (CRITICAL) (+8 more)

### Community 21 - "Community 21"
Cohesion: 0.2
Nodes (5): sync_card(), apply_sideboard(), _hydrate_deck_cards(), sync_card(), ScryfallSyncService

### Community 22 - "Community 22"
Cohesion: 0.21
Nodes (14): apply_additional_costs(), check_cost_option_available(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice() (+6 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (6): list_cards(), suggest_card(), list_cards(), suggest_card(), fuzzy_card_lookup(), CardService

### Community 26 - "Community 26"
Cohesion: 0.33
Nodes (5): DeckParser, ParsedDeck, FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 27 - "Community 27"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 29 - "Community 29"
Cohesion: 0.47
Nodes (4): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones()

## Knowledge Gaps
- **52 isolated node(s):** `Bug #8: resolve_effect should gracefully handle non-dict payloads.`, `Symptoms`, `Root Cause`, `Files Changed`, `code:block1 (Before: 5/5 games timeout at 6000 ticks)` (+47 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `from_decks()` connect `Community 1` to `Community 0`, `Community 32`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 13`, `Community 14`, `Community 15`, `Community 16`, `Community 17`, `Community 18`?**
  _High betweenness centrality (0.209) - this node is a cross-community bridge._
- **Why does `AIAgent` connect `Community 0` to `Community 2`, `Community 4`, `Community 8`, `Community 10`, `Community 13`, `Community 14`, `Community 16`, `Community 17`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 14` to `Community 0`, `Community 1`, `Community 32`, `Community 5`, `Community 7`, `Community 8`, `Community 10`, `Community 13`, `Community 15`, `Community 16`, `Community 17`, `Community 18`, `Community 19`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `main()` and `run()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 68 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 68 INFERRED edges - model-reasoned connections that need verification._
- **Are the 63 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 63 INFERRED edges - model-reasoned connections that need verification._