"""Paid native controls and exact old-producer captures, not invented Oracle."""
import hashlib
import json

import pytest

import domain_paid_support as g
import test_paid_exchange_desired as original
import test_exchange_edges as edges
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind


@pytest.fixture(scope='module')
def facts():
    rows = json.loads((original.HERE / 'qualifier-canonical.json').read_bytes())
    pins = json.loads((original.HERE / 'qualifier-provenance.json').read_bytes())
    for name, raw in rows.items():
        body = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(body).hexdigest() == pins['cards'][name]['canonical_fullrowSHA']
    return rows


def paid_permanent(state, facts, seat, name, pool, **targets):
    source = g.add(state, facts, name, seat, Zone.HAND)
    state.players[seat].mana_pool = dict(pool)
    state = g.cast(state, seat, source, **targets)
    item = next(item for item in state.stack if item.source_card_id == source)
    assert item.payload['mana_spent'] == sum(pool.values())
    assert stack_object_kind(state, item) == 'spell'
    state = edges.settle(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    return state, source


def activation(state, seat, source, target):
    public = original.moves(state, seat)
    options = [move for move in public if move['type'] == 'activate_ability'
               and move.get('card_id') == source]
    assert len(options) == 1
    return {'type': 'activate_ability', 'card_id': source,
            'ability_index': options[0]['ability_index'], 'targets': {'target_card_id': target}}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['protected', 'own', 'suppressed'])
def test_real_paid_rod_activation_target_boundary_and_resolution(facts, seat, case):
    state = g.position(facts, seat)
    target = g.add(state, facts, original.SOURCE, seat if case == 'own' else 3-seat)
    lawful = g.add(state, facts, 'Raging Goblin', 3-seat)
    if case == 'suppressed':
        state, _ = paid_permanent(state, facts, seat, 'Humility', {'C': 2, 'W': 2})
    state, source = paid_permanent(state, facts, seat, 'Rod of Ruin', {'C': 4})
    state.players[seat].mana_pool = {'C': 3}
    private = (list(state.players[3-seat].hand), list(state.players[3-seat].library))
    action = activation(state, seat, source, target)
    before = serialize_match_snapshot(state)
    if case == 'protected':
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, action)
        assert serialize_match_snapshot(state) == before
        action['targets']['target_card_id'] = lawful
    paid = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    assert paid.cards[source].tapped and sum(paid.players[seat].mana_pool.values()) == 0
    item = next(item for item in paid.stack if item.source_card_id == source)
    assert stack_object_kind(paid, item) == 'activated' and item.controller == seat
    terminal = edges.settle(g.restore(paid))
    assert not terminal.stack
    if case == 'protected':
        assert terminal.cards[target].zone == Zone.BATTLEFIELD
        assert terminal.cards[lawful].zone == Zone.GRAVEYARD
    elif case == 'own':
        assert terminal.cards[target].zone == Zone.BATTLEFIELD
        assert terminal.cards[target].counters['__damage_marked'] == 1
    else:
        assert terminal.cards[target].zone == Zone.GRAVEYARD
    assert (terminal.players[3-seat].hand, terminal.players[3-seat].library) == private
    original.record(f'qualifier-rod-{case}-{seat}', terminal, paid=3, action=action)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_ballista_cost_departure_keeps_actual_ability_kind(facts, seat):
    state = g.position(facts, seat)
    target = g.add(state, facts, original.SOURCE, seat)
    state, source = paid_permanent(state, facts, seat, 'Walking Ballista', {'C': 2}, x_value=1)
    assert state.cards[source].counters['+1/+1'] == 1
    state = checked_action(state, RulesEngine(), seat, activation(state, seat, source, target))
    assert state.cards[source].zone == Zone.GRAVEYARD
    item = next(item for item in state.stack if item.source_card_id == source)
    assert stack_object_kind(state, item) == 'activated'
    state = g.restore(state)
    assert stack_object_kind(state, state.stack[-1]) == 'activated'
    state = edges.settle(state)
    assert state.cards[target].counters['__damage_marked'] == 1 and not state.stack
    original.record(f'qualifier-ballista-departure-{seat}', state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['spell', 'activation'])
def test_load_exact_actual_old_native_capture_and_resume(seat, kind):
    directory = original.HERE / 'old-producer-captures'
    proof = json.loads((directory / 'provenance.json').read_bytes())
    filename = f'old-native-{kind}-{seat}.json'
    pin = next(record for record in proof['records'] if record['file'] == filename)
    raw = (directory / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin['sha256']
    packet = json.loads(raw)
    state = deserialize_match_snapshot(packet['snapshot'])
    item = next(item for item in state.stack if item.id == pin['actual_item_id'])
    assert '__announced_stack_kind' not in item.payload
    assert stack_object_kind(state, item) == ('spell' if kind == 'spell' else 'activated')
    source = item.source_card_id
    if kind == 'activation':
        assert state.cards[source].zone == Zone.GRAVEYARD
        target = item.payload['target_card_id']
    state = edges.settle(state)
    assert not state.stack
    if kind == 'spell':
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert state.cards[source].counters['+1/+1'] == 1
    else:
        assert state.cards[target].zone == Zone.GRAVEYARD
    original.record(f'qualifier-actual-old-{kind}-{seat}', state, input_sha=pin['sha256'])


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_spell_copy_opponent_qualified_hexproof_is_lawful(facts, seat):
    state = g.position(facts, seat)
    protected = g.add(state, facts, original.SOURCE, seat)
    target = g.add(state, facts, 'Raging Goblin', 3-seat)
    source = g.add(state, facts, 'Lightning Bolt', seat, Zone.HAND)
    state.players[seat].mana_pool = {'R': 1}
    state = g.cast(state, seat, source, target_card_id=target)
    original_item = state.stack[-1].id
    state = g.respond(state, 3-seat)
    copier = g.add(state, facts, 'Reverberate', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'R': 2}
    state = g.cast(state, 3-seat, copier, target_stack_id=original_item)
    assert state.stack[-1].payload['mana_spent'] == 2
    state = edges.settle(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    copied = next(item for item in state.stack if item.payload.get('__stack_copy_kind'))
    assert copied.controller == 3-seat and stack_object_kind(state, copied) == 'spell'
    assert state.cards[source].controller == seat
    public = original.moves(state, 3-seat)
    options = [option for move in public if move['type'] == 'choose_mechanic'
               for option in move.get('options', []) if option.endswith(':' + protected)]
    assert len(options) == 1
    state = g.act(g.restore(state), 3-seat, 'choose_mechanic', card_ids=options)
    state = edges.settle(state)
    assert state.cards[protected].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.GRAVEYARD and not state.stack
    original.record(f'qualifier-spell-copy-{seat}', state, offered=public)
