"""Exact browser-scene stock and real paid search; not HTTP/browser evidence."""
from copy import deepcopy
from uuid import UUID

import pytest

from game_state.serializers import (
    deserialize_match_snapshot,
    serialize_match,
    serialize_match_snapshot,
)
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests import test_linked_discard as linked
from tests.test_ui_synthetic_stock_publication import projected_fixture


def assert_search_move(move, seat, expected_ids):
    assert move['type'] == 'choose_mechanic'
    assert move['kind'] == 'search_library' and move['player_id'] == seat
    assert move['count'] == 2 and move['min_count'] == 0
    assert move['options'] == expected_ids
    assert len(set(move['options'])) == len(expected_ids)
    assert move['option_labels'] == {cid: 'Swamp' for cid in expected_ids}
    assert move['option_type_lines'] == {
        cid: 'Basic Land \u2014 Swamp' for cid in expected_ids
    }


@pytest.mark.parametrize('seat', [1, 2])
def test_real_linked_scene_retains_native_stock_and_exact_public_search(seat, monkeypatch):
    # Observe genuine constructor returns, independently of the later options.
    original_add = linked.add
    additions = []

    def observe_add(state, name, owner=1, zone=Zone.BATTLEFIELD):
        card = original_add(state, name, owner, zone)
        additions.append((name, owner, zone, card.id))
        return card

    monkeypatch.setattr(linked, 'add', observe_add)
    namespace, saved = projected_fixture()
    state = namespace['fixture'](face_kind=f'linked_discard_0_{seat}')
    stock = {
        f'p{owner}-{index:03d}': {'owner': owner, 'stock_key': 'Swamp'}
        for owner in (1, 2) for index in range(1, 61)
    }
    scene_ids = [str(UUID(int=index)) for index in range(1, 9)]
    appended_ids = scene_ids[4:]
    assert additions == [
        (name, seat, Zone.HAND, cid)
        for name, cid in zip(('Island', 'Swamp', 'Grizzly Bears'), scene_ids[1:4])
    ] + [('Swamp', seat, Zone.LIBRARY, cid) for cid in appended_ids]
    assert state.sideboard_facts['capture_version'] == 3
    assert state.sideboard_facts['coverage_ok'] is True
    assert state.sideboard_facts['inventory'] == stock
    assert saved['snapshot']['sideboard_facts'] == state.sideboard_facts
    assert set(state.cards) == set(stock) | set(scene_ids)
    for cid in stock:
        card = state.cards[cid]
        assert card.owner == stock[cid]['owner'] and card.controller == card.owner
        assert card.characteristic_record['physical']['name'] == 'Swamp'
        assert card.type_line == 'Basic Land \u2014 Swamp' and card.types == ['Land']
        assert card.oracle_text == '({T}: Add {B}.)' and card.zone == Zone.LIBRARY
    for cid in appended_ids:
        card = state.cards[cid]
        assert card.owner == card.controller == seat and card.zone == Zone.LIBRARY
        assert card.name == 'Swamp' and card.type_line == 'Basic Land \u2014 Swamp'
        assert card.types == ['Land'] and card.oracle_text == '({T}: Add {B}.)'
        assert cid not in stock
    expected_ids = [
        f'p{seat}-{index:03d}'
        for index in (*range(1, 54), *range(60, 53, -1))
    ] + appended_ids
    assert state.players[seat].library == expected_ids
    assert state.players[seat].hand == scene_ids[:4]
    assert state.players[3-seat].hand == []
    source = state.cards[scene_ids[0]]
    assert source.name == 'Rites of Spring' and source.mana_cost == '{1}{G}'
    assert source.oracle_text == (
        'Discard any number of cards. Search your library for up to that many '
        'basic land cards, reveal them, put them into your hand, then shuffle.'
    )
    rules = RulesEngine()
    pool = deepcopy(state.players[seat].mana_pool)
    opponent = deepcopy(serialize_match(state)['players'][3-seat])
    state = checked_action(state, rules, seat, {
        'type': 'cast_spell', 'card_id': source.id,
    })
    assert len(state.stack) == 1 and state.stack[0].source_card_id == source.id
    assert state.cards[source.id].zone == Zone.STACK
    assert sum(pool.values()) - sum(state.players[seat].mana_pool.values()) == 2
    assert state.players[seat].mana_pool['G'] < pool['G']
    for actor in (seat, 3-seat):
        assert state.priority_player == actor
        state = checked_action(state, rules, actor, {'type': 'pass_priority'})
    assert state.pending_mechanic_choice['kind'] == 'discard'
    assert state.pending_mechanic_choice['count'] == 3
    discarded = scene_ids[1:3]
    state = checked_action(state, rules, seat, {
        'type': 'choose_mechanic', 'card_ids': discarded,
    })
    snapshot = serialize_match_snapshot(state)
    state = deserialize_match_snapshot(deepcopy(snapshot))
    assert serialize_match_snapshot(state) == snapshot
    public = serialize_match(state)['pending_mechanic_choice']
    assert public['kind'] == 'search_library' and public['count'] == 2
    assert 'options' not in public and 'library_ids' not in public
    moves = rules.legal_moves(state, seat)
    assert len(moves) == 1
    assert_search_move(moves[0], seat, expected_ids)
    assert rules.legal_moves(state, 3-seat) == []
    assert serialize_match_snapshot(state) == snapshot
    for invalid_ids in (
        expected_ids[1:], expected_ids[:-1],
        [expected_ids[1], *expected_ids[1:]],
        [f'p{3-seat}-001', *expected_ids[1:]],
    ):
        corrupted = deepcopy(moves[0])
        corrupted['options'] = invalid_ids
        with pytest.raises(AssertionError):
            assert_search_move(corrupted, seat, expected_ids)
    for actor, ids in ((3-seat, expected_ids[:1]), (seat, expected_ids[:3])):
        with pytest.raises(ActionRejected):
            checked_action(state, rules, actor, {
                'type': 'choose_mechanic', 'card_ids': ids,
            })
        assert serialize_match_snapshot(state) == snapshot
    chosen = expected_ids[0]
    state = checked_action(state, rules, seat, {
        'type': 'choose_mechanic', 'card_ids': [chosen],
    })
    assert state.pending_mechanic_choice is None and state.stack == []
    assert state.players[seat].hand == [scene_ids[3], chosen]
    assert state.cards[chosen].zone == Zone.HAND and chosen in stock
    assert len(state.players[seat].library) == len(expected_ids) - 1
    assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in discarded)
    assert state.cards[source.id].zone == Zone.GRAVEYARD
    assert sum('shuffles their library' in row for row in state.log) == 1
    assert serialize_match(state)['players'][3-seat] == opponent
    assert state.sideboard_facts['inventory'] == stock
    final = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(deepcopy(final))) == final
