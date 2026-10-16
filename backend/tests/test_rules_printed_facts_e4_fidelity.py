"""First actual consumer inputs, not an assertion on a substitute fixture builder."""
import importlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import _infer_keywords, _infer_power, _infer_toughness
from rules_engine.card_types import printed_card_types
from tests.rules_printed_facts_e4 import raw_card

# Only separable named positives. Historic/parser collisions are not admitted here.
SUBJECTS = (
    ('test_oracle_effects', 'test_oracle_damage_parsing', 'infer_effect_from_oracle', 'Lightning Bolt'),
    ('test_oracle_effects', 'test_oracle_counterspell_parsing', 'infer_effect_from_oracle', 'Counterspell'),
    ('test_oracle_effects', 'test_oracle_copy_spell_parsing', 'infer_effect_from_oracle', 'Twincast'),
    ('test_oracle_effects', 'test_twincast_can_copy_instant_or_sorcery_but_not_creature_spell', 'build_cast_hints', 'Twincast'),
    ('test_oracle_effects', 'test_oracle_counter_ability_parsing', 'infer_effect_from_oracle', 'Stifle'),
    ('test_oracle_effects', 'test_oracle_target_hints_include_artifact_and_enchantment_targets', 'inspect_target_hints', 'Disenchant'),
    ('test_oracle_effects', 'test_split_card_marks_split_hints', 'inspect_target_hints', 'Fire // Ice'),
    ('test_oracle_effects', 'test_copy_spell_handler_replays_target_effect', 'resolve_effect', 'Lightning Bolt'),
    ('test_oracle_effects', 'test_copy_ability_handler_replays_target_ability', 'emit_event', 'Soul Warden'),
    ('test_oracle_effects', 'test_counter_ability_handler_removes_stack_item', 'checked_action', 'Soul Warden'),
    ('test_oracle_effects', 'test_oracle_reanimate_parsing_and_resolution', 'inspect_target_hints', 'Reanimate'),
    ('test_oracle_effects', 'test_oracle_reanimate_can_target_opponent_graveyard', 'inspect_target_hints', 'Reanimate'),
    ('test_oracle_effects', 'test_oracle_any_color_mana_choice_uses_hand_needs', 'infer_effect_from_oracle', 'Lotus Cobra'),
    ('test_oracle_effects', 'test_oracle_search_library_for_artifact_card_uses_type_based_filtering', 'infer_effect_from_oracle', 'Fabricate'),
    ('test_oracle_effects', 'test_oracle_token_count_and_keywords_parsing', 'infer_effect_from_oracle', 'Call the Cavalry'),
    ('test_oracle_effects', 'test_oracle_destroy_all_creatures_resolution_wipes_board', 'resolve_effect', 'Runeclaw Bear'),
    ('test_oracle_effects', 'test_oracle_destroy_target_artifact_or_enchantment_prefers_matching_permanent', 'infer_effect_from_oracle', 'Disenchant'),
    ('test_oracle_effects', 'test_oracle_destroy_all_artifacts_and_enchantments_wipes_both_types', 'resolve_effect', 'Oath of Nissa'),
    ('test_oracle_effects', 'test_oracle_collected_company_style_parsing', 'infer_effect_from_oracle', 'Collected Company'),
    ('test_oracle_effects', 'test_arboreal_grazer_style_land_from_hand_enters_tapped_without_land_play', 'infer_effect_from_oracle', 'Arboreal Grazer'),
    ('test_oracle_effects', 'test_storm_the_festival_style_puts_permanents_from_top', 'infer_effect_from_oracle', 'Storm the Festival'),
    ('test_oracle_effects', 'test_shark_typhoon_style_effect_uses_cast_spell_mana_value', 'emit_event', 'Shark Typhoon'),
    ('test_oracle_effects', 'test_goblin_guide_style_reveals_defending_top_land', 'infer_effect_from_oracle', 'Goblin Guide'),
    ('test_events_apnap', 'test_named_self_counter_trigger_resolves_without_card_specific_handler', 'emit_event', 'Sprite Dragon'),
    ('test_events_apnap', 'test_goblin_guide_attack_trigger_queues_structured_reveal', 'emit_event', 'Goblin Guide'),
    ('test_events_apnap', 'test_creature_dies_trigger_matches_you_control_clause', 'emit_event', 'Grim Haruspex'),
    ('test_events_apnap', 'test_creature_dies_trigger_does_not_match_opponent_creature', 'emit_event', 'Grim Haruspex'),
    ('test_events_apnap', 'test_gearhulk_etb_trigger_uses_graveyard_spell_effect', 'emit_event', 'Torrential Gearhulk'),
    ('test_events_apnap', 'test_play_land_emits_landfall_trigger', 'take_action', 'Lotus Cobra'),
    ('test_named_death_triggers', 'test_dying_blood_artist_sees_every_creature_in_simultaneous_wipe', 'destroy_all_creatures', 'Blood Artist'),
    ('test_named_death_triggers', 'test_departing_another_creature_watcher_excludes_its_own_death', 'destroy_all_creatures', 'Pitiless Plunderer'),
    ('test_named_death_triggers', 'test_graveyard_exile_replacement_prevents_simultaneous_death_triggers', 'destroy_all_creatures', 'Rest in Peace'),
    ('test_named_death_triggers', 'test_departing_nontoken_watcher_sees_other_nontoken_but_not_itself_or_token', 'destroy_all_creatures', 'Harvester of Souls'),
    ('test_trigger_power_damage', 'test_creature_death_trigger_deals_its_power_as_damage', 'emit_event', 'Dreadhorde Butcher'),
    ('test_trigger_power_damage', 'test_enter_trigger_casts_target_instant_from_graveyard', 'emit_event', 'Torrential Gearhulk'),
    ('test_trigger_power_damage', 'test_hydroid_krasis_self_cast_trigger_resolves_before_x_creature_enters', 'add_to_stack', 'Hydroid Krasis'),
    ('test_activated_sacrifice_events', 'test_human_orders_death_and_sacrifice_cost_triggers_above_ability', 'take_action', 'Fanatical Firebrand'),
    ('test_activated_sacrifice_events', 'test_human_orders_death_and_sacrifice_cost_triggers_above_ability', 'take_action', 'Bastion of Remembrance'),
    ('test_activated_sacrifice_events', 'test_human_orders_death_and_sacrifice_cost_triggers_above_ability', 'take_action', 'Mayhem Devil'),
    ('test_sacrifice_lookback', 'test_simultaneously_sacrificed_watcher_sees_each_annihilator_sacrifice', 'resolve_annihilator', 'Mayhem Devil'),
    ('test_sacrifice_lookback', 'test_simultaneously_sacrificed_watcher_sees_each_annihilator_sacrifice', 'resolve_annihilator', 'Llanowar Elves'),
    ('test_incubate_rules', 'test_sunfall_exiles_creatures_then_incubates_exiled_count', 'build_ability_spec', 'Sunfall'),
    ('test_incubate_rules', 'test_seedshark_incubates_cast_spells_mana_value_not_paid_cost', 'add_to_stack', 'Chrome Host Seedshark'),
    ('test_incubate_rules', 'test_incubate_twice_uses_land_count_and_unknown_x_is_not_silently_zero', 'build_ability_spec', 'Glistening Dawn'),
    ('test_target_restrictions', 'test_nonartifact_restriction_filters_creature_targets', 'inspect_target_hints', 'Go for the Throat'),
    ('test_target_restrictions', 'test_fatal_push_mana_value_condition_does_not_filter_targets', 'inspect_target_hints', 'Fatal Push'),
    ('test_target_restrictions', 'test_controlled_type_restriction_uses_current_battlefield_count', 'inspect_target_hints', 'Lay Down Arms'),
    ('test_target_restrictions', 'test_modal_counter_mode_is_structured_before_stack_target_exists', 'build_ability_spec', 'Drown in the Loch'),
)
PRINTED = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
           'printed_power', 'printed_toughness', 'loyalty', 'colors', 'keywords', 'layout',
           'card_faces', 'selected_face_index')


