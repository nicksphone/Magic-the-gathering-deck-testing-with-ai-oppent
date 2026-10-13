"""Empty advisory observations retain legacy serialized shape; live data survives."""
from copy import deepcopy

import pytest

from game_state.observations import observe_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, Zone
from knowledge.service import snapshot_for
from tests import test_ai_knowledge_snapshot_contract as contracts
from tests.test_ai_search_prefix import bare_state


def position(seat):
    state = bare_state(seat)
    fixture = contracts.KnowledgeSnapshotContract()
    raw, row, hydrated = fixture.fixture()
    card = CardInstance('observed', raw['name'], seat, seat, Zone.GRAVEYARD,
                        ['Instant'], mana_cost=raw['mana_cost'], oracle_text=raw['oracle_text'],
                        type_line=raw['type_line'], layout=raw['layout'])
    state.cards[card.id] = card
    state.players[seat].graveyard.append(card.id)
    return state, card, snapshot_for(row, raw['name'], hydrated)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('viewer', [1, 2])
def test_empty_observation_knowledge_is_omitted_like_card_without_live_mutation(seat, viewer):
    state, card, _ = position(seat)
    observe_cards(state, [card.id])
    before = deepcopy(state.card_observations)
    assert state.card_observations[viewer][card.id]['knowledge_snapshot'] == {}
    payload = serialize_match_snapshot(state)
    assert 'knowledge_snapshot' not in payload['cards'][card.id]
    assert 'knowledge_snapshot' not in payload['card_observations'][str(viewer)][card.id]
    assert state.card_observations == before
    restored = deserialize_match_snapshot(payload)
    observe_cards(restored, [card.id])
    assert serialize_match_snapshot(restored) == payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('viewer', [1, 2])
def test_nonempty_verified_observation_knowledge_survives_private_roundtrip(seat, viewer):
    state, card, knowledge = position(seat)
    card.knowledge_snapshot = knowledge
    observe_cards(state, [card.id])
    before = deepcopy(state.card_observations)
    payload = serialize_match_snapshot(state)
    assert payload['cards'][card.id]['knowledge_snapshot'] == knowledge
    assert payload['card_observations'][str(viewer)][card.id]['knowledge_snapshot'] == knowledge
    assert state.card_observations == before
    assert serialize_match_snapshot(deserialize_match_snapshot(payload)) == payload


@pytest.mark.parametrize('value', [None, False, [], {'future': 'unvalidated'}])
def test_omission_never_silently_erases_other_advisory_or_observation_data(value):
    state, card, _ = position(1)
    observe_cards(state, [card.id])
    state.card_observations[1][card.id]['knowledge_snapshot'] = deepcopy(value)
    state.card_observations[1][card.id]['unreviewed_observation_field'] = {'retain': True}
    before = deepcopy(state.card_observations)
    payload = serialize_match_snapshot(state)
    record = payload['card_observations']['1'][card.id]
    assert 'knowledge_snapshot' in record and record['knowledge_snapshot'] == value
    assert record['unreviewed_observation_field'] == {'retain': True}
    assert state.card_observations == before
