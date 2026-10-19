"""The printed opponent qualifier and the original any-source fixture are distinct."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_activated_ability_timing as original
from tests.cycling_timing_canonical_022758 import canonical_card, deck_entry, raw_card
from tests.test_cycling_timing_022758_fidelity import _assert_complete


def _position(seat, source_controller, ward_name, ward_count=1):
    deck = [deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=7)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = source_controller
    state.step = Step.PRECOMBAT_MAIN
    rats = canonical_card('Crypt Rats', id='qualified-rats', owner=source_controller,
                          controller=source_controller, zone=Zone.BATTLEFIELD)
    rats.summoning_sick = False
    state.cards[rats.id] = rats
    state.players[source_controller].battlefield.append(rats.id)
    for index in range(1, ward_count + 1):
        card = canonical_card(ward_name, id=f'hekma-{index}', owner=seat,
                              controller=seat, zone=Zone.BATTLEFIELD)
        _assert_complete(card, ward_name)
        state.cards[card.id] = card
        state.players[seat].battlefield.append(card.id)
    return state, rats.id


def test_urzas_armor_is_the_exact_full_official_any_source_instruction():
    raw = raw_card("Urza's Armor")
    assert raw['oracle_text'] == 'If a source would deal damage to you, prevent 1 of that damage.'
    assert raw['type_line'] == 'Artifact' and raw['mana_cost'] == '{6}'
    assert len(raw) == 64
    card = canonical_card("Urza's Armor", id='armor-proof', owner=1,
                          controller=1, zone=Zone.BATTLEFIELD)
    _assert_complete(card, "Urza's Armor")


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opposing_source', [False, True])
def test_canonical_hekma_qualifies_real_self_and_opposing_rats(seat, opposing_source):
    actor = 3 - seat if opposing_source else seat
    state, source_id = _position(seat, actor, 'Protection of the Hekma')
    state.players[actor].mana_pool['B'] = 1
    engine = RulesEngine()
    engine.take_action(state, actor, {
        'type': 'activate_ability', 'card_id': source_id,
        'ability_index': 0, 'targets': {'x_value': 1},
    }, reject_invalid=True)
    assert state.players[actor].mana_pool['B'] == 0
    assert state.stack[-1].source_card_id == source_id
    assert resolve_top_of_stack(state) is True
    assert state.pending_replacement_choice is None
    assert state.players[seat].life == (20 if opposing_source else 19)
    assert state.players[3 - seat].life == 19
    assert state.cards[source_id].zone == Zone.GRAVEYARD
    _assert_complete(state.cards['hekma-1'], 'Protection of the Hekma')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('lifelink,expected_life', [(False, 19), (True, 26)])
def test_two_canonical_armors_resume_actual_damage_batch_and_lifelink(seat, lifelink, expected_life):
    state, source_id = _position(seat, seat, "Urza's Armor", ward_count=2)
    if lifelink:
        state.cards[source_id].keywords.append('lifelink')
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    state.players[seat].mana_pool['B'] = 3
    engine = RulesEngine()
    engine.take_action(state, seat, {
        'type': 'activate_ability', 'card_id': source_id,
        'ability_index': 0, 'targets': {'x_value': 3},
    }, reject_invalid=True)
    assert state.players[seat].mana_pool['B'] == 0
    assert len(state.stack) == 1
    assert state.stack[-1].effect_key == 'damage_each_creature_and_player'
    assert resolve_top_of_stack(state) is False
    assert state.pending_replacement_choice['resume_kind'] == 'damage_batch'
    assert state.pending_replacement_choice['player_id'] == seat
    assert {row['source_id'] for row in state.pending_replacement_choice['options']} == {'hekma-1', 'hekma-2'}
    assert state.cards[source_id].zone == Zone.BATTLEFIELD
    snapshot = serialize_match_snapshot(state)
    pending = deepcopy(state.pending_replacement_choice)
    state = deserialize_match_snapshot(snapshot)
    assert state.pending_replacement_choice == pending
    chosen = []
    for expected_count in (2, 1):
        moves = [move for move in engine.legal_moves(state, seat)
                 if move['type'] == 'choose_replacement']
        assert len(moves) == expected_count
        move = moves[0]
        assert move['replacement_source_id'] not in chosen
        chosen.append(move['replacement_source_id'])
        engine.take_action(state, seat, move, reject_invalid=True)
    assert set(chosen) == {'hekma-1', 'hekma-2'}
    assert state.pending_replacement_choice is None and not state.stack
    assert state.players[seat].life == expected_life
    assert state.players[3 - seat].life == 17
    assert state.cards[source_id].zone == Zone.GRAVEYARD
    assert state.winner is None
    for index in (1, 2):
        card = state.cards[f'hekma-{index}']
        assert card.owner == card.controller == seat
        _assert_complete(card, "Urza's Armor")


@pytest.mark.parametrize('lifelink,expected_life', [(False, 19), (True, 26)])
def test_original_golden_body_uses_two_real_armors_and_real_snapshot(monkeypatch, lifelink, expected_life):
    actual_action = RulesEngine.take_action
    actual_restore = original.deserialize_match_snapshot
    observations = {'choices': [], 'restored': [], 'activations': []}

    def action(engine, state, player, value, *args, **kwargs):
        if value.get('type') == 'activate_ability':
            wards = [state.cards[f'hekma-{index}'] for index in (1, 2)]
            assert len([card for card in state.cards.values() if card.id.startswith('hekma-')]) == 2
            for card in wards:
                _assert_complete(card, "Urza's Armor")
                assert card.owner == card.controller == 1
            assert value == {'type': 'activate_ability', 'card_id': 'p1-053',
                             'ability_index': 0, 'targets': {'x_value': 3}}
            assert state.players[1].mana_pool['B'] == 3
            observations['activations'].append(value.copy())
        elif value.get('type') == 'choose_replacement':
            observations['choices'].append(value['replacement_source_id'])
        return actual_action(engine, state, player, value, *args, **kwargs)

    def restore(snapshot):
        state = actual_restore(snapshot)
        assert state.pending_replacement_choice['resume_kind'] == 'damage_batch'
        observations['restored'].append(state)
        return state

    with monkeypatch.context() as patch:
        patch.setattr(RulesEngine, 'take_action', action)
        patch.setattr(original, 'deserialize_match_snapshot', restore)
        original.test_crypt_rats_batch_resumes_human_damage_replacements_before_lethal_sba(
            lifelink, expected_life)
    assert len(observations['activations']) == 1
    assert len(observations['restored']) == 1
    assert len(observations['choices']) == 2
    assert set(observations['choices']) == {'hekma-1', 'hekma-2'}
    restored = observations['restored'][0]
    assert restored.pending_replacement_choice is None
    assert restored.players[1].life == expected_life and restored.players[2].life == 17
