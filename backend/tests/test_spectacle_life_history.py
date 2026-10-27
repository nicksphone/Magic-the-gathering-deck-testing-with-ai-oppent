"""Canonical life transitions plus explicitly synthetic cost-grammar controls.

Trusted initial battlefield placement is not a played-game/ETB certificate.
The original canonical16 separately checks paid Spectacle admission, not exile.
"""
from copy import deepcopy
import json

import pytest

from ai.agent import AIAgent
from effects.handlers import deal_damage, gain_life, lose_life
from game_state.copying import copy_match_state
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.costs import collect_cost_options
from rules_engine.damage_results import apply_player_damage
from rules_engine.engine import RulesEngine
from rules_engine.prevention import add_player_prevention_shield
from rules_engine.replacement import pay_life
from tests.ai_decisions_canonical_cdba import canonical_card
from tests.damage_life_printed_79 import canonical_card as damage_card
from tests.test_ai_strategy_fundamentals import position


RULES = RulesEngine()


def fixture(seat, lands=3):
    state, cards, _, _ = position(seat, ['Skewer the Critics'], ['Mountain'] * lands)
    return state, cards['Skewer the Critics']


def costs(state, seat, cid):
    return collect_cost_options(state, seat, state.cards[cid])


def cheap(state, seat, cid):
    return [option for option in costs(state, seat, cid) if option.id == 'spectacle']


def loss(state, seat):
    return getattr(state, 'life_lost_this_turn', {}).get(seat, 0)


def put(state, name, controller, *, damage=False):
    maker = damage_card if damage else canonical_card
    card = maker(name, id='spectacle-control-' + str(len(state.cards)),
                 owner=controller, controller=controller, zone=Zone.BATTLEFIELD,
                 summoning_sick=False, **({} if damage else {'as_instance': True}))
    state.cards[card.id] = card
    state.players[controller].battlefield.append(card.id)
    return card.id


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('cause', ('damage', 'paid_life', 'effect_loss'))
def test_actual_loss_routes_record_opposing_loss_without_new_events(seat, cause):
    state, cid = fixture(seat)
    if cause == 'damage':
        apply_player_damage(state, 3-seat, 2, None)
    elif cause == 'paid_life':
        assert pay_life(state, 3-seat, 2)
    else:
        lose_life(state, seat, {'target_player': 3-seat, 'amount': 2})
    assert state.players[3-seat].life == 18
    assert loss(state, 3-seat) == 2 and loss(state, seat) == 0
    assert cheap(state, seat, cid)
    assert not state.stack and not state.pending_trigger_order


@pytest.mark.parametrize('seat', (1, 2))
def test_gain_does_not_erase_loss_and_initial_low_life_is_not_a_witness(seat):
    state, cid = fixture(seat)
    state.players[3-seat].life = 7  # Declared pose, not an engine loss event.
    assert not cheap(state, seat, cid)
    gain_life(state, seat, {'target_player': 3-seat, 'amount': 16})
    assert loss(state, 3-seat) == 0
    lose_life(state, seat, {'target_player': 3-seat, 'amount': 2})
    gain_life(state, seat, {'target_player': 3-seat, 'amount': 2})
    assert state.players[3-seat].life == 23
    assert loss(state, 3-seat) == 2 and cheap(state, seat, cid)