def capture(monkeypatch, module_name, test_name, boundary, name):
    original = importlib.import_module('tests.' + module_name)
    found = []
    class BeforeConsumer(BaseException):
        pass
    owner = original.RulesEngine if boundary in {'take_action', 'checked_action'} else original
    if boundary == 'checked_action':
        # This function imports the consumer locally; intercept its real defining module.
        owner = importlib.import_module('rules_engine.action_validation')
    if boundary == 'emit_event' and not hasattr(original, boundary):
        owner = importlib.import_module('rules_engine.events')
    delegate = getattr(owner, boundary)
    def observe(*args, **kwargs):
        state = args[1] if boundary == 'take_action' else args[0]
        cards = list(state.cards.values())
        if boundary in {'infer_effect_from_oracle','inspect_target_hints','build_cast_hints','build_ability_spec'}:
            cards.append(args[1])
        matching = [c for c in cards if c.name == name]
        unique = {id(c): c for c in matching}
        if not unique:
            return delegate(*args, **kwargs)
        found.append(list(unique.values()))
        raise BeforeConsumer
    with monkeypatch.context() as patch:
        patch.setattr(owner, boundary, observe)
        with pytest.raises(BeforeConsumer):
            getattr(original, test_name)()
    assert len(found) == 1
    return found[0]


