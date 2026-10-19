"""Independent paid canonical edge cases; malformed-state cases are protocol probes."""
from copy import copy, deepcopy
import hashlib
import json

import pytest

import test_paid_exchange_desired as original
import domain_paid_support as g
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.engine import RulesEngine
from rules_engine.exchange_energy import compile_instruction


@pytest.fixture(scope='module')
def facts():
    rows = json.loads((original.HERE / 'additional-canonical.json').read_bytes())
    pins = json.loads((original.HERE / 'additional-provenance.json').read_bytes())
    old = json.loads((original.HERE / 'canonical.json').read_bytes())
    assert all(rows[name] == raw for name, raw in old.items())
    for name, raw in rows.items():
        encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == pins['cards'][name]['canonical_fullrowSHA']
    assert rows['Ornithopter']['layout'] == 'normal'
    return rows


def settle(state):
    for _ in range(24):
        if (not state.stack or state.pending_mechanic_choice or state.pending_trigger_order
                or state.pending_replacement_choice):
            return state
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Finite real priority resolution exceeded')


def paid_instant(state, facts, actor, name, pool, target):
    state = g.respond(state, actor)
    spell = g.add(state, facts, name, actor, Zone.HAND)
    state.players[actor].mana_pool = dict(pool)
    state = g.cast(state, actor, spell, target_card_id=target)
    item = next(item for item in state.stack if item.source_card_id == spell)
    assert item.payload['mana_spent'] == sum(pool.values())
    for _ in range(16):
        if state.cards[spell].zone == Zone.GRAVEYARD:
            return state
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Real paid response did not finish')


def chosen(state, source, seat, target, alternate, hidden, label):
    state = original.paid_entry(state, source, seat, label)
    option = original.target_boundary(state, source, seat, target, alternate, hidden, label)
    return checked_action(state, RulesEngine(), seat, option)


def pay(state, seat, accepted):
    move = original.public_energy_option(state, seat, accepted)
    before = serialize_match_snapshot(state)
    public = original.moves(state, seat)
    text = json.dumps(public)
    assert 'effect_payload' not in text and 'resolving_item' not in text
    assert serialize_match_snapshot(state) == before
    return checked_action(state, RulesEngine(), seat, move)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('which', ['source', 'target'])
def test_real_paid_departure_prevents_exchange_and_reward(facts, seat, which):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    private = (list(state.players[3-seat].hand), list(state.players[3-seat].library))
    label = f'edge-departure-{which}-{seat}'
    state = chosen(state, source, seat, target, alternate, hidden, label)
    departing = source if which == 'source' else target
    state = paid_instant(state, facts, seat, 'Unsummon', {'U': 1}, departing)
    assert state.cards[departing].zone == Zone.HAND
    state = settle(g.restore(state))
    assert not state.stack and not state.pending_mechanic_choice
    assert state.players[seat].counters.get('energy', 0) == 0
    remaining = target if which == 'source' else source
    assert state.cards[remaining].controller == (3-seat if which == 'source' else seat)
    assert state.players[3-seat].library == private[1]
    assert [cid for cid in state.players[3-seat].hand if cid != departing] == private[0]
    original.record(label + '-terminal', state, original_source=source, original_target=target)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('which', ['source', 'target'])
