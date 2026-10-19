"""Actual core consumers with inert read-only row lookup; no SQL/repository certificate."""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from card_data.hydration import hydrate_deck_cards
from game_state.observations import observe_cards
from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from knowledge.models import CardKnowledge
from knowledge.profiles import derive_profile, merge_profile_payload
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


RAW = {card['name']: card for card in map(json.loads, (
    Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_bytes().splitlines())}


class ReadOnlyRows:
    """Real CardKnowledge model values, not actual database reads."""
    def __init__(self):
        self.rows = {}
        for name in ('Lightning Bolt', 'Mountain', 'Forest', 'Bonecrusher Giant // Stomp'):
            raw = deepcopy(RAW[name])
            profile = merge_profile_payload({'card_data': raw, 'rulings_verified': False}, derive_profile(raw))
            self.rows[name] = CardKnowledge(name=name, scryfall_id=raw['id'], oracle_source='scryfall',
                                            profiles_json=json.dumps(profile))

    def get_cached_cards_by_names(self, names):
        return {}

    def get_card_knowledge_by_names(self, names):
        out = {}
        for name in names:
            for row in self.rows.values():
                raw = json.loads(row.profiles_json)['card_data']
                if name == row.name or any(name == face['name'] for face in raw.get('card_faces', [])):
                    out[name.casefold()] = row
        return out


def position(seat):
    assert 'knowledge_snapshot' in {field.name for field in fields(CardInstance)}, 'Consumer carrier absent'
    repo = ReadOnlyRows()
    own = hydrate_deck_cards(repo, [{'card_name': 'Lightning Bolt', 'quantity': 12},
                                   {'card_name': 'Mountain', 'quantity': 12},
                                   {'card_name': 'Bonecrusher Giant', 'quantity': 4}])
    enemy = hydrate_deck_cards(repo, [{'card_name': 'Forest', 'quantity': 24}])
    state = MatchFactory.from_decks(own if seat == 1 else enemy, enemy if seat == 1 else own, seed=731)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    # Declared trusted initial board, not a naturally replayed opening hand.
    for cid in list(state.players[seat].hand):
        state.players[seat].hand.remove(cid)
        state.players[seat].library.append(cid)
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    bolt = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Lightning Bolt')
    mountain = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Mountain')
    for card, zone in ((bolt, Zone.HAND), (mountain, Zone.BATTLEFIELD)):
        state.players[seat].library.remove(card.id)
        getattr(state.players[seat], zone.value).append(card.id)
        card.move_to_zone(zone)
        card.summoning_sick = False
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'tap_land_for_mana', 'card_id': mountain.id, 'color': 'R'})
    return state, bolt.id


@pytest.mark.parametrize('seat', [1, 2])
def test_real_row_hydration_factory_choice_and_checked_paid_cast(seat):
    state, cid = position(seat)
    assert state.cards[cid].knowledge_snapshot
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    decision = AIAgent(difficulty='strong', archetype='Aggro').choose_action(state, legal, seat)
    assert decision.knowledge_usage['persisted'] > 0
    assert decision.action['type'] == 'cast_spell'
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.stack[-1].source_card_id == cid
    from rules_engine.targeting import stack_object_kind
    assert stack_object_kind(result, result.stack[-1]) == 'spell'
    assert result.stack[-1].payload['mana_spent'] == 1
    assert sum(result.players[seat].mana_pool.values()) == 0
    for _ in range(2):
        result = checked_action(result, RulesEngine(), result.priority_player, {'type': 'pass_priority'})
    assert result.players[3 - seat].life == 17 and result.cards[cid].zone == Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before
    assert not any('knowledge' in line.lower() for line in state.log)


@pytest.mark.parametrize('seat', [1, 2])
def test_unsynced_fallback_keeps_same_decision_and_has_anonymous_counter(seat):
    state, cid = position(seat)
    legacy = deepcopy(state)
    for card in legacy.cards.values():
        card.knowledge_snapshot = {}
    legal = RulesEngine().legal_moves(state, seat)
    actor = AIAgent(difficulty='strong', archetype='Aggro')
    known = actor.choose_action(state, legal, seat)
    missing = AIAgent(difficulty='strong', archetype='Aggro').choose_action(legacy, legal, seat)
    assert known.action == missing.action
    assert known.reasoning == missing.reasoning
    assert missing.knowledge_usage['fallback'] > 0
    assert missing.knowledge_usage['fallback_reasons']['missing'] > 0
    assert set(missing.knowledge_usage) == {'persisted', 'fallback', 'opaque', 'fallback_reasons'}
    assert not any(word in json.dumps(missing.knowledge_usage) for word in ('Lightning', 'oracle_id', 'sha256', 'burn'))
    assert actor._knowledge_usage is None


