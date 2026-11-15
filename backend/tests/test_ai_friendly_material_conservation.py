"""Full canonical compound-removal components; no game replay or trained model."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random

import pytest

from ai.agent import AIAgent
from ai import pending_effects
from ai.pending_effects import friendly_destruction_profit
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_ai_recurring_engines import fixture, add
from tests.test_ai_own_only_sweeper import own_only_pose, RAW
from tests.test_linked_damage_targets import raw_card
from tests.test_any_player_cast_damage import settle


DATA = Path(__file__).parent/'fixtures/knowledge_profiles/seed155-scryfall.jsonl'
encoded = DATA.read_bytes()
assert sha256(encoded).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
CARDS = {r['name']: r for r in map(json.loads, encoded.splitlines())}


def position(seat, body, enemy=False):
    state = fixture()
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        player.life = 20
        player.mana_pool = {c: 0 for c in 'WUBRGC'}
    for _ in range(4): raw_card(state, CARDS['Plains'], seat, Zone.BATTLEFIELD)
    target = raw_card(state, CARDS[body], seat, Zone.BATTLEFIELD)
    target.summoning_sick = False
    spell = raw_card(state, CARDS['Lay Down Arms'], seat, Zone.HAND)
    other = raw_card(state, CARDS['Recruitment Officer'], 3-seat, Zone.BATTLEFIELD) if enemy else None
    move = next(m for m in RulesEngine().legal_moves(state, seat) if m.get('card_id') == spell.id)
    move = {**move, 'targets': {'target_card_id': target.id}}
    return state, move, target.id, other.id if other else None


def unchanged(state, original, rng, local):
    assert serialize_match_snapshot(state) == original
    assert random.getstate() == rng and state.rng.getstate() == local


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('body', ['Recruitment Officer', 'Thalia, Guardian of Thraben'])
def test_whole_compound_plain_life_does_not_compensate_healthy_material(seat, body):
    state, move, target, _ = position(seat, body)
    before, rng, local = serialize_match_snapshot(state), random.getstate(), state.rng.getstate()
    key, payload = infer_effect_from_oracle(state, state.cards[move['card_id']], seat, move['targets'])
    assert key == 'effect_sequence'
    assert [x['effect_key'] for x in payload['effects']] == ['exile', 'gain_life']
    result = settle(checked_action(state, RulesEngine(), seat, move))
    assert result.cards[target].zone == Zone.EXILE and result.players[seat].life == 23
    assert friendly_destruction_profit(state, seat, move) is False
    unchanged(state, before, rng, local)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enemy', [False, True])
def test_compound_materializer_rejects_or_retargets_without_rewriting_effects(seat, enemy):
    state, move, target, other = position(seat, 'Recruitment Officer', enemy)
    before, rng, local = serialize_match_snapshot(state), random.getstate(), state.rng.getstate()
    offered = deepcopy(move)
    action = AIAgent('master', 'Aggro')._materialize_action(state, move, seat)
    if enemy:
        assert not action.get('_invalid_ai_choice') and action['targets']['target_card_id'] == other
    else:
        assert action.get('_invalid_ai_choice') is True
    assert move == offered
    unchanged(state, before, rng, local)


@pytest.mark.parametrize('seat', [1, 2])
def test_known_four_life_rescue_precedes_material_comparison(seat):
    state, _ = own_only_pose(seat)
    state.players[seat].life = 4
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type': 'pass_priority'})
    for _ in range(2):
        burn = add(state, 'Skullcrack', 3-seat, Zone.HAND, cards=RAW)
        state = checked_action(state, rules, 3-seat, {'type':'cast_spell','card_id':burn.id,
                                                  'targets':{'target_player':seat}})
    state = checked_action(state, rules, 3-seat, {'type':'pass_priority'})
    assert settle(deepcopy(state)).winner == 3-seat
    sword = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Swords to Plowshares')
    body = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Cosmos Charger')
    action = dict(type='cast_spell',card_id=sword,targets={'target_card_id':body})
    before = serialize_match_snapshot(state)
    assert friendly_destruction_profit(state, seat, action) is True
    assert settle(checked_action(state, rules, seat, action)).winner is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_creature_already_lost_in_baseline_is_not_extra_material_loss(seat):
    state, _ = own_only_pose(seat)
    officer = raw_card(state, CARDS['Recruitment Officer'], seat, Zone.BATTLEFIELD)
    burn = add(state, 'Skullcrack', 3-seat, Zone.HAND, cards=RAW)
    # Use the full canonical Lightning Bolt for a genuinely doomed creature.
    state.players[3-seat].hand.remove(burn.id)
    state.players[3-seat].library.append(burn.id); state.cards[burn.id].move_to_zone(Zone.LIBRARY)
    bolt = raw_card(state, CARDS['Lightning Bolt'], 3-seat, Zone.HAND)
    rules = RulesEngine()
    state = checked_action(state, rules, seat, {'type':'pass_priority'})
    state = checked_action(state, rules, 3-seat, {'type':'cast_spell','card_id':bolt.id,
                                                'targets':{'target_card_id':officer.id}})
    state = checked_action(state, rules, 3-seat, {'type':'pass_priority'})
    assert settle(deepcopy(state)).cards[officer.id].zone == Zone.GRAVEYARD
    sword = next(cid for cid in state.players[seat].hand if state.cards[cid].name == 'Swords to Plowshares')
    before = serialize_match_snapshot(state)
    assert friendly_destruction_profit(state, seat,
        dict(type='cast_spell',card_id=sword,targets={'target_card_id':officer.id})) is True
    assert serialize_match_snapshot(state) == before


def test_unknown_characteristics_are_unknown_not_zero_or_an_exception():
    # Explicit synthetic public-characteristic protocol, not a shortened printing.
    state, _, _, _ = position(1, 'Recruitment Officer')
    card = CardInstance(id=state.allocate_object_id(), name='SYNTHETIC unknown characteristics',
                        owner=1, controller=1, zone=Zone.BATTLEFIELD, types=['Creature'])
    state.cards[card.id] = card; state.players[1].battlefield.append(card.id)
    assert pending_effects._public_destruction_material(state, 1) is None


def test_baseline_keeps_three_tuple_abi_and_settled_incarnation_summary():
    state, _, target, _ = position(1, 'Recruitment Officer')
    result = pending_effects._destruction_baseline(state, 1, None)
    status, winner, value = result
    assert isinstance(result, tuple) and len(result) == 3
    assert status == 'known' and winner is None and isinstance(value, float)
    summary = result.public_material
    key = next(k for k in summary['boards'][1] if k[0] == target)
    assert key in summary['useful'] and len(key) == 3
    copied = deepcopy(result)
    assert tuple(copied) == tuple(result) and copied.public_material == summary


@pytest.mark.parametrize('compensation', ['saved_asset', 'enemy_removed', 'mana', 'card', 'counter', 'untap', 'reentry'])
def test_synthetic_settled_compensation_is_not_rejected_as_plain_life(compensation):
    state, _, target, _ = position(1, 'Recruitment Officer', True)
    before = pending_effects._public_destruction_material(state, 1)
    after = deepcopy(before)
    key = next(k for k in after['boards'][1] if k[0] == target)
    del after['boards'][1][key]; after['life'][1] += 3
    assert pending_effects._uncompensated_life_material_loss(before, after, 1, 'spell') is True
    if compensation in {'saved_asset','reentry'}:
        newkey = ('saved-public-object', 1, 1) if compensation == 'saved_asset' else (key[0], key[1]+1, key[2]+2)
        after['boards'][1][newkey] = before['boards'][1][key]
    elif compensation == 'enemy_removed': after['boards'][2].clear()
    elif compensation == 'mana': after['mana'][1]['W'] += 1
    elif compensation == 'card': after['hand'].add('known-returned-card')
    elif compensation == 'counter': after['resources'][1][1]['energy'] = 1
    else:
        land = next(k for k in before['boards'][1] if k != key)
        traits, _ = before['boards'][1][land]
        before['boards'][1][land] = (traits, True)
        after['boards'][1][land] = (traits, False)
    assert pending_effects._uncompensated_life_material_loss(before, after, 1, 'spell') is False


def test_typed_wrapper_bounds_and_unknowns_abstain_without_partial_actions():
    agent = AIAgent(); leaf = dict(effect_key='exile', payload={'target_card_id':'own'})
    sequence = dict(effects=[leaf,dict(effect_key='gain_life',payload={'amount':3})])
    original = deepcopy(sequence)
    assert agent._friendly_removal_instruction('effect_sequence', sequence, 'own') is True
    assert agent._friendly_removal_instruction('effect_sequence', sequence, 'foreign') is False
    assert sequence == original
    for child in [dict(effect_key='unknown_future',payload={}), None]:
        assert agent._friendly_removal_instruction('effect_sequence', {'effects':[leaf,child]}, 'own') is None
    assert agent._friendly_removal_instruction('effect_sequence', {'effects':[leaf]*17}, 'own') is None
    deep = leaf
    for _ in range(8): deep = dict(effect_key='effect_sequence',payload={'effects':[deep]})
    assert agent._friendly_removal_instruction(deep['effect_key'],deep['payload'],'own') is None
    known = dict(condition='permanent_departure',effect_key='destroy_permanent',normal=2,enhanced=4,target_card_id='own')
    assert agent._friendly_removal_instruction('conditional_instruction', known, 'own') is True
    assert agent._friendly_removal_instruction('conditional_instruction', dict(known,condition='unknown'), 'own') is None


def test_typed_wrapper_stops_before_unbounded_or_after_unknown_children():
    # Synthetic traversal instrumentation, never native Oracle or effect data.
    class MustNotVisit(dict):
        def get(self, *args):
            raise AssertionError('Visited beyond the declared recognition frontier')
    agent = AIAgent()
    tail = MustNotVisit(effect_key='exile', payload={'target_card_id':'own'})
    assert agent._friendly_removal_instruction('effect_sequence', {'effects':[tail]*17}, 'own') is None
    assert agent._friendly_removal_instruction('effect_sequence', {'effects':[
        dict(effect_key='unknown',payload={}),tail]}, 'own') is None


@pytest.mark.parametrize('positive', [False, True])
def test_synthetic_unavailable_optional_summary_cannot_erase_known_negative(positive):
    # Protocol: unavailable optional data (e.g. unrelated delayed trigger/emblem),
    # not an invented native delayed event or unknown scalar utility.
    if positive:
        state, action, _, _ = position(1, 'Recruitment Officer')
    else:
        state, _ = own_only_pose(1)
        state.players[1].life = 20
        spell = next(cid for cid in state.players[1].hand if state.cards[cid].name == 'Swords to Plowshares')
        target = next(cid for cid in state.players[1].battlefield if state.cards[cid].name == 'Cosmos Charger')
        action = dict(type='cast_spell',card_id=spell,targets={'target_card_id':target})
    native = pending_effects._destruction_baseline(state, 1, None)
    receipt = pending_effects._DestructionBaseline(tuple(native), None)
    result = pending_effects._friendly_destruction_profit(state, 1, action,
        _baseline_supplier=lambda: receipt)
    assert result is (None if positive else False)