def expected_printed(name):
    raw = raw_card(name)
    cached = ScryfallSyncService._normalize_payload(raw, None)
    types = printed_card_types(cached['type_line'])
    return dict(name=cached['name'], oracle_text=cached['oracle_text'], mana_cost=cached['mana_cost'],
        type_line=cached['type_line'], types=types, power=_infer_power(cached['name'], cached['power'], types),
        toughness=_infer_toughness(cached['name'], cached['toughness'], types),
        printed_power=cached['power'], printed_toughness=cached['toughness'],
        loyalty=int(cached['loyalty']) if cached['loyalty'] is not None else None,
        colors=cached['colors'].split(',') if cached['colors'] else [], keywords=_infer_keywords(cached['oracle_text']),
        layout=cached['layout'], card_faces=json.loads(cached['card_faces_json']), selected_face_index=None)


@pytest.mark.parametrize('module_name,test_name,boundary,name', SUBJECTS,
    ids=[m+'.'+t+':'+n for m,t,b,n in SUBJECTS])
def test_original_first_consumer_receives_full_printed_facts(monkeypatch, module_name, test_name, boundary, name):
    cards = capture(monkeypatch, module_name, test_name, boundary, name)
    expected = expected_printed(name)
    for card in cards:
        assert {field: getattr(card, field) for field in PRINTED} == expected


def test_exact_sources_are_full_fresh_and_unmodified():
    for name in sorted({row[3] for row in SUBJECTS}):
        first, second = raw_card(name), raw_card(name)
        assert first == second and first is not second
        assert first['object'] == 'card' and first['name'] == name
        assert first['id'] and first['oracle_id'] and first['legalities'] and first['uri']
        first['legalities'].clear()
        assert raw_card(name)['legalities'] == second['legalities']


def test_pristine_old_protocol_functions_remain_source_exact():
    from tests.interface_scope_compatibility import restore_printed_protocol_source
    import ast
    import hashlib
    fixture = Path(__file__).parent / 'fixtures/rules_printed_facts_e4/UNCHANGED_FUNCTION_SHA256.json'
    for identity, digest in json.loads(fixture.read_bytes()).items():
        module, function = identity.split(':')
        source = (Path(__file__).parent / module).read_text()
        source = restore_printed_protocol_source(module, source)
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function)
        assert hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest() == digest


def test_current_canonical_fire_ice_reports_real_faces_not_invented_modal_modes():
    from game_state.state import MatchFactory, Zone
    from rules_engine.oracle_effects import inspect_target_hints
    from tests.rules_printed_facts_e4 import canonical_card, canonical_deck_entry
    state = MatchFactory.from_decks([canonical_deck_entry('Island', 60)],
                                   [canonical_deck_entry('Island', 60)], seed=119)
    card = canonical_card('Fire // Ice', id='official-split', owner=1, controller=1, zone=Zone.HAND)
    before = {field: getattr(card, field) for field in PRINTED}
    assert before == expected_printed('Fire // Ice')
    hints = inspect_target_hints(state, card, 1)
    assert hints['split_card'] is True and hints['face_names'] == ['Fire', 'Ice']
    assert not hints.get('modes')
    assert {field: getattr(card, field) for field in PRINTED} == before


def test_materialized_printed_containers_and_faces_are_independent():
    from game_state.state import Zone
    from tests.rules_printed_facts_e4 import canonical_card
    first = canonical_card('Fire // Ice', id='left', owner=1, controller=1, zone=Zone.HAND)
    second = canonical_card('Fire // Ice', id='right', owner=2, controller=2, zone=Zone.GRAVEYARD)
    assert first.id != second.id and first.owner == first.controller == 1
    assert second.owner == second.controller == 2 and second.zone == Zone.GRAVEYARD
    assert first.card_faces == second.card_faces == expected_printed('Fire // Ice')['card_faces']
    assert first.card_faces is not second.card_faces and first.card_faces[0] is not second.card_faces[0]
    first.card_faces[0]['name'] = 'local-mutation'
    first.colors.append('local-mutation')
    first.counters['local-mutation'] = 1
    assert second.card_faces == expected_printed('Fire // Ice')['card_faces']
    assert second.colors == expected_printed('Fire // Ice')['colors'] and second.counters == {}


