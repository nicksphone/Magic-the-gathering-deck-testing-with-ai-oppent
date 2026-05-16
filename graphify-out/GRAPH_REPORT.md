# Graph Report - mtg-deck-testing-lab  (2026-05-16)

## Corpus Check
- 110 files · ~292,686 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 963 nodes · 2780 edges · 49 communities (47 shown, 2 thin omitted)
- Extraction: 47% EXTRACTED · 53% INFERRED · 0% AMBIGUOUS · INFERRED: 1474 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `866df305`
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
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 31|Community 31]]

## God Nodes (most connected - your core abstractions)
1. `from_decks()` - 143 edges
2. `from_decks()` - 136 edges
3. `AIAgent` - 87 edges
4. `RulesEngine` - 82 edges
5. `AIAgent` - 79 edges
6. `RulesEngine` - 79 edges
7. `Repository` - 48 edges
8. `DeckService` - 45 edges
9. `AnalyticsService` - 41 edges
10. `legal_moves()` - 38 edges

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

## Communities (49 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (92): combat_damage(), declare_attackers(), declare_blockers(), init_db(), prevent_damage(), RulesEngine, from_decks(), prevent_damage() (+84 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (43): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIAgent, AIDecision, _card_looks_like_land(), _step_key() (+35 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (68): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged() (+60 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (44): build_cast_hints(), enrich_divide_total(), validate_cast_choice(), apply_additional_costs(), check_cost_option_available(), collect_cost_options(), CostOption, _first_discardable_card() (+36 more)

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (43): topdeck_put_creatures_battlefield(), apply_cost_modifiers(), apply_replacement_effects(), CostContext, ReplacementContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost() (+35 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (41): CardInstance, PlayerState, _extract_keywords_from_text(), extract_loyalty_abilities(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle() (+33 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (34): ai_diagnostics(), analytics_history(), apply_sideboard(), autoplay_tick(), _card_looks_like_land(), _default_player_for_state(), _ensure_builtin_decks(), _ensure_expansion_top_decks() (+26 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (11): card_color_names(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), _creature_is_lethally_damaged(), deal_damage(), deal_damage_multi() (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.24
Nodes (32): ActionRequest, BulkSyncRequest, DeckImportRequest, MatchController, PriorityStopsRequest, set_priority_stops(), SideboardRequest, StartMatchRequest (+24 more)

### Community 9 - "Community 9"
Cohesion: 0.1
Nodes (20): get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), list_expansion_top_decks(), sync_cards_bulk(), ai_diagnostics() (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (30): API Summary, Architecture Overview, Backend, code:text (mtg-deck-testing-lab/), code:bash (cd /home/nick/mtg-deck-testing-lab/backend), code:bash (cd /home/nick/mtg-deck-testing-lab/frontend), code:bash (curl -X POST "http://127.0.0.1:8000/cards/sync?name=Lightnin), code:text (4 Lightning Bolt) (+22 more)

### Community 11 - "Community 11"
Cohesion: 0.1
Nodes (23): classify(), main(), compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main(), now_utc() (+15 more)

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (25): resolve_effect(), gain_life(), resolve_effect(), Zone, Anthem-like buffs must not permanently modify card.power/toughness., test_continuous_buff_does_not_mutate_base_stats(), Sub-lethal damage should not kill the creature., Multiple damage instances should accumulate and kill. (+17 more)

### Community 13 - "Community 13"
Cohesion: 0.1
Nodes (17): groupBattlefield(), inferLandColor(), resolveCardMediaUrl(), Battlefield(), groupBattlefield(), HoverPreview, inferLandColor(), LandPile (+9 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (11): get_repo(), analytics_history(), get_repo(), _post_step_finalize(), take_action(), CardCache, DeckRecord, MatchRecord (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.15
Nodes (21): destroy_permanent(), sacrifice(), topdeck_put_creatures_battlefield(), emit_event(), _order_apnap(), StackItem, destroy_permanent(), sacrifice() (+13 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (14): draw_cards(), gain_life(), draw_card(), draw_cards(), apply_damage_replacements(), replace_draw_cards(), replace_gain_life(), _auto_bottom_cards() (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.16
Nodes (16): create_token(), Enum, _infer_keywords(), _infer_loyalty(), _infer_power(), _infer_toughness(), _infer_types(), Zone (+8 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (16): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #1 — Damage doesn't destroy creatures (FIXED), #2 — Summoning sickness cleared at wrong time (FIXED), #3 — Turn advancement skips phases (CRITICAL) (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.26
Nodes (6): DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 21 - "Community 21"
Cohesion: 0.27
Nodes (4): sync_card(), _hydrate_deck_cards(), sync_card(), ScryfallSyncService

### Community 22 - "Community 22"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.33
Nodes (9): _collect_triggers(), _first_number(), _maybe_payload(), _trigger_from_oracle(), _collect_triggers(), _first_number(), _maybe_payload(), _order_apnap() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.28
Nodes (5): list_cards(), suggest_card(), list_cards(), suggest_card(), CardService

### Community 26 - "Community 26"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 27 - "Community 27"
Cohesion: 0.38
Nodes (5): apply_sideboard(), apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones()

### Community 28 - "Community 28"
Cohesion: 0.6
Nodes (4): _human_priority_pause(), _human_priority_pause(), test_human_priority_pause_always_stops_for_land_drop_window(), test_human_priority_pause_respects_configured_step_stops()

## Knowledge Gaps
- **60 isolated node(s):** `Bug #8: resolve_effect should gracefully handle non-dict payloads.`, `Return destination zone for a dying creature: 'graveyard' or 'exile'.`, `Return PT bonus from +1/+1 and -1/-1 counters on a card.`, `Props`, `HoverPreview` (+55 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `from_decks()` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 11`, `Community 12`, `Community 15`, `Community 16`, `Community 17`, `Community 28`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 11`, `Community 12`, `Community 15`, `Community 16`, `Community 17`, `Community 28`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 0` to `Community 1`, `Community 3`, `Community 8`, `Community 11`, `Community 12`, `Community 16`, `Community 17`, `Community 28`, `Community 29`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `main()` and `_build_match()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `main()` and `_build_match()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 71 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 71 INFERRED edges - model-reasoned connections that need verification._