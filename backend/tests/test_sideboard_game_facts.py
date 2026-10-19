"""Actual Factory/draw transport; not a sideboarded game or BO3 certificate."""
from copy import deepcopy
from importlib.util import find_spec
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone, draw_card
from game_state.serializers import (
    deserialize_match_snapshot, serialize_match, serialize_match_snapshot,
)
from ai.information import decision_view


def state():
    rows = json.loads((Path(__file__).parent / 'fixtures/sideboard_basics.json').read_text())
    forest = next(row for row in rows if row['name'] == 'Forest')
    deck = [{**forest, 'card_name': forest['name'], 'quantity': 60}]
    return MatchFactory.from_decks(deck, deepcopy(deck), seed=13)


def facts_api():
    assert find_spec('ai.sideboard_facts') is not None, 'missing accepted-state fact producer'
    from ai import sideboard_facts
    return sideboard_facts


@pytest.mark.parametrize('pid', [1, 2])
def test_factory_binds_original_inventory_and_real_initial_draws(pid):
    game = state()
    assert getattr(game, 'sideboard_facts', None), 'Factory did not initialize facts'
    facts = game.sideboard_facts
    assert facts['version'] == 1 and facts['game_id'] == game.id
    assert facts['complete'] is False  # Opening draws are not completed game history.
    assert len(facts['inventory']) == 120
    for cid in game.players[pid].hand:
        assert facts['inventory'][cid] == {'owner': pid, 'stock_key': 'Forest'}
        assert facts['seats'][str(pid)]['hand_entries'][cid] == game.cards[cid].zone_change_sequence
    assert len(facts['seats'][str(pid)]['hand_entries']) == 7


@pytest.mark.parametrize('pid', [1, 2])
def test_real_draw_extends_only_that_owner_hand_records(pid):
    game = state()
    api = facts_api()
    before = deepcopy(game.sideboard_facts)
    cid = game.players[pid].library[-1]
    draw_card(game, pid)
    assert game.sideboard_facts['seats'][str(pid)]['hand_entries'][cid] == game.cards[cid].zone_change_sequence
    assert game.sideboard_facts['seats'][str(3-pid)] == before['seats'][str(3-pid)]
    assert cid in api.held_unused_ids(game, pid)


@pytest.mark.parametrize('pid', [1, 2])
def test_physical_hand_identity_not_same_name_or_returned_incarnation(pid):
    # Trusted zone primitive negative, not a claimed paid bounce episode.
    game = state()
    api = facts_api()
    held, other = game.players[pid].hand[:2]
    assert game.cards[held].name == game.cards[other].name
    assert held in api.held_unused_ids(game, pid)
    game.cards[held].move_to_zone(Zone.EXILE)
    game.cards[held].move_to_zone(Zone.HAND)
    assert held not in api.held_unused_ids(game, pid)
    assert other in api.held_unused_ids(game, pid)


def test_private_snapshot_roundtrip_preserves_detached_facts_and_old_snapshot_unknown():
    game = state()
    facts_api()
    snapshot = serialize_match_snapshot(game)
    assert snapshot['sideboard_facts'] == game.sideboard_facts
    assert snapshot['sideboard_facts'] is not game.sideboard_facts
    restored = deserialize_match_snapshot(deepcopy(snapshot))
    assert restored.sideboard_facts == game.sideboard_facts
    old = deepcopy(snapshot)
    del old['sideboard_facts']
    assert deserialize_match_snapshot(old).sideboard_facts == {}


@pytest.mark.parametrize('mutation', ['coverage_bool', 'wrong_owner', 'foreign_physical_id'])
def test_new_snapshot_invalid_fact_binding_rejects_without_mutating_payload(mutation):
    game = state()
    facts_api()
    snapshot = serialize_match_snapshot(game)
    if mutation == 'coverage_bool':
        snapshot['sideboard_facts']['complete'] = 1
    elif mutation == 'wrong_owner':
        cid = game.players[1].hand[0]
        snapshot['sideboard_facts']['inventory'][cid]['owner'] = 2
    else:
        snapshot['sideboard_facts']['seats']['1']['hand_entries']['foreign'] = 1
    before = deepcopy(snapshot)
    with pytest.raises(ValueError):
        deserialize_match_snapshot(snapshot)
    assert snapshot == before


@pytest.mark.parametrize('pid', [1, 2])
def test_public_and_decision_views_never_transport_private_fact_map(pid):
    game = state()
    facts_api()
    before = deepcopy(game.sideboard_facts)
    assert 'sideboard_facts' not in serialize_match(game)
    viewed, _ = decision_view(game, pid, [])
    assert viewed.sideboard_facts == {}
    assert game.sideboard_facts == before


def test_projected_draw_never_modifies_authoritative_fact_history():
    game = state()
    facts_api()
    before = deepcopy(game.sideboard_facts)
    projected, _ = decision_view(game, 1, [])
    draw_card(projected, 1)
    assert projected.sideboard_facts == {}
    assert game.sideboard_facts == before