@pytest.mark.parametrize('seat', (1, 2))
def test_own_loss_and_zero_payments_do_not_enable_spectacle(seat):
    state, cid = fixture(seat)
    assert pay_life(state, seat, 1) and pay_life(state, 3-seat, 0)
    assert loss(state, seat) == 1 and loss(state, 3-seat) == 0
    assert not cheap(state, seat, cid)


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('kind', ('prevented', 'infect', 'life_locked', 'creature_damage'))
def test_no_actual_player_life_loss_means_no_discount(seat, kind):
    state, cid = fixture(seat)
    if kind == 'prevented':
        add_player_prevention_shield(state, 3-seat, 3)
        assert deal_damage(state, seat, {'target_player': 3-seat, 'amount': 3}) == 0
    elif kind == 'infect':
        source = put(state, 'Glistener Elf', seat, damage=True)
        apply_player_damage(state, 3-seat, 2, source)
        assert state.players[3-seat].poison == 2
    elif kind == 'life_locked':
        put(state, 'Platinum Emperion', 3-seat, damage=True)
        assert not pay_life(state, 3-seat, 1)
        lose_life(state, seat, {'target_player': 3-seat, 'amount': 2})
        deal_damage(state, seat, {'target_player': 3-seat, 'amount': 2})
    else:
        target = put(state, 'Grizzly Bears', 3-seat)
        deal_damage(state, seat, {'target_card_id': target, 'amount': 1})
    assert state.players[3-seat].life == 20
    assert loss(state, 3-seat) == 0 and not cheap(state, seat, cid)


@pytest.mark.parametrize('seat', (1, 2))
def test_legacy_unknown_remains_unknown_after_one_player_witness_and_copies(seat):
    state, cid = fixture(seat)
    payload = serialize_match_snapshot(state)
    payload.pop('life_lost_this_turn', None)
    payload.pop('life_loss_history_known', None)
    restored = deserialize_match_snapshot(json.loads(json.dumps(payload)))
    assert getattr(restored, 'life_loss_history_known', True) is False
    assert not cheap(restored, seat, cid)
    assert pay_life(restored, 3-seat, 2)
    assert loss(restored, 3-seat) == 2 and loss(restored, seat) == 0
    assert restored.life_loss_history_known is False
    assert cheap(restored, seat, cid)
    snapshot = serialize_match_snapshot(restored)
    public = serialize_match(restored)
    assert public['life_lost_this_turn'] == restored.life_lost_this_turn
    assert public['life_loss_history_known'] is False
    assert serialize_match_snapshot(deserialize_match_snapshot(json.loads(json.dumps(snapshot)))) == snapshot
    clone = copy_match_state(restored, include_history=False)
    assert clone.life_lost_this_turn == restored.life_lost_this_turn
    assert clone.life_loss_history_known is False
    clone.life_lost_this_turn[seat] = 9
    assert loss(restored, seat) == 0


@pytest.mark.parametrize('seat', (1, 2))
def test_only_a_genuine_new_turn_resets_all_players_and_knownness(seat):
    state, _ = fixture(seat)
    state.life_loss_history_known = False
    assert pay_life(state, seat, 1) and pay_life(state, 3-seat, 2)
    turn = state.turn
    for _ in range(128):
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order)
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
        if state.turn > turn:
            break
        assert loss(state, seat) == 1 and loss(state, 3-seat) == 2
        assert state.life_loss_history_known is False
    assert state.turn == turn + 1
    assert state.life_lost_this_turn == {1: 0, 2: 0}
    assert state.life_loss_history_known is True


@pytest.mark.parametrize('bad', ({'1': -1, '2': 0}, {'1': True, '2': 0},
                                 {'1': '2', '2': 0}, {'1': 0, '3': 0}))
def test_malformed_loss_snapshot_is_rejected_not_cast_to_a_false_fact(bad):
    state, _ = fixture(1)
    payload = serialize_match_snapshot(state)
    payload['life_lost_this_turn'] = bad
    payload['life_loss_history_known'] = True
    with pytest.raises(ValueError):
        deserialize_match_snapshot(payload)


