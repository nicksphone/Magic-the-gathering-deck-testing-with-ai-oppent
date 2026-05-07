# Graph Report - mtg-deck-testing-lab  (2026-05-07)

## Corpus Check
- 104 files · ~291,217 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 650 nodes · 1645 edges · 14 communities detected
- Extraction: 50% EXTRACTED · 50% INFERRED · 0% AMBIGUOUS · INFERRED: 830 edges (avg confidence: 0.75)
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
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]

## God Nodes (most connected - your core abstractions)
1. `from_decks()` - 143 edges
2. `RulesEngine` - 79 edges
3. `AIAgent` - 78 edges
4. `Repository` - 38 edges
5. `legal_moves()` - 35 edges
6. `DeckService` - 29 edges
7. `AnalyticsService` - 27 edges
8. `_setup_creature()` - 24 edges
9. `MatchController` - 22 edges
10. `can_pay_with_pool_and_lands()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `test_ossification_is_inferred_as_enchantment_not_sorcery()` --calls--> `from_decks()`  [INFERRED]
  backend/tests/test_legendary_and_types_regression.py → backend/game_state/state.py
- `Zone` --uses--> `Return PT bonus from +1/+1 and -1/-1 counters on a card.`  [INFERRED]
  backend/game_state/state.py → backend/rules_engine/continuous.py
- `declare_blockers()` --calls--> `card_cant_block()`  [INFERRED]
  backend/rules_engine/combat.py → backend/rules_engine/restrictions.py
- `declare_blockers()` --calls--> `card_must_block_if_able()`  [INFERRED]
  backend/rules_engine/combat.py → backend/rules_engine/restrictions.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (66): classify(), main(), init_db(), compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main() (+58 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (58): build_cast_hints(), validate_cast_choice(), apply_additional_costs(), check_cost_option_available(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature() (+50 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (44): card_color_names(), _deal_unblocked_damage(), _mark_creature_damage(), _collect_triggers(), emit_event(), _first_number(), _maybe_payload(), _order_apnap() (+36 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (34): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), str, test_aggro_ai_prefers_creature_development_over_burn_early(), test_ai_assigns_two_blockers_against_menace_attacker(), test_ai_attack_selection_avoids_suicidal_one_one_into_bigger_board() (+26 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (53): combat_damage(), declare_blockers(), Enum, resolve_effect(), from_decks(), _infer_keywords(), _infer_loyalty(), _infer_power() (+45 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (34): BaseModel, Exception, ActionRequest, ai_diagnostics(), analytics_history(), BulkSyncRequest, DeckImportRequest, PriorityStopsRequest (+26 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (30): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), declare_attackers(), _defender_label(), _max_attackers_blockable_by_creature() (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (27): apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands() (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (25): enrich_divide_total(), _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle(), _infer_topdeck_creature_put_effect(), inspect_target_hints() (+17 more)

### Community 9 - "Community 9"
Cohesion: 0.19
Nodes (22): _all_battlefield_ids(), _continuous_pt_delta(), _counter_pt_delta(), effective_keywords(), effective_power(), effective_toughness(), _has_subtype(), _is_battlefield() (+14 more)

### Community 10 - "Community 10"
Cohesion: 0.18
Nodes (12): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _apply_attachment_state_checks(), _apply_legend_rule(), apply_state_based_actions(), _is_legendary() (+4 more)

### Community 11 - "Community 11"
Cohesion: 0.26
Nodes (6): DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 13 - "Community 13"
Cohesion: 0.53
Nodes (5): _human_priority_pause(), _build_match(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops(), test_set_priority_stops_updates_match_state()

### Community 14 - "Community 14"
Cohesion: 0.5
Nodes (2): groupBattlefield(), inferLandColor()

## Knowledge Gaps
- **Thin community `Community 14`** (5 nodes): `Battlefield()`, `groupBattlefield()`, `inferLandColor()`, `manaSummary()`, `Battlefield.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `from_decks()` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.291) - this node is a cross-community bridge._
- **Why does `AIAgent` connect `Community 3` to `Community 0`, `Community 1`, `Community 4`, `Community 5`, `Community 13`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 9`, `Community 13`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `start_match()` and `_start_next_game_state()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 68 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 68 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `Repository` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`Repository` has 27 INFERRED edges - model-reasoned connections that need verification._