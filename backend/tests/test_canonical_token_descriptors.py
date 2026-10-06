"""Canonical creature-token grammar through real casts and selected costs."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_spell_cost_overlap_investigation as cards

DIRECTORY = Path(__file__).parent / 'fixtures/token_descriptor_canonical'
RAW = json.loads((DIRECTORY / 'canonical.json').read_text())
cards.ROWS.update(RAW)


def record(request, **data):
    if os.environ.get('MTG_TOKEN_DESCRIPTOR_EVIDENCE'):
        directory = Path(os.environ['MTG_TOKEN_DESCRIPTOR_EVIDENCE'])
        directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
        (directory / (key + '.json')).write_text(json.dumps({'test': request.node.nodeid, **data}, indent=2) + '\n')


def restart(state):
    snapshot = serialize_match_snapshot(state)
    result = deserialize_match_snapshot(json.loads(json.dumps(snapshot)))
    assert serialize_match_snapshot(result) == snapshot
    return result


def entry(state, name, seat):
    card = cards.add(state, name, seat)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def pay(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    return result


def finish(state):
    while state.stack:
        assert resolve_top_of_stack(state)
        assert state.pending_mechanic_choice is None
    return state


def test_canonical_provenance():
    pin = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert pin['records_scanned'] == 38690 and pin['facts_modified'] is False
    assert pin['http_requests'] == 0
    assert hashlib.sha256((DIRECTORY / 'canonical.json').read_bytes()).hexdigest() == pin['canonical_sha256']
    for name, row in RAW.items():
        assert row['id'] == pin['rows'][name]['id']
        assert row['oracle_id'] == pin['rows'][name]['oracle_id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,expected,count,keywords', [
    ('Hangarback Walker', 'Thopter', 2, ['flying']),
    ('Myr Sire', 'Phyrexian Myr', 1, []),
])
def test_checked_selected_death_artifact_creature(request, seat, name, expected, count, keywords):
    state = cards.position(seat)
    tower = entry(state, 'Phyrexian Tower', seat)
    source = entry(state, name, seat)
    if name == 'Hangarback Walker':
        source.counters['+1/+1'] = count
    entry(state, 'Glorious Anthem', seat)
    before = serialize_match_snapshot(state)
    move = next(move for move in RulesEngine().legal_moves(state, seat)
                if move['type'] == 'activate_mana_ability' and move['card_id'] == tower.id
                and 'Sacrifice' in move['cost_text'])
    option = next(option for option in move['output_options'] if option['output_bundle'] == {'B': 2})
    action = {'type': 'activate_mana_ability', 'card_id': tower.id, 'ability_index': move['ability_index'],
              'color': option['color'], 'output_bundle': option['output_bundle'],
              'payment_choices': {'sacrifice_card_ids': [source.id]}}
    paid = pay(state, seat, action)
    trigger = deepcopy(serialize_match_snapshot(paid))
    result = finish(restart(paid))
    views = [serialize_card_view(result, cid) for cid in result.players[seat].battlefield if result.cards[cid].is_token]
    record(request, before=before, action=action, trigger=trigger, views=views,
           result=serialize_match_snapshot(result))
    assert result.players[seat].mana_pool['B'] == 2
    assert len(views) == count
    if name == 'Hangarback Walker':
        assert trigger['cards'][source.id]['last_known_battlefield']['counters']['+1/+1'] == count
    for view in views:
        assert view['name'] == expected
        assert set(view['types']) == {'Artifact', 'Creature', 'Token'}
        assert view['type_line'] == f'Token Artifact Creature \u2014 {expected}'
        assert view['colors'] == []
        assert view['base_power'] == view['base_toughness'] == 1
        assert view['printed_power'] == view['printed_toughness'] == '1'
        assert view['power'] == view['toughness'] == 2
        assert sorted(view['keywords']) == keywords


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['golem_entry', 'drake_spell'])
def test_canonical_cast_triggers_preserve_distinct_metadata(request, seat, family):
    state = cards.position(seat)
    if family == 'golem_entry':
        source = cards.add(state, 'Blade Splicer', seat, Zone.HAND)
        state.players[seat].mana_pool.update(W=1, C=2)
        action = {'type': 'cast_spell', 'card_id': source.id}
        expected, colors, stats, keywords = 'Phyrexian Golem', [], 3, ['first strike']
        types = {'Artifact', 'Creature', 'Token'}
    else:
        entry(state, 'Talrand, Sky Summoner', seat)
        source = cards.add(state, 'Shock', seat, Zone.HAND)
        state.players[seat].mana_pool.update(R=1)
        action = {'type': 'cast_spell', 'card_id': source.id, 'targets': {'target_player': 3-seat}}
        expected, colors, stats, keywords = 'Drake', ['U'], 2, ['flying']
        types = {'Creature', 'Token'}
    paid = pay(state, seat, action)
    queued = serialize_match_snapshot(paid)
    result = finish(restart(paid))
    views = [serialize_card_view(result, cid) for cid in result.players[seat].battlefield if result.cards[cid].is_token]
    record(request, action=action, queued=queued, views=views, result=serialize_match_snapshot(result))
    assert len(views) == 1
    view = views[0]
    assert view['name'] == expected and set(view['types']) == types
    token_types = 'Artifact Creature' if 'Artifact' in types else 'Creature'
    assert view['type_line'] == f'Token {token_types} \u2014 {expected}'
    assert view['base_power'] == view['base_toughness'] == stats
    assert view['printed_power'] == view['printed_toughness'] == str(stats)
    assert view['colors'] == colors and view['power'] == view['toughness'] == stats
    assert sorted(view['keywords']) == keywords
