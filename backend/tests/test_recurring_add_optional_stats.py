"""Real canonical rows may omit creature-only stats; no Oracle data is patched."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.card_types import printed_card_types
from tests.canonical_positive_fixtures import raw_card
from tests.test_ai_recurring_engines import CARDS, add, fixture
from tests.test_spell_entry_counters import ROWS as SPELLS


LANDS = {'Hallowed Fountain': raw_card('Hallowed Fountain')}


@pytest.mark.parametrize('name,rows', [
    ('The Phasing of Zhalfir', SPELLS),
    ('Hallowed Fountain', LANDS),
])
@pytest.mark.parametrize('player,zone', [(1, Zone.BATTLEFIELD), (2, Zone.HAND)])
def test_complete_noncreature_RAW_without_stats_preserves_facts_and_runtime_role(name, rows, player, zone):
    raw = rows[name]
    assert raw['object'] == 'card' and len(raw) > 30
    assert 'power' not in raw and 'toughness' not in raw
    before = deepcopy(rows)
    state = fixture()
    rng, stock, decks = state.rng.getstate(), deepcopy(state.sideboard_facts), deepcopy(state.starting_decks)

    card = add(state, name, player, zone, cards=rows)

    assert state.cards[card.id] is card
    assert getattr(state.players[player], zone.value).count(card.id) == 1
    assert (card.name, card.owner, card.controller, card.zone) == (name, player, player, zone)
    assert card.power is None and card.toughness is None
    assert card.types == printed_card_types(raw['type_line'])
    assert (card.type_line, card.mana_cost, card.oracle_text, card.keywords, card.colors) == (
        raw['type_line'], raw['mana_cost'], raw['oracle_text'], raw['keywords'], raw['colors'])
    assert rows == before
    assert state.rng.getstate() == rng and state.sideboard_facts == stock and state.starting_decks == decks


@pytest.mark.parametrize('name,rows', [('Blood Artist', CARDS), ('Walking Ballista', SPELLS)])
def test_present_creature_stats_keep_original_integer_conversion(name, rows):
    raw, before = rows[name], deepcopy(rows)
    card = add(fixture(), name, cards=rows)
    assert (card.power, card.toughness) == (int(raw['power']), int(raw['toughness']))
    assert rows == before


def test_existing_explicit_null_stats_remain_null():
    raw = CARDS['The Meathook Massacre']
    assert raw['power'] is None and raw['toughness'] is None
    card = add(fixture(), raw['name'])
    assert card.power is None and card.toughness is None
    assert card.oracle_text == raw['oracle_text']


@pytest.mark.parametrize('field', ['power', 'toughness'])
def test_present_malformed_stat_is_not_silently_defaulted(field):
    # Deliberately invalid protocol input, not a canonical-card claim.
    raw = deepcopy(SPELLS['Walking Ballista'])
    raw[field] = 'deliberately-not-a-number'
    rows, state = {raw['name']: raw}, fixture()
    before, ids = deepcopy(rows), set(state.cards)
    with pytest.raises(ValueError):
        add(state, raw['name'], cards=rows)
    assert rows == before and set(state.cards) == ids
