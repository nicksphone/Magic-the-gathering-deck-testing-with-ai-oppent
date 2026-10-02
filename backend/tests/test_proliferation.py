"""Canonical Oracle fixtures; counter setups are explicitly core-event states."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.proliferation_policy import preferred_recipients
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.proliferation import recipients
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from tests.test_ai_recurring_engines import add as add_card
from tests.test_counter_prohibitions import source as prohibition
from tests.test_counter_replacements import source as modifier, choose
from tests.test_restricted_mana import clean
from tests.test_saga_counter_events import saga
from tests.test_ward_resolution import add


ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/proliferate.json').read_text())}
for row in ROWS.values():
    for key in ('power', 'toughness', 'colors', 'keywords'):
        row.setdefault(key, None)


def card(state, name, player=1, zone=Zone.BATTLEFIELD):
    return add_card(state, name, player, zone, cards=ROWS)


def select(state, player, ids):
    return checked_action(state, RulesEngine(), player,
                          {'type': 'choose_mechanic', 'card_ids': ids})


@pytest.mark.parametrize('player', [1, 2])
def test_selection_adds_each_kind_not_each_existing_counter_and_is_not_targeting(player):
    state = clean(player)
    bear = add(state, 'Grizzly Bears', player)
    bear.keywords += ['Hexproof', 'Shroud', 'Ward {2}']
    bear.counters = {'+1/+1': 3, 'shield': 2, 'stun': 1, '__damage_marked': 1, 'charge': 0}
    state.players[player].poison = 2
    state.players[player].counters = {'energy': 3, 'experience': 1}
    state.mechanic_choice_players = {player}
    resolve_effect(state, player, 'proliferate', {})
    assert len(state.pending_mechanic_choice['options']) == 2
    before = serialize_match_snapshot(state)
    for ids in [['not-a-recipient'], [f'card:{bear.id}', f'card:{bear.id}']]:
        with pytest.raises(ActionRejected):
            select(state, player, ids)
        assert serialize_match_snapshot(state) == before
    with pytest.raises(ActionRejected):
        select(state, 3-player, [])
    assert serialize_match_snapshot(state) == before
    state = deserialize_match_snapshot(before)
    state = select(state, player, [f'card:{bear.id}', f'player:{player}'])
    assert state.cards[bear.id].counters == {
        '+1/+1': 4, 'shield': 3, 'stun': 2, '__damage_marked': 1, 'charge': 0}
    assert state.players[player].poison == 3
    assert state.players[player].counters == {'energy': 4, 'experience': 2}
    assert state.pending_mechanic_choice is None


@pytest.mark.parametrize('eligible', [False, True])
def test_none_is_a_legal_selection_and_still_a_proliferation_event(eligible):
    state = clean()
    watcher = card(state, 'Ezuri, Stalker of Spheres')
    if eligible:
        watcher.counters['+1/+1'] = 1
    state.mechanic_choice_players = {1}
    resolve_effect(state, 1, 'proliferate', {})
    if eligible:
        state = select(state, 1, [])
    assert state.cards[watcher.id].counters.get('+1/+1', 0) == int(eligible)
    assert len(state.stack) == 1
    assert state.stack[0].controller == 1
    hand = len(state.players[1].hand)
    resolve_top_of_stack(state)
    assert len(state.players[1].hand) == hand+1


@pytest.mark.parametrize('first,expected', [('add', 4), ('double', 3)])
def test_one_replacement_ability_modifies_all_matching_kinds_once(first, expected):
    state = clean()
    state.replacement_choice_required = True
    state.replacement_choice_players = {1}
    bear = add(state, 'Grizzly Bears')
    bear.counters = {'+1/+1': 1, 'shield': 1}
    modifier(state, 'Winding Constrictor')
    modifier(state, 'Doubling Season')
    resolve_effect(state, 1, 'proliferate', {'recipients': [f'card:{bear.id}']})
    assert bear.counters == {'+1/+1': 1, 'shield': 1}
    pending = state.pending_replacement_choice
    assert all(set(o['counter_kinds']) == {'+1/+1', 'shield'} for o in pending['options'])
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, first)
    assert not state.pending_replacement_choice
    assert state.cards[bear.id].counters == {'+1/+1': 1+expected, 'shield': 1+expected}
    assert len([line for line in state.log if 'proliferates.' in line]) == 1


def test_kind_specific_modifier_and_prohibition_do_not_bleed_between_kinds():
    state = clean()
    bear = add(state, 'Grizzly Bears')
    bear.counters = {'+1/+1': 1, 'shield': 1}
    modifier(state, 'Hardened Scales')
    state.players[2].poison = 2
    resolve_effect(state, 1, 'proliferate', {'recipients': [f'card:{bear.id}', 'player:2']})
    assert bear.counters == {'+1/+1': 3, 'shield': 2}
    assert state.players[2].poison == 3
    prohibition(state, 'Solemnity')
    resolve_effect(state, 1, 'proliferate', {'recipients': list(recipients(state))})
    assert bear.counters == {'+1/+1': 3, 'shield': 2}
    assert state.players[2].poison == 3


@pytest.mark.parametrize('active', [1, 2])
def test_all_recipients_wait_for_apnap_choices_and_resume_once(active):
    state = clean(active)
    state.replacement_choice_required = True
    state.replacement_choice_players = {1, 2}
    modifier(state, 'Vorinclex, Monstrous Raider', 1)
    modifier(state, 'Vorinclex, Monstrous Raider', 2)
    state.players[1].counters['energy'] = 1
    state.players[2].counters['energy'] = 1
    resolve_effect(state, 1, 'proliferate', {'recipients': ['player:2', 'player:1']})
    assert state.pending_replacement_choice['player_id'] == active
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'double')
    assert [state.players[p].counters['energy'] for p in (1, 2)] == [1, 1]
    assert state.pending_replacement_choice['player_id'] == 3-active
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'half')
    assert state.players[active].counters['energy'] == 2
    assert state.players[3-active].counters['energy'] == 1
    assert not state.pending_replacement_choice


def test_loyalty_and_lore_use_authoritative_fields_and_chapter_trigger():
    state = clean()
    history = saga(state)
    history.counters['__lore'] = 1
    walker = prohibition(state, "Elspeth, Sun's Champion")
    walker.loyalty = 7
    resolve_effect(state, 1, 'proliferate', {'recipients': [f'card:{history.id}', f'card:{walker.id}']})
    assert history.counters['__lore'] == 2 and walker.loyalty == 8
    assert 'lore' not in history.counters and 'loyalty' not in walker.counters
    assert [item.payload['__chapter_number'] for item in state.stack] == [2]


@pytest.mark.parametrize('name,draw_before,draw_after', [
    ('Contentious Plan', 0, 1), ("Tezzeret's Gambit", 2, 0),
])
def test_real_spell_instruction_order_and_snapshot_continuation(name, draw_before, draw_after):
    state = clean()
    spell = card(state, name, zone=Zone.HAND)
    state.players[1].hand.remove(spell.id)
    spell.move_to_zone(Zone.STACK)
    state.players[1].counters['energy'] = 1
    state.mechanic_choice_players = {1}
    key, payload = infer_effect_from_oracle(state, spell, 1)
    add_to_stack(state, spell.id, 1, spell.name, key, payload)
    hand = len(state.players[1].hand)
    resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'proliferate'
    assert len(state.players[1].hand) == hand+draw_before
    assert spell.id not in state.players[1].graveyard
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = select(state, 1, ['player:1'])
    assert state.players[1].counters['energy'] == 2
    assert len(state.players[1].hand) == hand+draw_before+draw_after
    assert state.players[1].graveyard.count(spell.id) == 1
    assert not state.pending_mechanic_choice and not state.stack


@pytest.mark.parametrize('name,event,payload', [
    ('Thrummingbird', 'combat_damage_dealt', {'source_card_id': 'SOURCE', 'target_player': 2, 'amount': 1}),
    ('Evolution Sage', 'enters_battlefield', {'card_id': 'LAND', 'controller': 1}),
    ('Inexorable Tide', 'spell_cast', {'card_id': 'SPELL', 'controller': 1}),
])
def test_canonical_trigger_families(name, event, payload):
    state = clean()
    source = card(state, name)
    land = add(state, 'Forest')
    spell = card(state, 'Contentious Plan', zone=Zone.HAND)
    ids = {'SOURCE': source.id, 'LAND': land.id, 'SPELL': spell.id}
    emit_event(state, event, {k: ids.get(v, v) if isinstance(v, str) else v for k, v in payload.items()})
    assert len(state.stack) == 1
    assert state.stack[0].effect_key == 'effect_sequence'
    assert state.stack[0].payload['effects'][0]['effect_key'] == 'proliferate'


@pytest.mark.parametrize('style', ['Aggro', 'Burn', 'Control', 'Tempo', 'Ramp', 'Tokens', 'Tribal', 'Drain', 'Midrange'])
def test_ai_uses_public_mixed_counter_values_across_archetypes(style):
    state = clean()
    own = add(state, 'Grizzly Bears')
    enemy = add(state, 'Grizzly Bears', 2)
    own.counters = {'+1/+1': 1, 'shield': 1}
    enemy.counters = {'-1/-1': 1}
    state.players[1].poison = 9
    state.players[2].poison = 9
    available = recipients(state)
    expected = {f'card:{own.id}', f'card:{enemy.id}', 'player:2'}
    assert set(preferred_recipients(state, 1, available)) == expected
    state.mechanic_choice_players = {1}
    resolve_effect(state, 1, 'proliferate', {})
    action = AIAgent('master', style).choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert action['type'] == 'choose_mechanic' and set(action['card_ids']) == expected


def test_mixed_kind_cost_cannot_be_optimized_by_omitting_a_harmful_kind():
    state = clean()
    state.players[1].counters['energy'] = 10
    state.players[1].poison = 9
    assert preferred_recipients(state, 1, recipients(state)) == []


def test_legacy_duplicate_poison_and_internal_player_markers_are_not_recipients():
    state = clean()
    state.players[1].counters = {'poison': 100, '__marker': 1}
    assert not recipients(state)
    state.players[1].poison = 2
    assert recipients(state)['player:1']['counter_amounts'] == {'poison': 1}


def test_stale_recipient_is_not_applied_to_a_new_object():
    state = clean()
    bear = add(state, 'Grizzly Bears')
    bear.counters = {'+1/+1': 1, 'shield': 1}
    modifier(state, 'Winding Constrictor')
    modifier(state, 'Doubling Season')
    resolve_effect(state, 1, 'proliferate', {'recipients': [f'card:{bear.id}']})
    bear.move_to_zone(Zone.EXILE)
    bear.move_to_zone(Zone.BATTLEFIELD)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = choose(state, 'double')
    assert state.cards[bear.id].counters == {}
    assert any('recipient changed zones' in line for line in state.log)


def test_two_instructions_have_independent_selections_and_one_spell_continuation():
    state = clean(2)
    state.players[1].counters['energy'] = 1
    state.players[2].counters['energy'] = 1
    state.mechanic_choice_players = {2}
    resolve_effect(state, 2, 'effect_sequence', {'effects': [
        {'effect_key': 'proliferate', 'payload': {}},
        {'effect_key': 'proliferate', 'payload': {}},
        {'effect_key': 'draw_cards', 'payload': {'amount': 1}},
    ]})
    state = select(state, 2, ['player:1'])
    assert state.pending_mechanic_choice['player_id'] == 2
    assert state.players[1].counters['energy'] == 2
    hand = len(state.players[2].hand)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = select(state, 2, ['player:2'])
    assert state.players[2].counters['energy'] == 2
    assert len(state.players[2].hand) == hand+1


def test_unimplemented_event_replacement_is_explicitly_reported():
    from rules_engine.coverage import known_unsupported_mechanics
    result = known_unsupported_mechanics(ROWS['Tekuthal, Inquiry Dominus']['oracle_text'])
    assert 'proliferate event replacement' in result
    assert 'conditional proliferation' in known_unsupported_mechanics(ROWS['Ezuri, Stalker of Spheres']['oracle_text'])


@pytest.mark.parametrize('style', ['Aggro', 'Control', 'Tempo', 'Ramp'])
def test_ai_casts_canonical_proliferation_spell_for_public_poison_lethal(style):
    state = clean()
    spell = card(state, 'Contentious Plan', zone=Zone.HAND)
    state.players[1].mana_pool = {'U': 2}
    state.players[2].poison = 9
    before = serialize_match_snapshot(state)
    action = AIAgent('master', style).choose_action(state, RulesEngine().legal_moves(state, 1), 1).action
    assert action['type'] == 'cast_spell' and action['card_id'] == spell.id
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('kind,expected_first,expected', [
    ('energy', 'add', 4), ('poison', 'double', 3),
])
def test_ai_vector_replacement_order_optimizes_recipient_result(kind, expected_first, expected):
    state = clean()
    modifier(state, 'Winding Constrictor')
    modifier(state, 'Vorinclex, Monstrous Raider')
    if kind == 'poison':
        state.players[1].poison = 1
    else:
        state.players[1].counters[kind] = 1
    resolve_effect(state, 1, 'proliferate', {'recipients': ['player:1']})
    pending = state.pending_replacement_choice
    decision = AIAgent('master').choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    chosen = next(o for o in pending['options'] if o['source_id'] == decision.action['replacement_source_id'])
    assert chosen['operation'] == expected_first
    state = checked_action(state, RulesEngine(), 1, decision.action)
    actual = state.players[1].poison if kind == 'poison' else state.players[1].counters[kind]
    assert actual == 1+expected


def test_events_observe_the_complete_placement_batch():
    from unittest.mock import patch
    from rules_engine.events import emit_event_batch as original
    state = clean()
    state.players[1].counters['energy'] = 1
    state.players[2].counters['energy'] = 1
    observed = []

    def observe(game_state, event, payloads):
        observed.append((event, [game_state.players[p].counters['energy'] for p in (1, 2)]))
        original(game_state, event, payloads)

    with patch('rules_engine.proliferation.emit_event_batch', side_effect=observe):
        resolve_effect(state, 1, 'proliferate', {'recipients': ['player:1', 'player:2']})
    assert observed and all(values == [2, 2] for _, values in observed)


def test_http_choices_reject_bad_actors_and_recover_nested_replacement(game):
    from tests.test_api_input_contracts import persist, rejected
    import main
    client, controller = game
    state = controller.state
    state.active_player = state.priority_player = 2
    state.players[2].counters['energy'] = 1
    state.players[2].poison = 1
    modifier(state, 'Winding Constrictor', 2)
    modifier(state, "Lae'zel, Vlaakith's Champion", 2)
    state.mechanic_choice_players = {2}
    resolve_effect(state, 2, 'proliferate', {})
    persist(controller)
    rejected(client, controller, {'type': 'choose_mechanic', 'card_ids': ['player:2']}, 1)
    rejected(client, controller, {'type': 'choose_mechanic', 'card_ids': [{}]}, 2)
    mid = state.id
    response = client.post(f'/matches/{mid}/action', json={
        'player_id': 2, 'action': {'type': 'choose_mechanic', 'card_ids': ['player:2']}})
    assert response.status_code == 200, response.text
    assert response.json()['pending_replacement_choice']['player_id'] == 2
    main.ACTIVE_MATCHES.pop(mid)
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), mid)
    restored = client.get(f'/matches/{mid}')
    assert restored.status_code == 200
    option = next(o for o in restored.json()['pending_replacement_choice']['options'] if o['name'] == 'Winding Constrictor')
    response = client.post(f'/matches/{mid}/action', json={
        'player_id': 2, 'action': {'type': 'choose_replacement', 'replacement_source_id': option['source_id']}})
    assert response.status_code == 200, response.text
    assert response.json()['players']['2']['counters']['energy'] == 4
    assert response.json()['players']['2']['poison'] == 4


# Importing the fixture is deliberate: all API tests run in an isolated checkout.
from tests.test_api_input_contracts import game
