"""Card-type boundary projection; real fixture AST, queries and paid casts."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.card_types import CARD_TYPES
from rules_engine.costs import CostOption, check_cost_option_available, collect_cost_options
from rules_engine.engine import RulesEngine
from rules_engine.graveyard_permissions import spell_cast_prohibited
from rules_engine.query_context import query_cache
from rules_engine.restrictions import can_cast_in_current_timing
from rules_engine.type_effects import effective_types
from tests.test_compleated_loyalty_full import RAW, act, clean, raw_card, settle
from test_soulless_jailer_query_contract import add, position, pure_scope, rows


def original_compleated_fixture():
    """Run the entire original function, replacing only its publication boundary."""
    path = Path(__file__).with_name('browser_fixture_server.py')
    tree = ast.parse(path.read_text())
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'fixture')
    function = deepcopy(function)
    function.decorator_list = []
    publications = []

    def publish(state, deck):
        publications.append((state, deck))
        return state

    namespace = {'MatchFactory': MatchFactory, 'Step': Step, 'publish': publish}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    state = namespace['fixture'](face_kind='compleated_payment')
    assert len(publications) == 1 and publications[0][0] is state
    assert publications[0][1] == [{'quantity': 60, 'card_name': 'Island'}]
    card, = [card for card in state.cards.values() if card.name == RAW['name']]
    assert card.zone == Zone.HAND and card.controller == 1
    assert card.types == ['Legendary', 'Planeswalker']
    assert not any(player.battlefield for player in state.players.values())
    return state, card


@pytest.mark.parametrize('boundary', ('timing', 'collect', 'availability'))
def test_original_fixture_compleated_payment_admission(boundary):
    state, card = original_compleated_fixture()
    before = serialize_match_snapshot(state)
    assert effective_types(state, card) == ['Legendary', 'Planeswalker']
    # The public typed query stays strict; callers must project its domain.
    assert spell_cast_prohibited(state, 1, card.zone,
                                 spell_types=('Legendary', 'Planeswalker')) is True
    assert spell_cast_prohibited(state, 1, card.zone, spell_types=('Planeswalker',)) is False
    if boundary == 'timing':
        assert can_cast_in_current_timing(state, card, 1)[0] is True
    elif boundary == 'collect':
        options = collect_cost_options(state, 1, card)
        assert [option.id for option in options] == ['base']
        assert options[0].mana_cost == card.mana_cost
    else:
        option = CostOption('base', 'Cast', card.mana_cost)
        assert check_cost_option_available(state, 1, card, option) is True
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('branch,loyalty,life', (('G', 5, 20), ('U', 5, 20), ('P', 3, 18)))
@pytest.mark.parametrize('representation', ('factory', 'printed-supertype-list'))
def test_full_canonical_paid_compleated_cast(seat, branch, loyalty, life, representation):
    state = clean(seat)
    card = raw_card(state, RAW, seat, Zone.HAND)
    if representation == 'printed-supertype-list':
        # The legacy fixture representation, derived from the unchanged full row.
        card.types = RAW['type_line'].split(' \u2014 ', 1)[0].split()
        assert card.types == ['Legendary', 'Planeswalker']
    assert card.oracle_text == RAW['oracle_text'] and card.loyalty == 5
    state.players[seat].mana_pool = {'C': 2, 'G': 1, 'U': 1}
    if branch != 'P':
        state.players[seat].mana_pool[branch] += 1
    before = serialize_match_snapshot(state)
    assert can_cast_in_current_timing(state, card, seat)[0] is True
    option, = collect_cost_options(state, seat, card)
    assert option.id == 'base' and option.mana_cost == RAW['mana_cost']
    assert check_cost_option_available(state, seat, card, option) is True
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == card.id
               for move in RulesEngine().legal_moves(state, seat))
    assert serialize_match_snapshot(state) == before
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                             'cost_choice': {'id': 'base'}, 'hybrid_choices': [branch]})
    assert state.cards[card.id].zone == Zone.STACK and len(state.stack) == 1
    frame = state.stack[-1]
    assert frame.source_card_id == card.id and frame.controller == seat
    assert frame.payload['__phyrexian_life_symbols'] == (1 if branch == 'P' else 0)
    assert not any(state.players[seat].mana_pool.values())
    assert state.players[seat].life == life and state.players[3 - seat].life == 20
    state = settle(state)
    assert state.cards[card.id].zone == Zone.BATTLEFIELD
    assert state.cards[card.id].loyalty == loyalty
    assert state.cards[card.id].oracle_text == RAW['oracle_text']
    assert state.players[seat].life == life and state.players[3 - seat].life == 20
    assert state.spells_cast_this_turn[seat] == 1 and not state.stack
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('value', (('Legendary', 'Planeswalker'), ('Unknown', 'Creature'),
                                  ('Unknown',), (), ['Creature'], (True,)))
def test_direct_invalid_typed_query_stays_strict_before_cache(rows, seat, value):
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    with pure_scope(state):
        before = dict(query_cache(state))
        for zone in (Zone.HAND, Zone.GRAVEYARD, Zone.EXILE):
            assert spell_cast_prohibited(state, seat, zone, spell_types=value) is True
        assert query_cache(state) == before


@pytest.mark.parametrize('seat', (1, 2))
def test_empty_card_type_projection_remains_denied_root_pure(seat):
    state = clean(seat)
    card = raw_card(state, RAW, seat, Zone.HAND)
    # Representation-only negative, not a fabricated supported Oracle family.
    card.types = ['Legendary', 'Unknown']
    state.players[seat].mana_pool = {'C': 2, 'G': 2, 'U': 1}
    assert not (set(effective_types(state, card)) & CARD_TYPES)
    before = serialize_match_snapshot(state)
    assert can_cast_in_current_timing(state, card, seat)[0] is False
    assert collect_cost_options(state, seat, card) == []
    assert check_cost_option_available(state, seat, card,
                                       CostOption('base', 'Cast', card.mana_cost)) is False
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('qualifier', ('Legendary', 'UnknownQualifier'))
def test_non_card_type_tokens_do_not_change_caller_domain(seat, qualifier):
    state = clean(seat)
    card = raw_card(state, RAW, seat, Zone.HAND)
    # Domain projection does not grant support for an unknown Oracle instruction.
    card.types = [qualifier, 'Planeswalker']
    state.players[seat].mana_pool = {'C': 2, 'G': 2, 'U': 1}
    before = serialize_match_snapshot(state)
    assert can_cast_in_current_timing(state, card, seat)[0] is True
    option, = collect_cost_options(state, seat, card)
    assert check_cost_option_available(state, seat, card, option) is True
    assert spell_cast_prohibited(state, seat, card.zone,
                                 spell_types=tuple(card.types)) is True
    assert serialize_match_snapshot(state) == before


def test_canonical_primary_row_not_shortened_or_replaced():
    directory = Path(__file__).parent / 'fixtures/compleated_loyalty_full'
    assert hashlib.sha256((directory / 'tamiyo.raw.json').read_bytes()).hexdigest() == (
        'dcbfd8d6648620cf3a466af951b7db1aee9b40f9fa0956edc9c0aba1a2dbea55')