def test_butcher_preserves_old_effective_power_without_fabricating_printed_stats(monkeypatch):
    from rules_engine.continuous import effective_power, effective_toughness
    from tests import test_trigger_power_damage as original
    original_emit = original.emit_event
    seen = []
    def inspect(state, event, payload):
        card = state.cards['butcher']
        assert card.power == card.toughness == 1
        assert card.printed_power == card.printed_toughness == '1'
        assert effective_power(state, card.id) == 3 and effective_toughness(state, card.id) == 1
        assert card.counters == {'__eot_power': 2} and payload['power'] == 3
        seen.append(True)
        return original_emit(state, event, payload)
    with monkeypatch.context() as patch:
        patch.setattr(original, 'emit_event', inspect)
        original.test_creature_death_trigger_deals_its_power_as_damage()
    assert seen == [True]


def test_materializer_rejects_printed_field_overrides():
    from game_state.state import Zone
    from tests.rules_printed_facts_e4 import canonical_card
    for key, value in [('oracle_text', ''), ('types', []), ('mana_cost', ''), ('power', 17), ('card_faces', [])]:
        with pytest.raises(AssertionError):
            canonical_card('Lightning Bolt', id='strict', owner=1, controller=1, zone=Zone.HAND, **{key: value})


def test_one_exact_intake_is_complete_pinned_and_precedes_offline_tests():
    import hashlib
    root = Path(__file__).parent / 'fixtures/rules_printed_facts_e4'
    proof = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert proof['complete'] and proof['request_count'] == len(proof['requests']) == 12
    assert proof['oracle_modified'] is False and proof['elapsed_seconds'] < 120
    assert proof['automatic_retry'] is False and proof['spacing_minimum_seconds'] >= 0.3
    for before, after in zip(proof['requests'], proof['requests'][1:]):
        assert after['start_monotonic'] - before['start_monotonic'] >= 0.3
    for record in proof['requests']:
        data = (root / record['file']).read_bytes()
        assert record['status'] == 200 and record['full_raw_preserved'] and record['identity_verified']
        assert len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256']
        assert record['response_headers'] and record['started_utc'] and record['finished_utc']
        assert record['response_url'] == record['url']
        assert json.loads(data)['name'] == record['requested_name']
        assert json.loads(data)['id'] == record['scryfall_id']


def test_mana_choice_pose_uses_existing_cards_without_extra_cards_or_mana(monkeypatch):
    from game_state.state import Zone
    from tests import test_oracle_effects as original
    actual_factory = original.MatchFactory.from_decks
    actual_infer = original.infer_effect_from_oracle
    initial = []
    observed = []
    def without_blue_in_initial_hand(*args, **kwargs):
        state = actual_factory(*args, **kwargs)
        player = state.players[1]
        blue = next(cid for cid in player.library + player.hand if state.cards[cid].name == 'Counterspell')
        if blue in player.hand:
            other = player.library[-1]
            player.hand[player.hand.index(blue)] = other
            player.library[-1] = blue
            state.cards[blue].move_to_zone(Zone.LIBRARY)
            state.cards[other].move_to_zone(Zone.HAND)
        assert blue not in player.hand
        initial.append((set(state.cards), len(player.hand), len(player.library), dict(player.mana_pool)))
        return state
    def observe(state, card, player_id, *args, **kwargs):
        player = state.players[player_id]
        assert any(state.cards[cid].name == 'Counterspell' and state.cards[cid].mana_cost == '{U}{U}' for cid in player.hand)
        assert (set(state.cards), len(player.hand), len(player.library), player.mana_pool) == initial[0]
        assert all(state.cards[cid].zone == Zone.HAND for cid in player.hand)
        assert all(state.cards[cid].zone == Zone.LIBRARY for cid in player.library)
        observed.append(True)
        return actual_infer(state, card, player_id, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(original.MatchFactory, 'from_decks', without_blue_in_initial_hand)
        patch.setattr(original, 'infer_effect_from_oracle', observe)
        original.test_oracle_any_color_mana_choice_uses_hand_needs()
    assert observed == [True]
