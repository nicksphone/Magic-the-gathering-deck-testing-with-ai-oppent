"""Observe original consumers, not only an independent RAW loader."""
from copy import deepcopy
from dataclasses import fields
import importlib
import json
from types import SimpleNamespace

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from tests.death_artifact_canonical4f86 import (
    FIXTURES, PRINTED, add_card, canonical_card, raw_card, set_printed,
)


DEATH = 'test_death_replacement_canonical'
ARTIFACT = 'test_artifact_graveyard_triggers'
TOKEN = 'test_token_zone_lifecycle'
CASES = [
    (DEATH, 'test_opponent_graveyard_replacement_uses_owner_not_controller', 'Leyline of the Void', 'discard_selected'),
    (DEATH, 'test_opponent_graveyard_replacement_uses_owner_not_controller', 'Grizzly Bears', 'apply_state_based_actions'),
    (DEATH, 'test_opponent_card_replacement_applies_to_resolved_spells_only_for_opponent', 'Lightning Bolt', 'finish_stack_resolution'),
    (DEATH, 'test_opponent_card_replacement_applies_before_source_leaves_in_same_batch', 'Glorious Anthem', 'destroy_all_enchantments'),
    (DEATH, 'test_rest_in_peace_exiles_itself_when_destroyed', 'Rest in Peace', 'destroy_permanent'),
    (DEATH, 'test_rest_in_peace_exiles_a_dying_creature', 'Grizzly Bears', 'apply_state_based_actions'),
    (DEATH, 'test_rest_in_peace_replaces_cycling_and_discard_cost_moves', 'Lonely Sandbar', 'take_action'),
    (DEATH, 'test_rest_in_peace_replaces_cycling_and_discard_cost_moves', 'Putrid Imp', 'apply_activated_costs'),
    (DEATH, 'test_rest_in_peace_exiles_dredge_mill_and_zero_loyalty_planeswalker', 'Stinkweed Imp', 'resolve_dredge'),
    (DEATH, 'test_rest_in_peace_exiles_dredge_mill_and_zero_loyalty_planeswalker', 'Jace, the Mind Sculptor', 'apply_state_based_actions'),
    (DEATH, 'test_real_subtype_replacement_applies_before_simultaneous_source_death', 'Lorcan, Warlock Collector', 'replacement_options'),
    (DEATH, 'test_real_subtype_replacement_applies_before_simultaneous_source_death', 'Arrogant Poet', 'replacement_options'),
    (ARTIFACT, 'test_prior_departure_cannot_trigger_on_later_artifact_death', 'Marionette Master', 'destroy_permanent'),
    (ARTIFACT, 'test_prior_departure_cannot_trigger_on_later_artifact_death', 'Everflowing Chalice', 'destroy_permanent'),
    (ARTIFACT, 'test_simultaneous_wipe_uses_departing_trigger_source_and_artifact', 'Memnite', 'destroy_all_creatures'),
    (TOKEN, 'test_token_in_graveyard_ceases_to_exist_at_next_state_based_check', 'Bastion of Remembrance', 'destroy_permanent'),
    (TOKEN, 'test_token_identity_survives_type_changes_and_legacy_snapshots', 'Grim Haruspex', 'destroy_permanent'),
    (TOKEN, 'test_bounced_token_cannot_pay_discard_cost_or_be_put_into_play', 'Putrid Imp', 'activated_cost_available'),
]


class Consumed(BaseException):
    pass


def expected_card(name):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)


@pytest.mark.parametrize('module,body,name,seam', CASES,
                         ids=[f'{m}:{n}:{s}' for m, _, n, s in CASES])
def test_original_first_consumer_has_full_canonical_printed_facts(monkeypatch, module, body, name, seam):
    original = importlib.import_module('tests.' + module)
    owner = original.RulesEngine if seam == 'take_action' else original
    consumer = getattr(owner, seam)
    expected = expected_card(name)

    def observe(*args, **kwargs):
        state = args[1] if seam == 'take_action' else args[0]
        matches = [card for card in state.cards.values() if card.name == name]
        if matches:
            actual = matches[0]
            compared = PRINTED - {'loyalty'} if name == 'Jace, the Mind Sculptor' else PRINTED
            different = sorted(f for f in compared if getattr(actual, f) != getattr(expected, f))
            assert not different, (name, different)
            if name == 'Jace, the Mind Sculptor':
                assert actual.loyalty == 0
            if name == 'Marionette Master':
                assert actual.counters == {'+1/+1': 2}
            if name == 'Everflowing Chalice':
                assert actual.counters == {'charge': 1}
            raise Consumed
        return consumer(*args, **kwargs)

    monkeypatch.setattr(owner, seam, observe)
    with pytest.raises(Consumed):
        getattr(original, body)()


def test_full_raw_sources_and_independent_factory_projection_are_fresh():
    sources = json.loads((FIXTURES / 'death_artifact4f86/SOURCES.json').read_bytes())
    assert len(sources) == 17
    for name in sources:
        raw = raw_card(name)
        assert raw['object'] == 'card' and len(raw) > 30
        actual, expected = canonical_card(name, id='source', owner=1, controller=1, zone=Zone.HAND), expected_card(name)
        assert all(getattr(actual, f) == getattr(expected, f) for f in PRINTED)
        raw['oracle_text'] = 'Deliberate noncanonical mutation, never printed facts'
        raw['legalities'].clear()
        assert raw_card(name)['oracle_text'] != raw['oracle_text']
        assert raw_card(name)['legalities']


def test_reprint_keeps_runtime_rng_stock_and_mutable_independence():
    original = importlib.import_module('tests.' + DEATH)
    state = original._leyline_state()
    card = state.cards[state.players[1].hand[0]]
    card.counters = {'__damage_marked': 1}
    before = deepcopy(vars(card))
    rng, facts, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    set_printed(card, 'Putrid Imp')
    sibling = canonical_card('Putrid Imp', id='sibling', owner=1, controller=1, zone=Zone.HAND)
    assert all(getattr(card, f.name) == before[f.name] for f in fields(CardInstance) if f.name not in PRINTED)
    assert state.rng.getstate() == rng and state.sideboard_facts == facts and state.starting_decks == decks
    assert card.characteristic_record == sibling.characteristic_record
    assert card.characteristic_record is not sibling.characteristic_record
    card.characteristic_record.clear()
    card.keywords.append('Deliberate protocol mutation')
    assert sibling.characteristic_record and 'Deliberate protocol mutation' not in sibling.keywords
    with pytest.raises(ValueError):
        canonical_card('Putrid Imp', id='forged', owner=1, controller=1, zone=Zone.HAND,
                       oracle_text='Deliberate noncanonical override')


def test_http_constructor_projection_is_not_http_acceptance():
    state = MatchFactory.from_decks([{'quantity': 60, 'card_name': 'Island'}], [], seed=4)
    controller = SimpleNamespace(state=state)
    rng, facts = state.rng.getstate(), deepcopy(state.sideboard_facts)
    card = add_card(controller, 'traveler', 'Doomed Traveler', Zone.BATTLEFIELD, owner=2)
    expected = expected_card('Doomed Traveler')
    assert all(getattr(card, f) == getattr(expected, f) for f in PRINTED)
    assert card.id == 'traveler' and card.owner == card.controller == 2 and not card.summoning_sick
    assert state.players[2].battlefield == ['traveler']
    assert state.rng.getstate() == rng and state.sideboard_facts == facts
