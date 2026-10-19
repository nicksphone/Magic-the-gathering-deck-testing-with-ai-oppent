"""Whole pure module; no claim to execute the two HTTP-containing modules whole."""
import hashlib
import json

import pytest

from tests.library_canonical_fixtures import (
    FIXTURES, RANKING_NAMES, RANKING_PROVENANCE_SHA, canonical_card, ranking_raw_card,
)
from tests.test_library_fixture_fidelity import (
    assert_printed, test_structural_forest_operands_are_not_reported_as_printed_fidelity as check_vector,
)


@pytest.mark.parametrize('name', RANKING_NAMES)
def test_complete_ranking_raw_and_materialized_facts_are_independent(name):
    directory = FIXTURES / 'library_ranking_vectors'
    data = (directory / 'PROVENANCE.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == RANKING_PROVENANCE_SHA
    proof = json.loads(data)
    assert set(proof['objects']) == set(RANKING_NAMES)
    assert proof['complete_object_count'] == 7 and proof['network_requests'] == 0
    assert proof['source_bulk_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
    assert proof['Oracle_modified'] is False and proof['original_HTTP_wire_body_claim'] is False
    raw, other = ranking_raw_card(name), ranking_raw_card(name)
    assert len(raw) > 50 and raw['object'] == 'card' and raw['name'] == name
    assert raw == other and raw is not other
    assert raw['legalities'] is not other['legalities']
    raw['legalities'].clear()
    assert other == ranking_raw_card(name) and other['legalities']
    first = canonical_card(name, id='ranking-first', owner=1, controller=1)
    second = canonical_card(name, id='ranking-second', owner=1, controller=1)
    assert_printed(first, other)
    assert_printed(second, other)
    assert first is not second and first.colors is not second.colors
    first.colors.clear()
    first.counters['ranking-independence'] = 1
    assert second.colors == other['colors'] and second.counters == {}


@pytest.mark.parametrize('module,test_name,kind', (
    ('top_card_choices', 'test_ai_top_three_choice_uses_resolution_time_cards', 'Sorcery'),
    ('library_search_rules', 'test_ai_topdeck_put_chooses_stronger_creature_at_resolution', 'Creature'),
))
def test_first_consumer_fidelity_forwards_into_original_scenario(monkeypatch, module, test_name, kind):
    check_vector(monkeypatch, module, test_name, kind)


def test_automatic_top_three_first_consumer_forwards_original_scenario(monkeypatch):
    from game_state.state import Zone
    from rules_engine.mana import mana_value
    from tests import test_top_card_choices as original

    expected = ('Preordain', 'Divination', 'Explore')
    delegate = original.resolve_effect
    captured = []

    def capture(state, *args, **kwargs):
        ids = list(state.players[1].library[-3:])
        assert len(ids) == len(set(ids)) == 3
        cards = [state.cards[cid] for cid in ids]
        assert [mana_value(card.mana_cost) for card in cards] == [1, 3, 2]
        for cid, card, name in zip(ids, cards, expected):
            assert card.id == cid and card.zone == Zone.LIBRARY
            assert card.owner == card.controller == 1
            assert_printed(card, ranking_raw_card(name))
        captured.append(ids)
        return delegate(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(original, 'resolve_effect', capture)
        original.test_top_three_hand_exile_bottom_choice_has_temporary_play_permission()
    assert len(captured) == 1