@pytest.mark.parametrize('seat', (1, 2))
def test_actual_spectacle_payment_still_pays_thalia_tax_and_keeps_printed_cost(seat):
    state, cid = fixture(seat)
    put(state, 'Thalia, Guardian of Thraben', 3-seat)
    assert pay_life(state, 3-seat, 1)
    option = cheap(state, seat, cid)
    assert len(option) == 1 and option[0].mana_cost == '{R}'
    after = checked_action(state, RULES, seat, {'type': 'cast_spell', 'card_id': cid,
        'cost_choice': {'id': option[0].id}, 'targets': {'target_player': 3-seat}})
    assert sum(after.cards[x].tapped for x in after.players[seat].battlefield) == 2
    assert after.cards[cid].mana_cost == '{2}{R}' and after.cards[cid].zone == Zone.STACK
    assert loss(state, 3-seat) == loss(after, 3-seat) == 1


@pytest.mark.parametrize('seat', (1, 2))
def test_forged_spectacle_cost_before_loss_is_rejected_without_root_change(seat):
    state, cid = fixture(seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RULES, seat, {'type': 'cast_spell', 'card_id': cid,
            'cost_choice': {'id': 'spectacle'}, 'targets': {'target_player': 3-seat}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('difficulty', ('strong', 'master'))
def test_ai_selects_discount_when_both_prices_are_payable_but_preserves_explicit_base(seat, difficulty):
    state, cid = fixture(seat)
    assert pay_life(state, 3-seat, 1)
    before = serialize_match_snapshot(state)
    moves = RULES.legal_moves(deepcopy(state), seat)
    move = next(move for move in moves if move.get('card_id') == cid and move['type'] == 'cast_spell')
    assert {option['id'] for option in move['cost_options']} == {'base', 'spectacle'}
    agent = AIAgent(archetype='Burn', difficulty=difficulty)
    action = agent._materialize_action(state, move, seat)
    assert action['cost_choice']['id'] == 'spectacle'
    explicit = agent._materialize_action(state, {**move, 'cost_choice': {'id': 'base'}}, seat)
    assert explicit['cost_choice']['id'] == 'base'
    assert serialize_match_snapshot(state) == before
    after = checked_action(state, RULES, seat, action)
    assert sum(after.cards[x].tapped for x in after.players[seat].battlefield) == 1


def test_synthetic_cost_grammar_preserves_additional_cost_and_excludes_other_alt_payments():
    # Deliberately synthetic compiler vector, not a claimed real card/Oracle row.
    state, _ = fixture(1)
    card = CardInstance('synthetic-cost', 'Synthetic Spectacle cost grammar vector', 1, 1,
        Zone.HAND, mana_cost='{2}{R}', types=['Sorcery'], oracle_text=(
            'Spectacle {R}\nKicker {1}\nAs an additional cost to cast this spell, pay 2 life.\n'
            'If this spell was kicked, gain 1 life.'))
    assert pay_life(state, 2, 1)
    options = collect_cost_options(state, 1, card)
    spectacle = [option for option in options if option.id == 'spectacle']
    assert len(spectacle) == 1 and spectacle[0].pay_life == 2
    assert any(option.kicker_base_id == 'spectacle' and option.pay_life == 2 for option in options)
    free = collect_cost_options(state, 1, card, without_mana=True)
    assert all(not option.id.startswith('spectacle') for option in free)
    assert all(option.pay_life == 2 for option in free)


@pytest.mark.parametrize('field,value', (('pay_life', 1), ('graveyard_permission_key', 'synthetic-grant'),
                                         ('mana_cost', '{U}')))
def test_synthetic_non_equivalent_offered_cost_is_not_treated_as_free_savings(field, value):
    # Negative move-metadata protocol control; never submitted as an actual cast.
    state, cid = fixture(1)
    assert pay_life(state, 2, 1)
    move = next(move for move in RULES.legal_moves(deepcopy(state), 1)
                if move.get('card_id') == cid and move['type'] == 'cast_spell')
    assert {option['id'] for option in move['cost_options']} == {'base', 'spectacle'}
    move = deepcopy(move)
    next(option for option in move['cost_options'] if option['id'] == 'spectacle')[field] = value
    action = AIAgent(archetype='Burn', difficulty='strong')._materialize_action(state, move, 1)
    assert action['cost_choice']['id'] == 'base'