@pytest.mark.parametrize('seat', [1, 2])
def test_private_cold_roundtrip_old_snapshot_and_malformed_carrier_fallback(seat):
    state, cid = position(seat)
    snapshot = serialize_match_snapshot(state)
    restored = deserialize_match_snapshot(deepcopy(snapshot))
    assert restored.cards[cid].knowledge_snapshot == state.cards[cid].knowledge_snapshot
    assert restored.cards[cid].knowledge_snapshot is not state.cards[cid].knowledge_snapshot
    old = deepcopy(snapshot)
    for card in old['cards'].values():
        card.pop('knowledge_snapshot')
    old_state = deserialize_match_snapshot(old)
    assert not old_state.cards[cid].knowledge_snapshot
    decision = AIAgent(difficulty='strong', archetype='Aggro').choose_action(
        old_state, RulesEngine().legal_moves(old_state, seat), seat)
    assert decision.knowledge_usage['fallback_reasons']['missing'] > 0
    malformed = deepcopy(snapshot)
    malformed['cards'][cid]['knowledge_snapshot'] = {'schema_version': 1, 'client_hash': '0' * 64}
    assert not deserialize_match_snapshot(malformed).cards[cid].knowledge_snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_identity_changes_never_restore_a_carrier_or_change_choice(seat):
    state, cid = position(seat)
    legal = RulesEngine().legal_moves(state, seat)
    view, _ = decision_view(state, seat, legal)
    hidden = state.players[3 - seat].hand + state.players[3 - seat].library + state.players[seat].library
    for hidden_id in hidden:
        card = view.cards[hidden_id]
        assert is_unknown(card)
        assert card.knowledge_snapshot == {} and card.card_faces == []
        assert not card.oracle_text and not card.types
    changed = deepcopy(state)
    for hidden_id in hidden:
        card = changed.cards[hidden_id]
        card.name = RAW['Bonecrusher Giant // Stomp']['name']
        card.oracle_text = RAW['Lightning Bolt']['oracle_text']
        card.card_faces = deepcopy(RAW['Bonecrusher Giant // Stomp']['card_faces'])
        card.knowledge_snapshot = deepcopy(state.cards[cid].knowledge_snapshot)
    a = AIAgent(difficulty='strong', archetype='Aggro').choose_action(state, legal, seat)
    b = AIAgent(difficulty='strong', archetype='Aggro').choose_action(changed, legal, seat)
    assert a.action == b.action and a.reasoning == b.reasoning and a.knowledge_usage == b.knowledge_usage


@pytest.mark.parametrize('seat', [1, 2])
def test_public_serialization_omits_private_carrier_and_source_hash(seat):
    state, cid = position(seat)
    encoded = json.dumps(serialize_match(state, look_players=[seat]))
    assert 'knowledge_snapshot' not in encoded
    assert state.cards[cid].knowledge_snapshot['source_sha256'] not in encoded


@pytest.mark.parametrize('seat', [1, 2])
def test_modal_proxy_requires_explicit_index_and_original_face_reference(seat):
    state, _ = position(seat)
    card = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Bonecrusher Giant')
    actor = AIAgent()
    proxy = actor._modal_face_proxy(card, card.card_faces[1], face_index=1)
    assert proxy.selected_face_index == 1 and proxy.knowledge_snapshot
    assert 'burn' in actor._spell_tags(proxy)
    from knowledge.service import tags_for
    assert tags_for(proxy).source == 'persisted'
    assert not actor._modal_face_proxy(card, deepcopy(card.card_faces[1]), face_index=1).knowledge_snapshot
    assert not actor._modal_face_proxy(card, card.card_faces[0], face_index=1).knowledge_snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_authorized_observation_retains_old_carrier_but_library_trip_masks_it(seat):
    state, _ = position(seat)
    enemy = 3 - seat
    card = state.cards[state.players[enemy].hand[0]]
    state.players[enemy].hand.remove(card.id)
    card.move_to_zone(Zone.BATTLEFIELD)
    state.players[enemy].battlefield.append(card.id)
    observe_cards(state, [card.id])
    retained = deepcopy(card.knowledge_snapshot)
    state.players[enemy].battlefield.remove(card.id)
    card.move_to_zone(Zone.HAND)
    state.players[enemy].hand.append(card.id)
    card.knowledge_snapshot = {'private_future': True}
    legal = RulesEngine().legal_moves(state, seat)
    view, _ = decision_view(state, seat, legal)
    assert view.cards[card.id].knowledge_snapshot == retained
    state.players[enemy].hand.remove(card.id)
    card.move_to_zone(Zone.LIBRARY)
    state.players[enemy].library.append(card.id)
    view, _ = decision_view(state, seat, legal)
    assert is_unknown(view.cards[card.id]) and view.cards[card.id].knowledge_snapshot == {}
