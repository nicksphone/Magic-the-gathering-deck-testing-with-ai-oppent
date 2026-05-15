# Graph Report - mtg-deck-testing-lab  (2026-05-15)

## Corpus Check
- 109 files · ~292,447 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 959 nodes · 2773 edges · 48 communities (45 shown, 3 thin omitted)
- Extraction: 47% EXTRACTED · 53% INFERRED · 0% AMBIGUOUS · INFERRED: 1470 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f301506d`
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
4. `RulesEngine` - 81 edges
5. `RulesEngine` - 79 edges
6. `AIAgent` - 78 edges
7. `Repository` - 48 edges
8. `DeckService` - 45 edges
9. `AnalyticsService` - 41 edges
10. `legal_moves()` - 38 edges

## Surprising Connections (you probably didn't know these)
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `suggest_card()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py
- `simulate_batch()` --calls--> `AnalyticsService`  [INFERRED]
  backend/main.py → backend/analytics/service.py
- `analytics_history()` --calls--> `AnalyticsService`  [INFERRED]
  backend/main.py → backend/analytics/service.py
- `list_cards()` --calls--> `CardService`  [INFERRED]
  backend/main.py → backend/card_data/service.py

## Communities (48 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (105): combat_damage(), declare_blockers(), check_cost_option_available(), resolve_effect(), _auto_bottom_cards(), RulesEngine, from_decks(), draw_cards() (+97 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (42): AIAgent, AIDecision, _card_looks_like_land(), _step_key(), AIAgent, AIDecision, _card_looks_like_land(), _step_key() (+34 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (66): _attacker_has_active_landwalk_with_state(), _can_block_attacker(), _combat_damage_step(), _creature_is_lethally_damaged(), _damage_prevented_by_protection(), declare_attackers(), _defender_label(), _max_attackers_blockable_by_creature() (+58 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (49): enrich_divide_total(), validate_cast_choice(), apply_additional_costs(), collect_cost_options(), CostOption, _first_discardable_card(), _first_sacrificable_creature(), _join_costs() (+41 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (38): ai_diagnostics(), analytics_history(), apply_sideboard(), _card_looks_like_land(), _default_player_for_state(), _force_ai_land_action(), get_legal_moves(), get_match() (+30 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (41): topdeck_put_creatures_battlefield(), apply_cost_modifiers(), CostContext, add_generic_to_cost(), _apply_generic_delta_to_cost(), auto_pay_cost(), can_pay_with_pool_and_lands(), count_untapped_lands_by_color() (+33 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (30): ActionRequest, BulkSyncRequest, DeckImportRequest, PriorityStopsRequest, SideboardRequest, StartMatchRequest, BaseModel, Exception (+22 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (34): build_cast_hints(), CardInstance, _extract_keywords_from_text(), _extract_modes(), _first_creature(), _infer_clause_effect(), infer_effect_from_oracle(), _infer_topdeck_creature_put_effect() (+26 more)

### Community 8 - "Community 8"
Cohesion: 0.1
Nodes (24): _ensure_builtin_decks(), _ensure_expansion_top_decks(), get_expansion_top_deck(), import_all_expansion_top_decks(), import_deck(), import_deck_file(), import_expansion_top_deck(), lifespan() (+16 more)