def test_real_paid_blink_does_not_exchange_old_object(facts, seat, which):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    label = f'edge-blink-{which}-{seat}'
    state = chosen(state, source, seat, target, alternate, hidden, label)
    blinked = source if which == 'source' else target
    incarnation = object_incarnation(state.cards[blinked])
    old_stack = next(item.id for item in state.stack if item.source_card_id == source)
    state = paid_instant(state, facts, seat, 'Flicker of Fate', {'C': 1, 'W': 1}, blinked)
    assert object_incarnation(state.cards[blinked]) != incarnation
    if which == 'source':
        options = original.moves(state, seat)
        choice = next(move for move in options if move['type'] == 'choose_trigger_target'
                      and move['target_card_id'] == alternate)
        state = checked_action(state, RulesEngine(), seat, choice)
        state = settle(state)
        state = pay(state, seat, False)
        assert state.players[seat].counters['energy'] == 4
    state = settle(g.restore(state))
    assert not any(item.id == old_stack for item in state.stack)
    assert state.cards[target].controller == 3-seat
    assert state.players[seat].counters.get('energy', 0) == (4 if which == 'source' else 0)
    original.record(label + '-terminal', state, old_stack=old_stack, old_incarnation=incarnation)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_control_change_makes_exchange_impossible(facts, seat):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    label = f'edge-control-{seat}'
    state = chosen(state, source, seat, target, alternate, hidden, label)
    state = paid_instant(state, facts, 3-seat, 'Ray of Command', {'C': 3, 'U': 1}, source)
    assert state.cards[source].controller == state.cards[target].controller == 3-seat
    state = settle(g.restore(state))
    assert state.cards[target].controller == 3-seat
    assert state.players[seat].counters.get('energy', 0) == 0
    assert not state.pending_mechanic_choice
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('accepted', [False, True])
def test_zero_value_is_a_real_optional_payment(facts, seat, accepted):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat, 'Ornithopter')
    label = f'edge-zero-{accepted}-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    state = pay(g.restore(state), seat, accepted)
    assert state.players[seat].counters['energy'] == 4
    assert state.cards[target].zone == (Zone.BATTLEFIELD if accepted else Zone.GRAVEYARD)
    assert state.cards[source].controller == 3-seat
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
def test_sacrifice_indestructible_acquired_creature(facts, seat):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat, 'Avacyn, Angel of Hope')
    label = f'edge-indestructible-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    state = pay(state, seat, False)
    assert state.cards[target].zone == Zone.GRAVEYARD and target in state.players[3-seat].graveyard
    assert state.players[seat].counters['energy'] == 4
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_static_player_prohibition_does_not_undo_exchange(facts, seat):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    g.add(state, facts, 'Solemnity', 3-seat)
    assert counter_placement_forbidden(state, 'energy', target_player=seat)
    label = f'edge-player-prohibition-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    assert state.cards[target].controller == seat and state.cards[source].controller == 3-seat
    assert state.players[seat].counters.get('energy', 0) == 0
    assert state.pending_mechanic_choice['options'] == ['decline']
    state = pay(state, seat, False)
    assert target in state.players[3-seat].graveyard
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_static_suppression_prevents_trigger(facts, seat):
    state, source, target, _, _, _, _ = original.position(facts, seat)
    g.add(state, facts, 'Humility', 3-seat)
    label = f'edge-suppression-{seat}'
    state = settle(original.paid_entry(state, source, seat, label))
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].controller == seat and state.cards[target].controller == 3-seat
    assert not state.stack and not state.pending_trigger_order
    assert state.players[seat].counters.get('energy', 0) == 0
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['Winding Constrictor', 'Vorinclex, Monstrous Raider'])
def test_real_counter_replacement_restart_keeps_exchange_once(facts, seat, first):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    modifiers = {name: g.add(state, facts, name, seat)
                 for name in ('Winding Constrictor', 'Vorinclex, Monstrous Raider')}
    private = (list(state.players[3-seat].hand), list(state.players[3-seat].library))
    label = f'edge-replacement-{first}-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    assert state.pending_replacement_choice
    assert state.players[seat].counters.get('energy', 0) == 0
    assert state.cards[source].controller == 3-seat and state.cards[target].controller == seat
    pending = deepcopy(state.pending_replacement_choice)
    assert pending['counter_payload']['target_card_id'] is None
    assert pending['counter_payload']['__exchange_target_id'] == target
    assert pending['counter_payload']['__exchange_phase'] == 'energy'
    assert pending['resolving_item']['source_card_id'] == source
    selected = next(option['source_id'] for option in pending['options']
                    if option['source_id'].startswith(modifiers[first] + ':'))
    state = g.act(g.restore(state), seat, 'choose_replacement', replacement_source_id=selected)
    reward = 10 if first == 'Winding Constrictor' else 9
    assert state.players[seat].counters['energy'] == reward
    assert sum('gains control of' in line for line in state.log) == 2
    state = pay(g.restore(state), seat, True)
    assert state.players[seat].counters['energy'] == reward - 1
    assert state.cards[target].zone == Zone.BATTLEFIELD and not state.stack
    assert (state.players[3-seat].hand, state.players[3-seat].library) == private
    original.record(label + '-terminal', state, original_pending=pending)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_creature_counter_prohibition_does_not_block_player_energy(facts, seat):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    suncleanser = g.add(state, facts, 'Suncleanser', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = g.cast(state, seat, suncleanser)
    assert next(item for item in state.stack if item.source_card_id == suncleanser).payload['mana_spent'] == 2
    for _ in range(16):
        if state.cards[suncleanser].zone == Zone.BATTLEFIELD:
            break
        state = g.act(state, state.priority_player, 'pass_priority')
    assert state.cards[suncleanser].zone == Zone.BATTLEFIELD
    offered = original.moves(state, seat)
    choices = [(move, option) for move in offered if move['type'] == 'choose_mechanic'
               for option in move.get('options', [])
               if str(move.get('option_labels', {}).get(option, '')).startswith('Remove all counters from target creature')]
    assert len(choices) == 1
    state = g.act(state, seat, 'choose_mechanic', choice_id=choices[0][1])
    option = next(move for move in original.moves(state, seat)
                  if move['type'] == 'choose_trigger_target' and move.get('target_card_id') == target)
    state = settle(checked_action(state, RulesEngine(), seat, option))
    assert counter_placement_forbidden(state, 'energy', target_card_id=target)
    assert not counter_placement_forbidden(state, 'energy', target_player=seat)
    label = f'edge-creature-prohibition-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    assert state.players[seat].counters['energy'] == 4
    state = pay(g.restore(state), seat, True)
    assert state.players[seat].counters['energy'] == 3 and state.cards[target].zone == Zone.BATTLEFIELD
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_source_departure_after_success_keeps_reward(facts, seat):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    label = f'edge-after-success-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    state = pay(state, seat, True)
    assert state.players[seat].counters['energy'] == 3
    state = paid_instant(state, facts, seat, 'Lightning Bolt', {'R': 1}, source)
    state = settle(g.restore(state))
    assert state.cards[source].zone == Zone.GRAVEYARD and source in state.players[seat].graveyard
    assert state.cards[target].zone == Zone.BATTLEFIELD and state.cards[target].controller == seat
    assert state.players[seat].counters['energy'] == 3
    original.record(label + '-terminal', state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [True, -1, '1', None, 1_000_001])
def test_malformed_balance_protocol_rejects_without_mutation(facts, seat, bad):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    label = f'edge-balance-{bad!r}-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    state.players[seat].counters['energy'] = bad
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, seat, 'choose_mechanic', choice_id='pay')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unaffordable_payment_protocol_uses_sacrifice(facts, seat):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    label = f'edge-unaffordable-protocol-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    # Protocol robustness only: no priority window exists during the real choice.
    state.players[seat].counters['energy'] = 0
    state = g.act(state, seat, 'choose_mechanic', choice_id='pay')
    assert state.cards[target].zone == Zone.GRAVEYARD and target in state.players[3-seat].graveyard
    assert state.players[seat].counters['energy'] == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [True, -1, '1', None, 1_000_001])
def test_malformed_payment_count_rejects_without_mutation(facts, seat, bad):
    state, source, target, alternate, _, _, hidden = original.position(facts, seat)
    label = f'edge-malformed-{bad!r}-{seat}'
    state = settle(chosen(state, source, seat, target, alternate, hidden, label))
    state.pending_mechanic_choice['effect_payload']['energy_cost'] = bad
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, seat, 'choose_mechanic', choice_id='pay')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [' Unknown instruction.', '\nDraw a card.', ' Then gain 7 life.',
                                 '\nWhen this creature dies, draw a card.'])
def test_complete_unknown_suffix_is_compiler_only_fail_closed(facts, seat, tail):
    state, source, _, _, _, _, _ = original.position(facts, seat)
    raw = deepcopy(facts)
    proxy = copy(state.cards[source])
    proxy.oracle_text += tail
    key, payload = compile_instruction(proxy, seat)
    assert key == 'noop' and payload == {'__unsupported_instruction': proxy.oracle_text}
    assert facts == raw and state.cards[source].oracle_text == facts[original.SOURCE]['oracle_text']
