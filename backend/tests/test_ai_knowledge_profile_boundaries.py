"""Finite compatibility/mismatch controls, not a new rules-authority mechanism."""
from copy import deepcopy
from dataclasses import asdict, fields
from unittest.mock import patch

from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from card_data.tactical import tactical_tags
from game_state.state import CardInstance
from knowledge.profiles import _hash
from knowledge.service import copy_snapshot, snapshot_for, tags_for
from rules_engine.engine import RulesEngine
import pytest
from tests.test_ai_knowledge_profile_consumer import ReadOnlyRows, position
from tests import test_ai_knowledge_snapshot_contract as contracts


def fixture(name='Lightning Bolt'):
    case = contracts.KnowledgeSnapshotContract()
    raw, row, hydrated = case.fixture(name)
    snapshot = snapshot_for(row, name, hydrated)
    assert snapshot
    return case.card(raw, hydrated, snapshot), raw, row, hydrated


def test_new_carrier_is_appended_preserving_old_positional_constructor_slots():
    assert fields(CardInstance)[-1].name == 'knowledge_snapshot'


def test_actual_front_face_zero_and_unselected_composite_are_distinct():
    card, raw, _, _ = fixture('Bonecrusher Giant // Stomp')
    card.selected_face_index = 0
    assert tags_for(card).source == 'persisted' and tags_for(card).face_index == 0
    card.selected_face_index = None
    card.type_line = raw['type_line']
    # Genuine combined parent descriptor, not a selected/fused playable spell.
    assert tags_for(card).source == 'fallback'


def test_changed_live_oracle_uses_current_legacy_tags_not_stale_profile():
    card, _, _, _ = fixture()
    card.oracle_text = 'Draw a card.'  # Explicit inert current-surface mismatch.
    result = tags_for(card)
    assert result.source == 'fallback' and result.reason == 'surface'
    assert set(result.tags) == tactical_tags(card.oracle_text, card.type_line, card.types)
    assert 'burn' not in result.tags


def test_actual_face_roster_change_and_boolean_index_are_rejected():
    card, _, _, _ = fixture('Bonecrusher Giant // Stomp')
    card.selected_face_index = True
    assert tags_for(card).source == 'fallback'
    card.selected_face_index = 1
    card.card_faces.reverse()
    assert tags_for(card).source == 'fallback'


def test_client_supplied_carrier_is_dropped_before_hydration_even_with_valid_seal():
    card, raw, _, _ = fixture()
    forged = deepcopy(card.knowledge_snapshot)
    repo = ReadOnlyRows()
    repo.rows.clear()
    hydrated = hydrate_deck_cards(repo, [{'card_name': 'Lightning Bolt', 'quantity': 1,
                                        'image_uri': raw['image_uris']['normal'],
                                        'knowledge_snapshot': forged}])
    assert 'knowledge_snapshot' not in hydrated[0]


def test_persisted_positive_lookup_does_not_run_tactical_parser_again():
    card, _, _, _ = fixture()
    with patch('knowledge.service.tactical_tags', side_effect=AssertionError('Positive lookup reparsed Oracle')):
        assert 'burn' in AIAgent()._spell_tags(card)


def test_cold_semantic_validation_rejects_resealed_forged_tags():
    card, _, _, _ = fixture()
    forged = deepcopy(card.knowledge_snapshot)
    forged['root']['tags'] = ['ramp']
    forged['snapshot_sha256'] = _hash({key: value for key, value in forged.items() if key != 'snapshot_sha256'})
    assert copy_snapshot(forged, semantic=True) == {}


def test_repeated_real_consumer_calls_count_once_per_decision_surface():
    state, _ = position(1)
    legal = RulesEngine().legal_moves(state, 1)
    original = AIAgent(difficulty='strong', archetype='Aggro').choose_action(state, legal, 1)
    actor = AIAgent(difficulty='strong', archetype='Aggro')
    call = actor._spell_tags

    def twice(card):
        tags = call(card)
        assert call(card) == tags
        return tags

    with patch.object(actor, '_spell_tags', side_effect=twice):
        doubled = actor.choose_action(state, legal, 1)
    assert doubled.action == original.action and doubled.reasoning == original.reasoning
    assert doubled.knowledge_usage == original.knowledge_usage


