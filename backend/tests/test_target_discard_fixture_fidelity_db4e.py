"""Observe original source consumers; pure projections are not HTTP acceptance."""
from copy import deepcopy
from dataclasses import fields
import importlib
import json
from types import SimpleNamespace

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from tests.target_discard_canonical_db4e import (
    FIXTURES, PRINTED, canonical_card, raw_card, set_printed,
)


TARGET = 'test_player_target_immunity'
DISCARD = 'test_revealed_hand_discard'
CASES = [
    (TARGET, 'test_leyline_filters_opponent_player_but_allows_controller_and_untargeted_damage', 'Leyline of Sanctity', 'validate_hexproof_shroud_targets', ()),
    (TARGET, 'test_leyline_filters_opponent_player_but_allows_controller_and_untargeted_damage', 'Shock', 'validate_hexproof_shroud_targets', ()),
    (TARGET, 'test_ivory_mask_shroud_blocks_both_players_from_targeting_its_controller', 'Ivory Mask', 'validate_hexproof_shroud_targets', ()),
    (TARGET, 'test_trigger_options_and_resolution_recheck_player_hexproof', 'Aegis of the Gods', 'legal_moves', ()),
    (TARGET, 'test_ai_does_not_choose_protected_opponent_for_burn_spell', 'Lightning Bolt', 'legal_moves', ('Lightning Bolt',)),
    (TARGET, 'test_ai_can_burn_opposing_creature_behind_player_hexproof', 'Grizzly Bears', 'legal_moves', ()),
    (TARGET, 'test_battlefield_target_hints_omit_defended_creature', 'Grizzly Bears', 'legal_moves', ('hexproof',)),
    (DISCARD, 'test_coercion_caster_chooses_from_opponents_revealed_hand', 'Coercion', 'legal_moves', ()),
    (DISCARD, 'test_ai_values_revealed_cards_for_opponents_archetype', 'Counterspell', 'checked_action', ()),
    (DISCARD, 'test_ai_values_revealed_cards_for_opponents_archetype', 'Lightning Bolt', 'checked_action', ()),
    (DISCARD, 'test_thoughtseize_filters_lands_then_loses_life_after_discard_choice', 'Thoughtseize', 'checked_action', ()),
    (DISCARD, 'test_duress_filters_creatures_and_lands_without_life_loss', 'Duress', 'checked_action', ()),
    (DISCARD, 'test_inquisition_filters_by_type_and_mana_value_across_snapshot', 'Inquisition of Kozilek', 'checked_action', ()),
    (DISCARD, 'test_despise_offers_creature_or_planeswalker_only', 'Despise', 'checked_action', ()),
    (DISCARD, 'test_appetite_exiles_only_expensive_revealed_card_across_snapshot', 'Appetite for Brains', 'checked_action', ()),
    (DISCARD, 'test_thoughtseize_filters_lands_then_loses_life_after_discard_choice', 'Forest', 'checked_action', ()),
    (DISCARD, 'test_thoughtseize_filters_lands_then_loses_life_after_discard_choice', 'Lightning Bolt', 'checked_action', ()),
    (DISCARD, 'test_thoughtseize_filters_lands_then_loses_life_after_discard_choice', 'Llanowar Elves', 'checked_action', ()),
    (DISCARD, 'test_inquisition_filters_by_type_and_mana_value_across_snapshot', 'Serra Angel', 'checked_action', ()),
    (DISCARD, 'test_despise_offers_creature_or_planeswalker_only', 'Jace, the Mind Sculptor', 'checked_action', ()),
    (DISCARD, 'test_appetite_exiles_only_expensive_revealed_card_across_snapshot', "Liliana's Caress", 'checked_action', ()),
    (DISCARD, 'test_ai_completes_revealed_exile_choice', 'Serra Angel', 'checked_action', ()),
    (DISCARD, 'test_thoughtseize_reveals_lands_and_loses_life_when_no_card_qualifies', 'Thoughtseize', 'checked_action', ()),
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


def assert_printed(actual, expected):
    different = sorted(field for field in PRINTED if getattr(actual, field) != getattr(expected, field))
    assert not different, (actual.name, different)


@pytest.mark.parametrize('module,body,name,seam,args', CASES,
                         ids=[f'{module}:{body}:{name}' for module, body, name, _, _ in CASES])
def test_original_first_consumer_has_complete_printed_facts(monkeypatch, module, body, name, seam, args):
    original = importlib.import_module('tests.' + module)
    owner = original.RulesEngine if seam == 'legal_moves' else original
    consumer = getattr(owner, seam)
    expected = expected_card(name)
    if body == 'test_battlefield_target_hints_omit_defended_creature':
        expected.keywords = ['hexproof']  # Explicit original noncanonical defense vector.

    def observe(*values, **kwargs):
        state = values[1] if seam == 'legal_moves' else values[0]
        matches = [card for card in state.cards.values() if card.name == name]
        if matches:
            assert_printed(matches[0], expected)
            raise Consumed
        return consumer(*values, **kwargs)

    monkeypatch.setattr(owner, seam, observe)
    call_args = (*args, raw_card(args[0])['oracle_text']) if body == 'test_ai_does_not_choose_protected_opponent_for_burn_spell' else args
    with pytest.raises(Consumed):
        getattr(original, body)(*call_args)


def test_http_installer_projection_stops_before_persistence_not_HTTP_acceptance(monkeypatch):
    original = importlib.import_module('tests.' + TARGET)
    deck = [{'quantity': 60, 'card_name': 'Island'}]
    state = MatchFactory.from_decks(deck, deck, seed=4)
    controller = SimpleNamespace(state=state)

    def before_persist(actual):
        assert actual is controller
        assert_printed(actual.state.cards['shield'], expected_card('Leyline of Sanctity'))
        assert_printed(actual.state.cards['bolt'], expected_card('Shock'))
        raise Consumed

    monkeypatch.setattr(original, 'persist', before_persist)
    with pytest.raises(Consumed):
        original.test_hexproof_player_is_missing_from_http_hints_and_rejected_without_mutation((None, controller))


def test_direct_HTTP_controller_source_stops_before_TestClient_not_HTTP_acceptance(monkeypatch):
    original = importlib.import_module('tests.' + DISCARD)
    make_controller = original.MatchController
    captured = []

    def controller(*args, **kwargs):
        value = make_controller(*args, **kwargs)
        captured.append(value)
        return value

    def before_client(*args, **kwargs):
        assert len(captured) == 1
        value = captured[0]
        cid = value.state.players[1].hand[0]
        assert_printed(value.state.cards[cid], expected_card('Coercion'))
        raise Consumed

    monkeypatch.setattr(original, 'MatchController', controller)
    monkeypatch.setattr(original, 'TestClient', before_client)
    with pytest.raises(Consumed):
        original.test_coercion_reveals_options_only_during_casters_choice()


def test_all_eighteen_full_rows_and_real_factory_templates_are_fresh():
    sources = json.loads((FIXTURES / 'target_discard_db4e/SOURCES.json').read_bytes())
    assert len(sources) == 18
    for name in sources:
        raw = raw_card(name)
        assert raw['object'] == 'card' and len(raw) > 30 and raw['legalities']
        assert_printed(canonical_card(name, id='real', owner=1, controller=1, zone=Zone.HAND), expected_card(name))
        raw['oracle_text'] = 'Deliberate noncanonical protocol mutation'
        raw['legalities'].clear()
        assert raw_card(name)['oracle_text'] != raw['oracle_text'] and raw_card(name)['legalities']


def test_reprint_preserves_runtime_rng_stock_and_captured_boundary():
    original = importlib.import_module('tests.' + DISCARD)
    state, cid = original._state()
    card = state.cards[cid]
    card.counters = {'__damage_marked': 1}
    before = deepcopy(vars(card))
    rng, facts, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    set_printed(card, 'Thoughtseize')
    sibling = canonical_card('Thoughtseize', id='other', owner=1, controller=1, zone=Zone.HAND)
    assert all(getattr(card, field.name) == before[field.name] for field in fields(CardInstance) if field.name not in PRINTED)
    assert state.rng.getstate() == rng and state.sideboard_facts == facts and state.starting_decks == decks
    assert card.characteristic_record == sibling.characteristic_record
    assert card.characteristic_record is not sibling.characteristic_record
    card.characteristic_record.clear()
    card.keywords.append('Deliberate noncanonical vector')
    assert sibling.characteristic_record and 'Deliberate noncanonical vector' not in sibling.keywords
    with pytest.raises(ValueError):
        canonical_card('Thoughtseize', id='forged', owner=1, controller=1, zone=Zone.HAND,
                       characteristic_record={})


def test_direct_constructor_retains_all_original_nonprinted_defaults():
    actual = canonical_card('Shock', id='direct', owner=1, controller=1, zone=Zone.HAND)
    old = CardInstance('direct', 'Anonymous protocol baseline', 1, 1, Zone.HAND, ['Instant'])
    assert all(getattr(actual, field.name) == getattr(old, field.name)
               for field in fields(CardInstance) if field.name not in PRINTED)
