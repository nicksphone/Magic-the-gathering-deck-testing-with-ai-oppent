"""Desired paired-kicker contracts: real canonical payments; metadata probes labeled."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from api_contracts import CostChoice
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.costs import collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.continuous import has_keyword
from rules_engine.move_generator import _cost_option_view
from rules_engine.targeting import stack_object_kind
import domain_paid_support as g

ROOT = Path(__file__).parent / 'fixtures/archangel_pair'
ROWS = {x['name']: x for x in (json.loads(p.read_text()) for p in ROOT.glob('*.json'))}
RULES = RulesEngine()
CHOICES = [('base', 0, ()), ('kicker_1', 1, ('B',)),
           ('kicker_2', 1, ('R',)), ('kicker_1_2', 2, ('B', 'R'))]

def act(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RULES, seat, action)
    assert serialize_match_snapshot(state) == before
    return result

def cold(state):
    packet = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(json.loads(json.dumps(packet)))
    assert serialize_match_snapshot(restored) == packet
    return restored

def setup(seat):
    state = g.position(ROWS, seat)
    source = g.add(state, ROWS, 'Archangel of Wrath', seat, Zone.HAND)
    return state, source

def advance(state, predicate):
    for _ in range(128):
        if predicate(state):
            return state
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        assert not state.pending_trigger_order, 'Choose actual offered trigger actions explicitly'
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('128 actual priority actions exceeded boundary')

def targets(state, seat, target):
    for _ in range(12):
        if not state.pending_trigger_order:
            return state
        actor = state.pending_trigger_order['current_controller']
        moves = RULES.legal_moves(state, actor)
        if state.pending_trigger_order.get('phase') == 'targets':
            move = next(m for m in moves if m['type'] == 'choose_trigger_target'
                        and all(m.get(k) == v for k, v in target.items()))
        else:
            move = next(m for m in moves if m['type'] == 'choose_trigger_order')
        state = act(state, actor, deepcopy(move))
    raise AssertionError('12 actual target/order choices exceeded boundary')

def cast_pair(state, source, seat, choice, count, paid):
    state.players[seat].mana_pool = {'C': 2, 'W': 2, 'B': 1, 'R': 1}
    menu = [_cost_option_view(option, state, seat, source)
            for option in collect_cost_options(state, seat, state.cards[source])]
    assert {row['id'] for row in menu} == {row[0] for row in CHOICES}
    assert len(menu) == 4
    public = CostChoice(id=choice).model_dump(exclude_none=True)
    assert public == {'id': choice} and 'kicker_count' not in public
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source,
                              'cost_choice': public, 'targets': {}})
    assert state.players[seat].mana_pool.get('C', 0) == 0
    assert state.players[seat].mana_pool.get('W', 0) == 0
    for symbol in ('B', 'R'):
        assert state.players[seat].mana_pool.get(symbol, 0) == (0 if symbol in paid else 1)
    assert state.cards[source].zone == Zone.STACK
    item = next(i for i in state.stack if i.source_card_id == source)
    assert item.payload['__kicker_count'] == count
    assert item.payload['__kicked'] is (count > 0)
    assert state.cards[source].kicker_count == count
    assert state.cards[source].was_kicked is (count > 0)
    return cold(state), item.id

def enter(state, source, seat, count, spell, target):
    state = advance(state, lambda s: all(i.id != spell for i in s.stack))
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].kicker_count == count
    assert state.cards[source].was_kicked is (count > 0)
    assert has_keyword(state, source, 'flying') and has_keyword(state, source, 'lifelink')
    if count:
        assert state.pending_trigger_order
        queued = [item for group in state.pending_trigger_order.get('groups', {}).values()
                  for item in group if item['source_card_id'] == source]
        assert len(queued) + sum(i.source_card_id == source for i in state.stack) == count
    state = targets(cold(state), seat, target)
    entries = [i for i in state.stack if i.source_card_id == source]
    assert len(entries) == count
    assert all(stack_object_kind(state, i) == 'triggered' and i.effect_key == 'deal_damage'
               and i.payload['amount'] == 2 for i in entries)
    assert state.players[seat].life == state.players[3-seat].life == 20
    return cold(state), [i.id for i in entries]

def response(state, seat, name, pool, target):
    cid = g.add(state, ROWS, name, seat, Zone.HAND)
    state.players[seat].mana_pool = pool
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    state = act(state, seat, {'type': 'cast_spell', 'card_id': cid,
                              'cost_choice': {'id': 'base'}, 'targets': target})
    assert sum(state.players[seat].mana_pool.values()) == 0
    frame = next(i.id for i in state.stack if i.source_card_id == cid)
    return advance(state, lambda s: all(i.id != frame for i in s.stack))

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice,count,paid', CHOICES)
def test_real_public_payment_independent_etbs_and_lifelink(seat, choice, count, paid):
    state, source = setup(seat)
    state, spell = cast_pair(state, source, seat, choice, count, paid)
    state, entries = enter(state, source, seat, count, spell, {'target_player': 3-seat})
    state = targets(state, seat, {'target_player': 3-seat})
    state = advance(cold(state), lambda s: not s.stack)
    assert state.players[3-seat].life == 20 - 2 * count
    assert state.players[seat].life == 20 + 2 * count
    assert state.cards[source].kicker_count == count

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('episode', ['source-bounce', 'target-bounce', 'trigger-counter', 'blink-reset'])
def test_actual_paid_responses_retained_count_and_independent_targets(seat, episode):
    state, source = setup(seat)
    victim = g.add(state, ROWS, 'Wall of Omens', 3-seat, Zone.BATTLEFIELD)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state, entries = enter(state, source, seat, 2, spell,
                           {'target_card_id': victim} if episode == 'target-bounce'
                           else {'target_player': 3-seat})
    state = targets(state, seat, {'target_card_id': victim} if episode == 'target-bounce'
                    else {'target_player': 3-seat})
    if episode == 'trigger-counter':
        state = response(state, 3-seat, 'Stifle', {'U': 1}, {'target_stack_id': entries[-1]})
        assert sum(i.id in entries for i in state.stack) == 1
    elif episode == 'blink-reset':
        old = object_incarnation(state.cards[source])
        state = response(state, seat, 'Flicker of Fate', {'C': 1, 'W': 1}, {'target_card_id': source})
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert object_incarnation(state.cards[source]) != old
        assert state.cards[source].kicker_count is None and not state.cards[source].was_kicked
        assert {i.id for i in state.stack} == set(entries)
    else:
        cid = victim if episode == 'target-bounce' else source
        state = response(state, 3-seat, 'Unsummon', {'U': 1}, {'target_card_id': cid})
        assert state.cards[cid].zone == Zone.HAND
        if cid == source:
            assert state.cards[source].kicker_count is None and not state.cards[source].was_kicked
    state = advance(cold(state), lambda s: not s.stack)
    damage = 0 if episode == 'target-bounce' else 2 if episode == 'trigger-counter' else 4
    assert state.players[3-seat].life == 20 - damage
    assert state.players[seat].life == 20 + damage

@pytest.mark.parametrize('seat', [1, 2])
def test_actual_countered_cast_has_no_entry_reward_and_resets_count(seat):
    state, source = setup(seat)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state = response(state, 3-seat, 'Essence Scatter', {'C': 1, 'U': 1}, {'target_stack_id': spell})
    assert not state.stack and state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[source].kicker_count is None and not state.cards[source].was_kicked
    assert state.players[seat].life == state.players[3-seat].life == 20

@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_spell_copy_retains_count_without_second_kicker_payment(seat):
    state, source = setup(seat)
    engine = g.add(state, ROWS, 'Lithoform Engine', seat, Zone.BATTLEFIELD)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state.players[seat].mana_pool = {'C': 4}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine, 'ability_index': 2,
                              'targets': {'target_stack_id': spell}})
    assert state.cards[engine].tapped and sum(state.players[seat].mana_pool.values()) == 0
    for _ in range(128):
        if not state.stack and not state.pending_trigger_order:
            break
        if state.pending_trigger_order:
            state = targets(state, seat, {'target_player': 3-seat})
        else:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
    else:
        raise AssertionError('128 actual copied-spell priority actions exceeded boundary')
    angels = [c for c in state.cards.values() if c.zone == Zone.BATTLEFIELD and c.name == ROWS['Archangel of Wrath']['name']]
    assert len(angels) == 2 and sum(c.is_token for c in angels) == 1
    assert all(c.kicker_count == 2 and c.was_kicked for c in angels)
    assert state.players[seat].life == 28 and state.players[3-seat].life == 12
    assert state.kicked_spells_cast_this_turn[seat] == 1

@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_permanent_token_copy_does_not_inherit_cast_payment(seat):
    state, source = setup(seat)
    state, spell = cast_pair(state, source, seat, 'kicker_1_2', 2, ('B', 'R'))
    state, _ = enter(state, source, seat, 2, spell, {'target_player': 3-seat})
    state = targets(state, seat, {'target_player': 3-seat})
    state = advance(state, lambda s: not s.stack)
    state = response(state, seat, 'Cackling Counterpart', {'C': 1, 'U': 2}, {'target_card_id': source})
    assert not state.stack and not state.pending_trigger_order
    copies = [c for c in state.cards.values() if c.is_token and c.name == ROWS['Archangel of Wrath']['name'] and c.zone == Zone.BATTLEFIELD]
    assert len(copies) == 1 and copies[0].kicker_count is None and not copies[0].was_kicked
    assert state.players[seat].life == 24 and state.players[3-seat].life == 16

# Detached snapshot mutations below are schema diagnostics, not played episodes.
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count,was', [(None, False), (True, True), (False, False), ('2', True),
    (2.0, True), (-1, False), (3, True), (0, True), (1, False), (2, False)])
def test_diagnostic_explicit_count_requires_exact_int_and_boolean_consistency(seat, count, was):
    state, source = setup(seat)
    packet = serialize_match_snapshot(state)
    packet['cards'][source]['kicker_count'] = count
    packet['cards'][source]['was_kicked'] = was
    with pytest.raises(ValueError):
        deserialize_match_snapshot(packet)

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('was', [False, True])
def test_diagnostic_legacy_absence_is_not_explicit_zero(seat, was):
    state, source = setup(seat)
    packet = serialize_match_snapshot(state)
    packet['cards'][source].pop('kicker_count', None)
    packet['cards'][source]['was_kicked'] = was
    restored = deserialize_match_snapshot(packet)
    assert restored.cards[source].kicker_count is None and restored.cards[source].was_kicked is was
    assert 'kicker_count' not in serialize_match_snapshot(restored)['cards'][source]

@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('count,was', [(0, False), (1, True), (2, True)])
def test_diagnostic_explicit_count_roundtrip_is_lossless(seat, count, was):
    state, source = setup(seat)
    packet = serialize_match_snapshot(state)
    packet['cards'][source]['kicker_count'] = count
    packet['cards'][source]['was_kicked'] = was
    restored = deserialize_match_snapshot(packet)
    assert type(restored.cards[source].kicker_count) is int and restored.cards[source].kicker_count == count
    assert restored.cards[source].was_kicked is was
    assert serialize_match_snapshot(restored)['cards'][source]['kicker_count'] == count
