"""Favor-only canonical retained positions and real paid response episodes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from ai.information import decision_view, is_unknown
from game_state.state import Zone, object_incarnation
from game_state.serializers import serialize_match
from game_state.observations import remembered_hand_card
from rules_engine.continuous import effective_keywords
from rules_engine.engine import RulesEngine
from tests.test_library_reorder import setup as library_position
from tests.scheduler_fixture_position import ordinary_position
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import act, restart, snap

FIXTURES = Path(__file__).parent / 'fixtures/favor_target_lifecycle'
ROWS = {}
for entry in json.loads((FIXTURES / 'provenance.json').read_text())['cards']:
    data = (FIXTURES / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    row = json.loads(data)
    assert row['object'] == 'card' and row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row
FAVOR_PATH = FIXTURES.parent / 'targeted_search/fertilids-favor.json'
FAVOR = json.loads(FAVOR_PATH.read_text())
FAVOR_PROVENANCE = json.loads(FAVOR_PATH.with_name('provenance.json').read_text())
assert hashlib.sha256(FAVOR_PATH.read_bytes()).hexdigest() == next(
    row['sha256'] for row in FAVOR_PROVENANCE['cards'] if row['name'] == FAVOR['name'])
RESPONSES = {'unsummon': ('Unsummon', 'U'), 'bolt': ('Lightning Bolt', 'R'),
             'veil': ('Snakeskin Veil', 'G'), 'blink': ('Cloudshift', 'W')}


def position(seat, mode='none', eligible=True):
    # Explicit canonical retained position, never historical repair.
    state, _ = library_position('Index', seat, size=8)
    ordinary_position(state)
    state.mechanic_choice_players = {1, 2}
    affected = 3-seat
    creature = raw_card(state, ROWS['Grizzly Bears'], affected, Zone.BATTLEFIELD)
    favor = raw_card(state, FAVOR, seat, Zone.HAND)
    response = None
    if mode in RESPONSES:
        name, color = RESPONSES[mode]
        response = raw_card(state, ROWS[name], affected, Zone.HAND)
        state.players[affected].mana_pool = {color: 1}
    state.players[seat].mana_pool = {'G': 1, 'C': 3}
    if not eligible:
        for cid in list(state.players[affected].library):
            state.players[affected].library.remove(cid)
            state.cards[cid].move_to_zone(Zone.HAND)
            state.players[affected].hand.append(cid)
    data = {'seat': seat, 'affected': affected, 'mode': mode, 'source': favor.id,
            'target': creature.id, 'response': response.id if response else None,
            'target_initial_reference': [object_incarnation(creature), creature.zone_change_sequence],
            'initial_counters': dict(creature.counters), 'caster_library': list(state.players[seat].library),
            'library': list(state.players[affected].library)}
    return state, data


def favor_action(data):
    targets = {'target_player': data['affected']}
    if data['mode'] != 'zero':
        targets['target_card_id'] = data['target']
    return {'type': 'cast_spell', 'card_id': data['source'],
            'cost_choice': {'id': 'base'}, 'targets': targets}


def response_action(data):
    return {'type': 'cast_spell', 'card_id': data['response'],
            'cost_choice': {'id': 'base'}, 'targets': {'target_card_id': data['target']}}


def resolve_one(state):
    size = len(state.stack)
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert len(state.stack) == size-1 or state.pending_mechanic_choice
    return state


def record(tmp_path, label, state, data):
    payload = {'root': snap(state), 'data': data,
               'legal_moves': {str(pid): RulesEngine().legal_moves(state, pid) for pid in (1, 2)},
               'public': serialize_match(state)}
    (tmp_path / (label + '.json')).write_text(json.dumps(payload, sort_keys=True))


def assert_private(state, affected):
    pending = serialize_match(state)['pending_mechanic_choice']
    if pending:
        assert set(pending) <= {'kind', 'player_id', 'label', 'count', 'min_count'}
    for pid in (1, 2):
        moves = RulesEngine().legal_moves(state, pid)
        view, _ = decision_view(state, pid, moves)
        for cid in state.players[3-pid].hand + state.players[3-pid].library:
            remembered = remembered_hand_card(state, pid, state.cards[cid])
            if remembered is None:
                assert is_unknown(view.cards[cid])
            else:
                assert view.cards[cid].name == remembered.name
                assert view.cards[cid].types == remembered.types
    if state.pending_mechanic_choice:
        assert not RulesEngine().legal_moves(state, 3-affected)


def paid_to_search(seat, mode, tmp_path, eligible=True):
    state, data = position(seat, mode, eligible)
    record(tmp_path, 'initial', state, data)
    state = act(state, seat, favor_action(data))
    item = state.stack[-1]
    data['stack_id'] = item.id
    assert item.controller == seat and item.source_card_id == data['source']
    assert item.payload['mana_spent'] == 4
    assert state.players[seat].mana_pool['G'] == state.players[seat].mana_pool['C'] == 0
    record(tmp_path, 'paid-favor', state, data)
    if data['response']:
        state = act(state, seat, {'type': 'pass_priority'})
        assert state.priority_player == data['affected']
        state = act(state, data['affected'], response_action(data))
        assert state.stack[-1].payload['mana_spent'] == 1
        state = resolve_one(restart(state, tmp_path, 'paid-response'))
        assert len(state.stack) == 1 and state.stack[0].id == data['stack_id']
        target = state.cards[data['target']]
        record(tmp_path, 'response-resolved', state, data)
        if mode == 'unsummon':
            assert target.zone == Zone.HAND
        elif mode == 'bolt':
            assert target.zone == Zone.GRAVEYARD
        elif mode == 'veil':
            assert 'hexproof' in effective_keywords(state, target.id)
            assert target.counters.get('+1/+1', 0) == 1
        elif mode == 'blink':
            assert target.zone == Zone.BATTLEFIELD
            assert [object_incarnation(target), target.zone_change_sequence] != data['target_initial_reference']
    data['counters_before_favor'] = dict(state.cards[data['target']].counters)
    state = resolve_one(restart(state, tmp_path, 'before-favor-resolution'))
    record(tmp_path, 'search-prompt-or-complete', state, data)
    return state, data


def assert_outcome(state, data, find):
    assert state.pending_mechanic_choice is None and not state.stack
    assert state.cards[data['source']].zone == Zone.GRAVEYARD
    assert state.players[data['seat']].library == data['caster_library']
    if find:
        card = state.cards[data['chosen']]
        assert card.zone == Zone.BATTLEFIELD and card.tapped
        assert card.owner == card.controller == data['affected']
        assert state.players[data['affected']].battlefield.count(card.id) == 1
    else:
        assert set(state.players[data['affected']].library) == set(data['library'])
    expected = deepcopy(data['counters_before_favor'])
    if data['mode'] == 'none':
        expected['+1/+1'] = expected.get('+1/+1', 0) + 2
    assert state.cards[data['target']].counters == expected, {
        'mode': data['mode'], 'zone': state.cards[data['target']].zone.value,
        'expected': expected, 'actual': state.cards[data['target']].counters}