@pytest.mark.parametrize('seat', [1, 2])
def test_distinct_physical_modal_cards_count_separately_without_proxy_engine_id(seat):
    from game_state.state import Zone
    state, _ = position(seat)
    cards = [card for card in state.cards.values()
             if card.owner == seat and card.name == 'Bonecrusher Giant'][:2]
    assert len(cards) == 2 and cards[0].id != cards[1].id
    # Trusted board positioning; this regression measures telemetry, not policy quality.
    for card in cards:
        state.players[seat].library.remove(card.id)
        card.move_to_zone(Zone.HAND)
        state.players[seat].hand.append(card.id)
    actor = AIAgent(difficulty='strong', archetype='Aggro')
    choose = actor._choose_action
    observed = []

    def consult(projected, moves, player):
        proxies = [actor._modal_face_proxy(projected.cards[card.id],
                                          projected.cards[card.id].card_faces[1], face_index=1)
                   for card in cards]
        assert all(not hasattr(proxy, 'id') for proxy in proxies)
        before = actor._knowledge_usage['counts']['persisted']
        for proxy in proxies:
            assert 'burn' in actor._spell_tags(proxy)
        assert actor._knowledge_usage['counts']['persisted'] - before == 2
        # Rebuilt proxies for the same original instances must not add consultations.
        for card, proxy in zip(cards, proxies):
            assert actor._spell_tags(proxy) == actor._spell_tags(
                actor._modal_face_proxy(projected.cards[card.id],
                                       projected.cards[card.id].card_faces[1], face_index=1))
        assert actor._knowledge_usage['counts']['persisted'] - before == 2
        observed.append(True)
        return choose(projected, moves, player)

    with patch.object(actor, '_choose_action', side_effect=consult):
        decision = actor.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert observed == [True] and decision.knowledge_usage['persisted'] >= 2
    assert actor._knowledge_usage is None


def test_pending_and_verified_flags_are_preserved_without_rulings_text_transport():
    card, raw, row, hydrated = fixture()
    assert card.knowledge_snapshot['rulings_pending'] is True
    import json
    profile = json.loads(row.profiles_json)
    # Inert flag transport control; not an official rulings-verification proof.
    profile['rulings_verified'] = True
    profile['rulings'] = [{'private_payload': 'must not be carried'}]
    row.profiles_json = json.dumps(profile)
    snapshot = snapshot_for(row, raw['name'], hydrated)
    assert snapshot['rulings_pending'] is False
    assert 'rulings' not in snapshot and 'private_payload' not in json.dumps(snapshot)


@pytest.mark.parametrize('seat', [1, 2])
def test_nested_public_pending_projection_cannot_export_private_carrier(seat):
    import json
    from game_state.serializers import serialize_match, serialize_match_snapshot
    state, cid = position(seat)
    # Inert pending-payload transport control using real asdict(CardInstance),
    # not a claim that this fixture emitted an actual entry/replacement event.
    pending = {'kind': 'entry_counters', 'entry_targets': [{'projection': asdict(state.cards[cid])}]}
    pending['nested'] = ([asdict(state.cards[cid])], ('kept', True, 1, 1.0, {'projection': asdict(state.cards[cid])}))
    state.pending_replacement_choice = deepcopy(pending)
    state.pending_trigger_order = deepcopy(pending)
    state.pending_mechanic_choice = deepcopy(pending)
    before = serialize_match_snapshot(state)
    public = serialize_match(state, look_players=[seat])
    encoded = json.dumps(public)
    assert 'knowledge_snapshot' not in encoded
    assert state.cards[cid].knowledge_snapshot['source_sha256'] not in encoded
    nested = public['pending_replacement_choice']['nested']
    assert type(nested[0]) is list and type(nested[1]) is tuple
    assert tuple(type(value) for value in nested[1][:4]) == (str, bool, int, float)
    assert nested[1][:4] == ('kept', True, 1, 1.0)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_cold_known_memory_cannot_bypass_semantic_carrier_validation(seat):
    from ai.information import decision_view
    from game_state.observations import observe_cards
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from game_state.state import Zone
    state, _ = position(seat)
    enemy = 3 - seat
    card = state.cards[state.players[enemy].hand[0]]
    state.players[enemy].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[enemy].battlefield.append(card.id)
    observe_cards(state, [card.id])
    state.players[enemy].battlefield.remove(card.id)
    card.move_to_zone(Zone.HAND)
    state.players[enemy].hand.append(card.id)
    saved = serialize_match_snapshot(state)
    carrier = saved['card_observations'][str(seat)][card.id]['knowledge_snapshot']
    carrier['root']['tags'] = ['burn']
    carrier['snapshot_sha256'] = _hash({key: value for key, value in carrier.items() if key != 'snapshot_sha256'})
    restored = deserialize_match_snapshot(saved)
    view, _ = decision_view(restored, seat, RulesEngine().legal_moves(restored, seat))
    known = view.cards[card.id]
    assert known.name == 'Forest'  # Legitimate known identity itself survives.
    assert known.knowledge_snapshot == {}
    assert tags_for(known).source == 'fallback' and 'burn' not in tags_for(known).tags
