"""Canonical Spectacle cost offers/admission only; no exile resolution."""
from copy import deepcopy
import hashlib
import json

import pytest

from ai.action_contract import complete_action
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import inspect_target_hints
from tests.ai_decisions_canonical_cdba import raw_card
from tests.test_ai_strategy_fundamentals import position
from tests.test_learned_tactical_guard import _salve


RULES = RulesEngine()
CARDS = ('Skewer the Critics', 'Light Up the Stage')
SCENARIOS = ('before_damage', 'after_damage', 'damage_then_gain', 'next_own_turn')


def checked(state, actor, intent, trace):
    before = serialize_match_snapshot(state)
    action = complete_action(intent)
    result = checked_action(state, RULES, actor, action)
    assert serialize_match_snapshot(state) == before
    trace.append(dict(actor=actor, action=action, turn_before=state.turn,
                      step_before=state.step.value, life_after={pid:p.life for pid,p in result.players.items()}))
    return result


def settle(state, trace):
    for _ in range(32):
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                    or state.pending_trigger_order), 'Unknown choice: fixture refusal'
        if not state.stack:
            return state
        state = checked(state, state.priority_player, {'type':'pass_priority'}, trace)
    raise AssertionError('Fixture stack did not settle in32 checked passes')


def offered(state, seat, card_id):
    before = serialize_match_snapshot(state)
    result = [move for move in RULES.legal_moves(deepcopy(state), seat)
              if move.get('type') == 'cast_spell' and move.get('card_id') == card_id]
    assert serialize_match_snapshot(state) == before
    return result


def cost_is(option, mana):
    return str(option.get('mana_cost', '')).replace(' ', '').upper() == mana


@pytest.mark.parametrize('name', CARDS)
@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_canonical_spectacle_cost_offer_and_admission(name, seat, scenario, tmp_path):
    raw = raw_card(name)
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['mana_cost'] == '{2}{R}' and 'Spectacle {R}' in raw['oracle_text']
    state, cards, _, _ = position(seat, ['Lightning Bolt', name], ['Mountain'] * 2)
    initial_turn, initial_life = state.turn, state.players[3-seat].life
    trace, salve = [], None
    if scenario == 'damage_then_gain':
        # Retained pinned complete RAW -> real Factory. White mana is an initial
        # declared fixture resource; no active-player/priority rewriting.
        salve = _salve(state, 3-seat)
    if scenario != 'before_damage':
        bolt = offered(state, seat, cards['Lightning Bolt'])[0]
        price = next(option for option in bolt['cost_options'] if cost_is(option, '{R}'))
        state = checked(state, seat, {**bolt, 'cost_choice':{'id':price['id']},
                                     'targets':{'target_player':3-seat}}, trace)
        state = settle(state, trace)
        assert state.turn == initial_turn and state.players[3-seat].life == initial_life-3
        assert sum(not state.cards[cid].tapped for cid in state.players[seat].battlefield) == 1
        assert not any(state.players[seat].mana_pool.values())
    if scenario == 'damage_then_gain':
        state = checked(state, seat, {'type':'pass_priority'}, trace)
        assert state.priority_player == 3-seat and state.active_player == seat
        salve_offer = offered(state, 3-seat, salve)[0]
        price = next(option for option in salve_offer['cost_options'] if cost_is(option, '{W}'))
        modes = inspect_target_hints(state, state.cards[salve], 3-seat)['modes']
        mode = next(mode for mode in modes if mode.startswith('Target player gains'))
        state = checked(state, 3-seat, {**salve_offer, 'cost_choice':{'id':price['id']},
                        'targets':{'target_player':3-seat, 'mode_text':mode}}, trace)
        state = settle(state, trace)
        assert state.players[3-seat].life == initial_life
        assert state.cards[salve].zone == Zone.GRAVEYARD
        assert not any(state.players[3-seat].mana_pool.values())
        assert state.turn == initial_turn and state.active_player == seat
    if scenario == 'next_own_turn':
        # Reach a CASTABLE later own main naturally; testing the opponent's turn
        # would make the negative vacuous for these sorceries.
        for _ in range(128):
            if (state.turn > initial_turn and state.active_player == seat
                    and state.step == Step.PRECOMBAT_MAIN and not state.stack):
                break
            assert not (state.pending_mechanic_choice or state.pending_replacement_choice
                        or state.pending_trigger_order), 'Unknown next-turn choice'
            state = checked(state, state.priority_player, {'type':'pass_priority'}, trace)
        else:
            raise AssertionError('Did not reach next own main naturally within128 actions')
        assert state.players[3-seat].life == initial_life-3
    assert state.active_player == state.priority_player == seat
    assert state.step == Step.PRECOMBAT_MAIN and not state.stack
    assert cards[name] in state.players[seat].hand
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
    assert serialize_match_snapshot(restored) == snapshot
    actual_offers = offered(state, seat, cards[name])
    assert offered(restored, seat, cards[name]) == actual_offers
    one_red = [(move, option) for move in actual_offers for option in move['cost_options']
               if cost_is(option, '{R}')]
    qualifies = scenario in ('after_damage', 'damage_then_gain')
    report = dict(name=name, seat=seat, scenario=scenario, expected_cheap_cost=qualifies,
                  initial_turn=initial_turn, actual_turn=state.turn,
                  opponent_life=state.players[3-seat].life,
                  untapped_mountains=sum(not state.cards[cid].tapped
                                          for cid in state.players[seat].battlefield),
                  own_mana_pool=dict(state.players[seat].mana_pool),
                  actual_public_offers=actual_offers, checked_precondition_actions=trace,
                  root_purity=True, json_snapshot_restore_equal=True,
                  snapshot_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest(),
                  actual_cost_id=None, card_resolution_attempted=False)
    path = tmp_path/'CASE.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    if not qualifies:
        assert not one_red, 'Spectacle must not offer one-red cost without current-turn opposing life loss'
        return
    assert len(one_red) == 1, 'Missing genuine public one-red Spectacle offer after opposing life loss'
    move, option = one_red[0]
    assert 'spectacle' in option['label'].lower()
    assert type(option['id']) is str and option['id']
    targets = {'target_player':3-seat} if name == 'Skewer the Critics' else {}
    action = {**move, 'cost_choice':{'id':option['id']}, 'targets':targets}
    paid = checked(state, seat, action, trace)
    assert cards[name] not in paid.players[seat].hand
    assert paid.stack[-1].source_card_id == cards[name]
    assert all(paid.cards[cid].tapped for cid in paid.players[seat].battlefield)
    assert not any(paid.players[seat].mana_pool.values())
    report.update(actual_cost_id=option['id'], admitted_paid_action=trace[-1],
                  admitted=True, card_resolution_attempted=False)
    path.write_text(json.dumps(report,indent=2)+'\n')

