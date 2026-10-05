"""Canonical cache facts; no live DB, network, fake card text, or altered stats."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.action_validation import ActionRejected, checked_action, validate_action
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.ward import parse_ward_cost, ward_instances

FACTS = json.loads((Path(__file__).parent / 'fixtures/cathar_day_night.json').read_text())
CATHAR = 'Brutal Cathar // Moonrage Brute'


def test_cached_fixture_facts_match_provenance_backed_canonical_records():
    from hashlib import sha256
    directory = Path(__file__).parent / 'fixtures/cathar_canonical'
    provenance = json.loads((directory / 'provenance.json').read_text())
    for record in provenance['cards']:
        contents = (directory / record['file']).read_bytes()
        assert sha256(contents).hexdigest() == record['sha256']
        raw = json.loads(contents)
        cached = FACTS[record['name']]
        front = (raw.get('card_faces') or [raw])[0]
        assert cached['scryfall_id'] == raw['id']
        assert (cached['layout'] or 'normal') == raw['layout']
        for field in ('name', 'type_line'):
            assert cached[field] == raw[field]
        for field in ('oracle_text', 'mana_cost', 'power', 'toughness', 'colors'):
            default = [] if field == 'colors' else None if field in ('power', 'toughness') else ''
            assert cached[field] == raw.get(field, front.get(field, default))
        assert len(cached['card_faces']) == len(raw.get('card_faces', []))
        for cached_face, canonical_face in zip(cached['card_faces'], raw.get('card_faces', [])):
            for field, value in cached_face.items():
                expected = canonical_face.get('image_uris', {}).get('normal') if field == 'image_uri' else canonical_face.get(field)
                assert value == expected


def setup(seat, designation='day', human=True):
    deck = [{**deepcopy(FACTS[name]), 'card_name': name, 'quantity': count}
            for name, count in ((CATHAR, 8), ('Recruitment Officer', 8), ('Plains', 44))]
    state = MatchFactory.from_decks(deck, deck, seed=621)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.day_night = designation
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {seat}
    state.players[seat].mana_pool.update({color: 20 for color in 'WUBRGC'})
    source = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Brutal Cathar')
    targets = [card for card in state.cards.values() if card.owner == 3-seat and card.name == 'Recruitment Officer'][:2]
    own = next(card for card in state.cards.values() if card.owner == seat and card.name == 'Recruitment Officer')
    for card, destination in [(source, Zone.HAND), *[(card, Zone.BATTLEFIELD) for card in [*targets, own]]]:
        for zone in ('library', 'hand'):
            if card.id in getattr(state.players[card.owner], zone):
                getattr(state.players[card.owner], zone).remove(card.id)
        card.move_to_zone(destination)
        getattr(state.players[card.owner], destination.value).append(card.id)
        if destination == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, card.id)
    return state, source, targets, own


def cast(state, source):
    rules = RulesEngine()
    action = {'type': 'cast_spell', 'card_id': source.id}
    validate_action(state, rules, source.controller, action)
    rules.take_action(state, source.controller, action, reject_invalid=True)
    assert source.zone == Zone.STACK and source.name == 'Brutal Cathar'
    assert resolve_top_of_stack(state)


def choose(state, seat, target, ai=False):
    moves = RulesEngine().legal_moves(state, seat)
    if ai:
        action = AIAgent(difficulty='master', archetype='Control').choose_action(state, moves, seat).action
    else:
        action = next(move for move in moves if move.get('target_card_id') == target.id)
    assert action['type'] == 'choose_trigger_target'
    rules = RulesEngine()
    validate_action(state, rules, seat, action)
    rules.take_action(state, seat, action, reject_invalid=True)


def return_exiled(state, source):
    resolve_effect(state, source.owner, 'linked_exile_return', {'returning': [{
        'card_id': source.id, 'destination': 'battlefield', 'timestamp': object_incarnation(source),
    }]})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('designation', ['none', 'day', 'night'])
def test_canonical_entry_face_and_trigger(seat, designation):
    state, source, targets, own = setup(seat, designation)
    before = object_incarnation(source)
    cast(state, source)
    assert object_incarnation(source) != before
    if designation == 'night':
        assert (source.name, source.selected_face_index, source.power, source.toughness) == ('Moonrage Brute', 1, 3, 3)
        assert 'first strike' in source.keywords
        assert [parse_ward_cost(cost) for cost in ward_instances(state, source)] == [{'kind': 'life', 'amount': 3}]
        assert not state.stack and not state.pending_trigger_order
    else:
        assert state.day_night == 'day'
        assert source.selected_face_index == 0
        moves = RulesEngine().legal_moves(state, seat)
        assert {move.get('target_card_id') for move in moves} == {target.id for target in targets}
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            checked_action(state, RulesEngine(), seat, {**moves[0], 'target_card_id': source.id})
        assert serialize_match_snapshot(state) == before
        state = deserialize_match_snapshot(before)
        choose(state, seat, targets[1])
        assert resolve_top_of_stack(state)
        assert state.cards[targets[1].id].zone == Zone.EXILE
        assert state.cards[own.id].zone == Zone.BATTLEFIELD
        assert state.linked_exiles[0]['source_timestamp'] == object_incarnation(state.cards[source.id])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('human', [True, False])
def test_transform_front_choice_and_exile_survives_back_transform(seat, human):
    state, source, targets, _ = setup(seat, 'night', human=human)
    cast(state, source)
    incarnation = object_incarnation(source)
    state.day_night = 'day'
    RulesEngine()._transform_day_night_permanents(state, 'day')
    assert len(state.stack) == 1
    assert state.stack[-1].effect_key == 'exile_until_source_leaves'
    if human:
        assert not RulesEngine().legal_moves(state, 3-seat)
        choose(state, seat, targets[0], ai=True)
    target_id = state.stack[-1].payload['target_card_id']
    state.day_night = 'night'
    RulesEngine()._transform_day_night_permanents(state, 'night')
    assert object_incarnation(source) == incarnation
    assert resolve_top_of_stack(state)
    assert state.cards[target_id].zone == Zone.EXILE
    assert state.linked_exiles
    resolve_effect(state, seat, 'exile', {'target_card_id': source.id})
    assert state.cards[target_id].zone == Zone.BATTLEFIELD
    assert not state.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('blink', [False, True])
def test_departed_or_blinked_source_before_resolution_does_not_exile(seat, blink):
    state, source, targets, _ = setup(seat, human=False)
    cast(state, source)
    old = state.stack[-1].payload['source_timestamp']
    resolve_effect(state, seat, 'exile', {'target_card_id': source.id})
    if blink:
        state.day_night = 'night'
        return_exiled(state, source)
        assert source.zone == Zone.BATTLEFIELD
        assert source.name == 'Moonrage Brute'
        assert object_incarnation(source) != old
    assert resolve_top_of_stack(state)
    assert all(target.zone == Zone.BATTLEFIELD for target in targets)
    assert not state.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('blink', [False, True])
@pytest.mark.parametrize('human', [False, True])
def test_target_departure_before_resolution_does_not_exile_new_object(seat, blink, human):
    state, source, targets, _ = setup(seat, human=human)
    cast(state, source)
    if human:
        choose(state, seat, targets[0])
    target = state.cards[state.stack[-1].payload['target_card_id']]
    resolve_effect(state, seat, 'exile', {'target_card_id': target.id})
    if blink:
        return_exiled(state, target)
    assert resolve_top_of_stack(state)
    assert target.zone == (Zone.BATTLEFIELD if blink else Zone.EXILE)
    assert not state.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('designation', ['day', 'night'])
def test_noncast_reentry_uses_current_designation(seat, designation):
    state, source, targets, _ = setup(seat, 'night', human=False)
    cast(state, source)
    resolve_effect(state, seat, 'exile', {'target_card_id': source.id})
    state.day_night = designation
    return_exiled(state, source)
    assert source.selected_face_index == (1 if designation == 'night' else 0)
    assert len(state.stack) == (0 if designation == 'night' else 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_linked_return_of_daybound_card_at_night_has_no_front_trigger(seat):
    state, source, _, _ = setup(seat, human=True)
    other = next(card for card in state.cards.values() if card.owner == 3-seat and card.name == 'Brutal Cathar')
    for zone in ('hand', 'library'):
        if other.id in getattr(state.players[other.owner], zone):
            getattr(state.players[other.owner], zone).remove(other.id)
    other.move_to_zone(Zone.BATTLEFIELD)
    state.players[other.owner].battlefield.append(other.id)
    assign_static_order_on_battlefield_entry(state, other.id)
    cast(state, source)
    choose(state, seat, other)
    assert resolve_top_of_stack(state)
    assert other.zone == Zone.EXILE
    state.day_night = 'night'
    RulesEngine()._transform_day_night_permanents(state, 'night')
    resolve_effect(state, seat, 'exile', {'target_card_id': source.id})
    assert other.zone == Zone.BATTLEFIELD and other.name == 'Moonrage Brute'
    assert not state.stack and not state.linked_exiles


def test_empty_dfc_root_oracle_is_hydrated_from_canonical_faces():
    data = deepcopy(FACTS[CATHAR])
    data['oracle_text'] = ''
    row = SimpleNamespace(**{**data, 'card_faces_json': json.dumps(data['card_faces']), 'colors': 'W', 'image_uri': None})
    repo = SimpleNamespace(get_cached_cards_by_names=lambda names: {CATHAR.lower(): row})
    hydrated = hydrate_deck_cards(repo, [{'card_name': CATHAR, 'quantity': 1}])[0]
    assert hydrated['oracle_text'] == FACTS[CATHAR]['card_faces'][0]['oracle_text']
    assert len(hydrated['card_faces']) == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('designation', ['day', 'night'])
def test_self_exile_return_prepares_new_incarnation_in_correct_face(seat, designation):
    state, source, targets, _ = setup(seat, human=False)
    cast(state, source)
    old_trigger = state.stack[-1]
    old_incarnation = object_incarnation(source)
    state.day_night = designation
    resolve_effect(state, seat, 'exile_return_transformed', {'target_card_id': source.id})
    assert object_incarnation(source) != old_incarnation
    assert source.selected_face_index == (1 if designation == 'night' else 0)
    if designation == 'day':
        assert state.stack[-1] is not old_trigger
        assert resolve_top_of_stack(state)
        held = {target.id for target in targets if target.zone == Zone.EXILE}
        assert len(held) == 1
    else:
        held = set()
    assert state.stack[-1] is old_trigger
    assert resolve_top_of_stack(state)
    assert {target.id for target in targets if target.zone == Zone.EXILE} == held


@pytest.mark.parametrize('seat', [1, 2])
def test_entry_projection_leaves_daybound_spell_front_face_up(seat):
    from rules_engine.card_faces import day_night_entry_face
    state, source, _, _ = setup(seat, 'night')
    projection = day_night_entry_face(state, source)
    assert projection.name == 'Moonrage Brute' and projection.selected_face_index == 1
    assert source.name == 'Brutal Cathar' and source.selected_face_index is None
