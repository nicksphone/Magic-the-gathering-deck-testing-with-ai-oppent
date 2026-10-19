"""Explicit fixture provenance: full Factory capture or initially unknown board."""
from copy import deepcopy

import pytest

from ai.sideboard_facts import copy_facts
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from tests.extra_sequence_support import position
from tests.generic_import_fixtures import client
from tests.test_builtin_metadata_refresh import repo
from tests.test_library_reorder import setup
from tests.test_static_replacement_producer_http import install


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_http_fixture_keeps_factory_uuid_and_capture(repo, client, seat):
    import main
    state = position(seat)
    identity, facts = state.id, deepcopy(state.sideboard_facts)
    controller = install(repo, client, state)
    assert state.id == identity and state.sideboard_facts == facts
    assert controller.state is state and main.ACTIVE_MATCHES[identity] is controller
    assert controller.controllers == {1: 'human', 2: 'human'}
    assert copy_facts(state.sideboard_facts, state) == facts
    row = repo.get_active_match(identity)
    assert row is not None
    import json
    snapshot = json.loads(row.state_json)
    assert snapshot['id'] == identity and snapshot['sideboard_facts'] == facts
    assert [r.id for r in repo.list_active_matches()] == [identity]
    main.ACTIVE_MATCHES.pop(identity)
    main._restore_active_matches(repo, identity)
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[identity].state) == serialize_match_snapshot(deserialize_match_snapshot(snapshot))


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_library_is_initially_unknown_not_recaptured_stock(seat):
    state, source = setup('Index', seat)
    assert state.sideboard_facts == {}
    assert source.id in state.players[seat].hand
    assert len(state.players[seat].library) == 8
    assert len(state.players[3-seat].library) == 60
    snapshot = serialize_match_snapshot(state)
    assert snapshot['sideboard_facts'] == {}
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['game_id', 'missing_stock', 'printed_source'])
def test_original_factory_corruption_still_rejects_without_repair(seat, bad):
    state = position(seat)
    cid = next(iter(state.sideboard_facts['inventory']))
    if bad == 'game_id':
        state.id = 'deliberately-wrong-game'
        message = 'Invalid private sideboard facts'
    elif bad == 'missing_stock':
        del state.cards[cid]
        message = 'Invalid sideboard inventory binding'
    else:
        state.cards[cid].printed_characteristics['name'] = 'Deliberately wrong source'
        message = 'Sideboard stock does not match physical printed source'
    before = deepcopy(state.sideboard_facts)
    with pytest.raises(ValueError, match=message):
        serialize_match_snapshot(state)
    assert state.sideboard_facts == before


@pytest.mark.parametrize('seat', [1, 2])
def test_original_factory_position_keeps_full_birth_stock(seat):
    state = position(seat)
    facts = copy_facts(state.sideboard_facts, state)
    assert facts['game_id'] == state.id and facts['coverage_ok'] is True
    assert len(facts['inventory']) == 120 and facts['complete'] is False
    assert serialize_match_snapshot(deserialize_match_snapshot(serialize_match_snapshot(state))) == serialize_match_snapshot(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_controlled_constructor_preserves_every_non_capture_position_field(seat):
    from tests.fixture_state_support import controlled_library_position
    old = serialize_match_snapshot(position(seat))
    new = serialize_match_snapshot(controlled_library_position(seat))
    assert new['sideboard_facts'] == {} and old['sideboard_facts']['inventory']
    assert {k: v for k, v in old.items() if k not in {'id', 'sideboard_facts'}} == {
        k: v for k, v in new.items() if k not in {'id', 'sideboard_facts'}}


@pytest.mark.parametrize('bad', ['game_id', 'missing_stock', 'printed_source'])
def test_explicit_adoption_cannot_repair_corrupt_factory_capture(repo, client, bad):
    from tests.fixture_state_support import adopt_fixture_state
    import main
    state = position(1)
    controller = install(repo, client, state)
    original = serialize_match_snapshot(controller.state)
    registry = dict(main.ACTIVE_MATCHES)
    sql = list(repo.session.connection().connection.driver_connection.iterdump())
    bad_state = deepcopy(state)
    cid = next(iter(bad_state.sideboard_facts['inventory']))
    if bad == 'game_id':
        bad_state.id = 'deliberately-wrong-game'
    elif bad == 'missing_stock':
        del bad_state.cards[cid]
    else:
        bad_state.cards[cid].printed_characteristics['name'] = 'Deliberately wrong source'
    with pytest.raises(ValueError):
        adopt_fixture_state(controller, bad_state, repo)
    assert serialize_match_snapshot(controller.state) == original
    assert main.ACTIVE_MATCHES == registry
    assert list(repo.session.connection().connection.driver_connection.iterdump()) == sql
