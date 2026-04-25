# Graph Report - mtg-deck-testing-lab  (2026-04-25)

## Corpus Check
- 87 files · ~189,439 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 433 nodes · 959 edges · 13 communities detected
- Extraction: 52% EXTRACTED · 48% INFERRED · 0% AMBIGUOUS · INFERRED: 462 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

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
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]

## God Nodes (most connected - your core abstractions)
1. `from_decks()` - 70 edges
2. `AIAgent` - 53 edges
3. `RulesEngine` - 45 edges
4. `Repository` - 31 edges
5. `AnalyticsService` - 26 edges
6. `DeckService` - 20 edges
7. `ScryfallSyncService` - 19 edges
8. `legal_moves()` - 19 edges
9. `MatchController` - 16 edges
10. `can_pay_with_pool_and_lands()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `draw_cards()` --calls--> `draw_card()`  [INFERRED]
  backend/effects/handlers.py → backend/game_state/state.py
- `test_ossification_is_inferred_as_enchantment_not_sorcery()` --calls--> `from_decks()`  [INFERRED]
  backend/tests/test_legendary_and_types_regression.py → backend/game_state/state.py
- `MatchController` --uses--> `AIAgent`  [INFERRED]
  backend/main.py → backend/ai/agent.py
- `MatchController` --uses--> `AnalyticsService`  [INFERRED]
  backend/main.py → backend/analytics/service.py
- `MatchController` --uses--> `ScryfallSyncService`  [INFERRED]
  backend/main.py → backend/card_data/sync.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (44): BaseModel, init_db(), Exception, ActionRequest, autoplay_tick(), BulkSyncRequest, DeckImportRequest, _default_player_for_state() (+36 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (33): build_cast_hints(), apply_additional_costs(), check_cost_option_available(), collect_cost_options(), _first_discardable_card(), _first_sacrificable_creature(), _join_costs(), normalize_cost_choice() (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (43): enrich_divide_total(), CostOption, Enum, create_token(), _extract_keywords_from_text(), extract_loyalty_abilities(), _extract_modes(), _first_creature() (+35 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (20): _collect_triggers(), emit_event(), _first_number(), _order_apnap(), _trigger_from_oracle(), deal_damage(), deal_damage_multi(), destroy_permanent() (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (17): AIAgent, AIDecision, test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_avoids_mana_tap_loop_when_no_cast_available(), test_ai_forces_land_drop_on_own_main_phase(), test_ai_materialize_sets_default_cost_choice_when_options_present(), test_ai_materializes_x_value_for_x_spells(), test_ai_prefers_blue_source_for_counterspell_setup() (+9 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (10): guess_archetype(), ai_diagnostics(), analytics_history(), simulate_batch(), start_match(), AnalyticsService, FakeRepo, test_ai_diagnostics_reports_matchup_metrics() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (21): apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands(), count_untapped_lands_by_color() (+13 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (12): _ensure_builtin_decks(), import_deck(), import_deck_file(), list_decks(), sync_cards_bulk(), DeckParser, ParsedDeck, fuzzy_card_lookup() (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (11): fallback_card_payload(), apply_sideboard(), _hydrate_deck_cards(), sync_card(), apply_sideboard_swaps(), _from_counter(), _to_counter(), ScryfallSyncService (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.24
Nodes (13): combat_damage(), _combat_damage_step(), _deal_unblocked_damage(), declare_attackers(), declare_blockers(), _defender_label(), _has_keyword(), _remove_dead_creatures() (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.27
Nodes (7): _apply_legend_rule(), apply_state_based_actions(), _is_legendary(), test_legend_rule_is_per_controller_not_global(), test_legend_rule_moves_duplicate_legendary_to_graveyard(), test_legend_rule_applies_for_offline_named_legendary_permanents(), test_ossification_is_inferred_as_enchantment_not_sorcery()

### Community 12 - "Community 12"
Cohesion: 0.4
Nodes (4): validate_cast_choice(), validate_cast_targets(), test_choose_two_validator(), test_divide_validator()

### Community 13 - "Community 13"
Cohesion: 0.5
Nodes (2): groupBattlefield(), inferLandColor()

## Knowledge Gaps
- **Thin community `Community 13`** (5 nodes): `Battlefield()`, `groupBattlefield()`, `inferLandColor()`, `manaSummary()`, `Battlefield.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `from_decks()` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 9`, `Community 11`?**
  _High betweenness centrality (0.232) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `AIAgent` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 5`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Are the 59 inferred relationships involving `from_decks()` (e.g. with `start_match()` and `_start_next_game_state()`) actually correct?**
  _`from_decks()` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Repository` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`Repository` has 20 INFERRED edges - model-reasoned connections that need verification._