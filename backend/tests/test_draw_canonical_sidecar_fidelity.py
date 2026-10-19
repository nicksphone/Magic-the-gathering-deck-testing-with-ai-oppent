"""Inspect original inputs before actual draw, inference and paid-cast consumers."""
from copy import deepcopy
from dataclasses import fields
import importlib
import json

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone
from tests.draw_canonical_sidecar import canonical_card, raw_card, reprint
from tests.library_canonical_fixtures import PRINTED


RESTRICTIONS = 'test_draw_restrictions'
EACH = 'test_each_player_draw'
CASES = [
    (RESTRICTIONS, 'test_spirit_caps_each_players_successful_draws_before_replacements', 'Spirit of the Labyrinth', 'resolve_effect'),
    (RESTRICTIONS, 'test_spirit_caps_each_players_successful_draws_before_replacements', 'Thought Reflection', 'resolve_effect'),
    (RESTRICTIONS, 'test_narset_counts_prior_draw_and_resets_for_each_new_turn_after_restore', 'Narset, Parter of Veils', 'resolve_effect'),
    (RESTRICTIONS, 'test_dredge_replacement_does_not_consume_turn_draw_allowance', 'Stinkweed Imp', 'resolve_effect'),
    (RESTRICTIONS, 'test_denied_draw_does_not_lose_to_empty_library_or_fire_draw_events', 'Island', 'resolve_effect'),
    (EACH, 'test_vision_skeins_draws_active_player_first_even_when_other_player_casts', 'Vision Skeins', 'infer_effect_from_oracle'),
    (EACH, 'test_prosperity_x_draws_both_players_then_simultaneous_deckout', 'Prosperity', 'infer_effect_from_oracle'),
    (EACH, 'test_dredge_choice_resumes_remaining_draws_and_other_player', 'Stinkweed Imp', 'infer_effect_from_oracle'),
    (EACH, 'test_one_empty_library_does_not_prevent_other_players_draw', 'Island', 'infer_effect_from_oracle'),
    (EACH, 'test_vision_skeins_on_stack_draws_game_after_both_libraries_empty', 'Vision Skeins', 'take_action'),
]


class Consumed(BaseException):
    pass


def expected_card(name):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    state = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)


@pytest.mark.parametrize('module,body,name,seam', CASES,
                         ids=[case[0] + ':' + case[2] + ':' + case[3] for case in CASES])
def test_original_first_consumer_receives_complete_canonical_printed_facts(monkeypatch, module, body, name, seam):
    original = importlib.import_module('tests.' + module)
    owner = original.RulesEngine if seam == 'take_action' else original
    consumer = getattr(owner, seam)
    expected = expected_card(name)

    def observe(*args, **kwargs):
        state = args[1] if seam == 'take_action' else args[0]
        candidates = list(state.cards.values())
        if seam == 'infer_effect_from_oracle':
            candidates.append(args[1])
        if seam != 'take_action' or args[3].get('type') == 'cast_spell':
            matches = [card for card in candidates if card.name == name]
            if matches:
                actual = matches[0]
                different = sorted(field for field in PRINTED
                                   if getattr(actual, field) != getattr(expected, field))
                assert not different, (name, different)
                raise Consumed
        return consumer(*args, **kwargs)

    monkeypatch.setattr(owner, seam, observe)
    with pytest.raises(Consumed):
        getattr(original, body)()


def test_complete_raws_keep_independent_mutables_and_printed_pose_guard():
    for name in ('Island', 'Spirit of the Labyrinth', 'Thought Reflection',
                 'Narset, Parter of Veils', 'Stinkweed Imp', 'Vision Skeins', 'Prosperity'):
        first, second = raw_card(name), raw_card(name)
        assert first == second and first is not second
        assert first['object'] == 'card' and len(first) > 40
        first['legalities'].clear()
        assert second['legalities'] and raw_card(name) == second
        with pytest.raises(ValueError):
            canonical_card(name, oracle_text='Deliberate noncanonical pose')


def test_reprint_preserves_all_runtime_fields_rng_and_mutable_independence():
    original = importlib.import_module('tests.' + EACH)
    state, _ = original._game()
    card = state.cards[state.players[1].hand[0]]
    before = deepcopy(vars(card))
    rng, facts, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)
    reprint(card, 'Vision Skeins')
    sibling = canonical_card('Vision Skeins', id='independent', owner=1, controller=1, zone=Zone.HAND)
    assert all(getattr(card, field.name) == before[field.name]
               for field in fields(CardInstance) if field.name not in PRINTED)
    assert state.rng.getstate() == rng and state.sideboard_facts == facts and state.starting_decks == decks
    assert all(getattr(card, field) == getattr(sibling, field) for field in PRINTED)
    card.characteristic_record['physical']['name'] = 'Noncanonical independence sentinel'
    card.colors.clear()
    assert sibling.characteristic_record['physical']['name'] == 'Vision Skeins'
    assert sibling.colors == raw_card('Vision Skeins')['colors']