### Community 9 - "Community 9"
Cohesion: 0.1
Nodes (23): classify(), main(), compact_action(), hand_snapshot(), hydrate_deck(), load_named_deck(), main(), now_utc() (+15 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (30): API Summary, Architecture Overview, Backend, code:text (mtg-deck-testing-lab/), code:bash (cd /home/nick/mtg-deck-testing-lab/backend), code:bash (cd /home/nick/mtg-deck-testing-lab/frontend), code:bash (curl -X POST "http://127.0.0.1:8000/cards/sync?name=Lightnin), code:text (4 Lightning Bolt) (+22 more)

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (17): groupBattlefield(), inferLandColor(), resolveCardMediaUrl(), Battlefield(), groupBattlefield(), HoverPreview, inferLandColor(), LandPile (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.15
Nodes (19): card_color_names(), _deal_unblocked_damage(), _mark_creature_damage(), deal_damage(), deal_damage_multi(), _move_creature_to_graveyard(), prevent_damage(), _creature_is_lethally_damaged() (+11 more)

### Community 14 - "Community 14"
Cohesion: 0.16
Nodes (16): attach_if_legal(), attached_to(), is_aura(), is_equipment(), _apply_attachment_state_checks(), _apply_legend_rule(), apply_state_based_actions(), _is_legendary() (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.15
Nodes (9): get_repo(), analytics_history(), get_repo(), CardCache, DeckRecord, MatchRecord, StatsSnapshot, Repository (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.33
Nodes (16): autoplay_tick(), _human_priority_pause(), MatchController, init_db(), autoplay_tick(), _human_priority_pause(), MatchController, test_autoplay_advances_to_next_game_for_full_ai_match() (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (16): #10 — `destroy_permanent` doesn't clear damage counters (LOW), #11 — `on_event("startup")` deprecated (LOW), #12 — No rate limiting on Scryfall API (LOW), #13 — `mana_pool[color]` can go negative (MEDIUM), #14 — AI not playing lands / blocking with mana creatures (FIXED), #1 — Damage doesn't destroy creatures (FIXED), #2 — Summoning sickness cleared at wrong time (FIXED), #3 — Turn advancement skips phases (CRITICAL) (+8 more)

### Community 18 - "Community 18"
Cohesion: 0.19
Nodes (14): destroy_permanent(), sacrifice(), topdeck_put_creatures_battlefield(), StackItem, emit_event(), _order_apnap(), add_to_stack(), resolve_top_of_stack() (+6 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (11): draw_cards(), gain_life(), draw_card(), apply_damage_replacements(), replace_draw_cards(), replace_gain_life(), apply_damage_replacements(), Return destination zone for a dying creature: 'graveyard' or 'exile'. (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.24
Nodes (4): sync_card(), _hydrate_deck_cards(), sync_card(), ScryfallSyncService

### Community 21 - "Community 21"
Cohesion: 0.26
Nodes (6): DeckParser, ParsedDeck, fuzzy_card_lookup(), FakeRepo, test_parse_minimum_deck_and_suggestions(), test_parse_unknown_card_suggests()

### Community 23 - "Community 23"
Cohesion: 0.17
Nodes (11): ✅ Bug #1 — `exile_from` crashes with KeyError for exiled cards (Critical), ✅ Bug #2 — `combat_damage` crashes on tapped blockers (Critical), ✅ Bug #3 — `destroy_target` crashes with `None` on non-existent targets (Critical), ✅ Bug #4 — `resolve_effect` crashes on unknown effect type (Critical), ✅ Bug #5 — `resolve_effect` crashes on payload KeyError (Critical), ✅ Bug #6 — SBA doesn't check lethal damage on tokens (Medium), ✅ Bug #7 — `continuous_buff` permanently modifies base stats (Medium), ✅ Bug #8 — `resolve_effect` crashes on payload TypeError (Low) (+3 more)

### Community 24 - "Community 24"
Cohesion: 0.18
Nodes (10): code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":2,"turn":2,"step":"Step.PRECOMB), code:text (AI TRACE {"trace":true,"pid":1,"turn":2,"step":"Step.PRECOMB), Cross-Game Strategy Signals, Dimir Control vs Ramp: Cost-Failure + Strategy Analysis (10 Games), Failure 1: Game 4, Turn 2, Actor P2, Failure 2: Game 5, Turn 2, Actor P2 (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.39
Nodes (8): _collect_triggers(), _first_number(), _maybe_payload(), _trigger_from_oracle(), _collect_triggers(), _first_number(), _maybe_payload(), _trigger_from_oracle()

### Community 26 - "Community 26"
Cohesion: 0.36
Nodes (8): emit_event(), _order_apnap(), destroy_permanent(), sacrifice(), _put_trigger_creature(), test_apnap_trigger_order_on_shared_event(), test_begin_end_step_triggers_only_for_active_player_when_oracle_says_your(), test_begin_upkeep_triggers_apply_apnap_for_each_upkeep_text()

### Community 27 - "Community 27"
Cohesion: 0.22
Nodes (8): Bug #1: AI Agent Plays Invalid Land Actions (Infinite Stall Loop), code:block1 (Before: 5/5 games timeout at 6000 ticks), Files Changed, Lessons Learned, MTG Deck Testing Lab — Known Bugs & Fixes, Root Cause, Symptoms, Verification

### Community 28 - "Community 28"
Cohesion: 0.47
Nodes (4): apply_sideboard_swaps(), _from_counter(), _to_counter(), test_sideboard_swap_moves_cards_between_zones()

## Knowledge Gaps
- **60 isolated node(s):** `Bug #8: resolve_effect should gracefully handle non-dict payloads.`, `Return destination zone for a dying creature: 'graveyard' or 'exile'.`, `Return PT bonus from +1/+1 and -1/-1 counters on a card.`, `Props`, `HoverPreview` (+55 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `from_decks()` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 9`, `Community 13`, `Community 14`, `Community 16`, `Community 18`, `Community 26`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `from_decks()` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 7`, `Community 9`, `Community 13`, `Community 14`, `Community 16`, `Community 18`, `Community 19`, `Community 26`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `RulesEngine` connect `Community 0` to `Community 1`, `Community 3`, `Community 6`, `Community 9`, `Community 14`, `Community 16`, `Community 19`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `from_decks()` (e.g. with `main()` and `run()`) actually correct?**
  _`from_decks()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `from_decks()` (e.g. with `main()` and `_build_match()`) actually correct?**
  _`from_decks()` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `AIAgent` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`AIAgent` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 70 inferred relationships involving `RulesEngine` (e.g. with `MatchController` and `DeckImportRequest`) actually correct?**
  _`RulesEngine` has 70 INFERRED edges - model-reasoned connections that need verification._