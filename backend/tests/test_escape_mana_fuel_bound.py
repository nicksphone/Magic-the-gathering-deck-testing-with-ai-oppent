"""Do not search mana permutations when that search cannot produce escape fuel."""
import random
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine import mana
from rules_engine.spell_cost_witness import _BoundedPaymentPostcondition, escape_payment_condition
from tests.test_fixed_spell_cost_witness import ROWS as COST_ROWS
from tests.test_ai_recurring_engines import add as canonical_add
from tests.test_spell_cost_overlap_investigation import position, unchanged_root


class SearchRequired(AssertionError):
    pass


ROWS = dict(COST_ROWS)
ROWS.update({raw['name']: raw for line in (Path(__file__).parent /
    'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines()
    if line.strip() for raw in [json.loads(line)]})
ROWS['Opt'] = json.loads((Path(__file__).parent /
    'fixtures/global_flash_timing_audit/opt.json').read_text())
ROWS['Treasure'] = json.loads((Path(__file__).parents[1] /
    'card_data/builtin_token_seed.json').read_text())['Treasure']


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    raw = ROWS[name]
    card = canonical_add(state, name, seat, zone, cards={name: {
        'mana_cost': '', 'colors': [], 'keywords': [], **raw,
        'power': raw.get('power'), 'toughness': raw.get('toughness')}})
    card.summoning_sick = False
    return card


def escape_position(seat, fuel=1, treasure=True):
    state = position(seat)
    spell = add(state, 'Woe Strider', seat, Zone.GRAVEYARD)
    for _ in range(fuel):
        add(state, 'Opt', seat, Zone.GRAVEYARD)
    for name in ('Swamp', 'Swamp', 'Island', 'Mountain', 'Ornithopter'):
        add(state, name, seat)
    add(state, 'Raging Goblin', 3-seat)
    if treasure:
        token = add(state, 'Treasure', seat)
        token.is_token = True
    return state, spell


def require_search(*args, **kwargs):
    raise SearchRequired('The mana planner explored a branch')


def plan(state, seat, spell, condition):
    return mana._plan_payment(state, seat, mana.parse_mana_cost('{3}{B}{B}'),
        payment_context=('spell', {'Creature'}), reserved_card_ids={spell.id},
        post_payment_condition=condition)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fuel', [0, 1, 3])
@pytest.mark.parametrize('treasure', [False, True])
def test_no_graveyard_growth_avoids_all_mana_search(monkeypatch, seat, fuel, treasure):
    state, spell = escape_position(seat, fuel, treasure)
    condition = escape_payment_condition(seat, spell.id, 4)
    monkeypatch.setattr(mana, '_plan_free_payment', require_search)
    rng = random.getstate()
    with unchanged_root(state):
        assert plan(state, seat, spell, condition) is None
    assert random.getstate() == rng


@pytest.mark.parametrize('seat', [1, 2])
def test_pending_resources_do_not_count_as_escape_fuel(monkeypatch, seat):
    state, spell = escape_position(seat, 4)
    held = state.players[seat].graveyard[-1]
    condition = escape_payment_condition(seat, spell.id, 4).with_pending([held])
    monkeypatch.setattr(mana, '_plan_free_payment', require_search)
    with unchanged_root(state):
        assert plan(state, seat, spell, condition) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('context', ['sufficient', 'discard', 'sacrifice', 'self_sacrifice', 'counters', 'custom'])
def test_potential_fuel_or_unproved_context_preserves_search(monkeypatch, seat, context):
    state, spell = escape_position(seat, 4 if context == 'sufficient' else 1)
    condition = escape_payment_condition(seat, spell.id, 4)
    if context == 'discard':
        add(state, 'Skirge Familiar', seat)
        add(state, 'Island', seat, Zone.HAND)
    elif context == 'sacrifice':
        add(state, 'Phyrexian Tower', seat)
    elif context == 'self_sacrifice':
        add(state, 'Blood Pet', seat)
    elif context == 'counters':
        state.cards[state.players[seat].battlefield[-1]].counters['charge'] = 1
    elif context == 'custom':
        condition = _BoundedPaymentPostcondition(lambda state, pending: False)
    monkeypatch.setattr(mana, '_plan_free_payment', require_search)
    with unchanged_root(state), pytest.raises(SearchRequired):
        plan(state, seat, spell, condition)
