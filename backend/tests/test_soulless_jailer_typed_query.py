"""Typed query ABI and real face/method projections, without actions or payments."""
import ast
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from game_state.state import Zone
from rules_engine import graveyard_permissions as permissions
from rules_engine.alternative_casts import spell_cast_view
from rules_engine.card_faces import select_cast_face
from rules_engine.costs import collect_cost_options
from rules_engine.query_context import query_cache
from rules_engine.restrictions import can_cast_in_current_timing
from rules_engine.type_effects import effective_types
from test_soulless_jailer_query_contract import ADVENTURE, add, position, pure_scope, rows


def typed_query():
    query = getattr(permissions, 'spell_cast_prohibited', None)
    assert callable(query), 'The method-projected typed prohibition ABI is missing'
    return query


def projected_types(state, view):
    return tuple(sorted(set(effective_types(state, view))))


@pytest.fixture(scope='module')
def extra_rows():
    directory = Path(__file__).parent / 'fixtures'
    canonical = (directory / 'graveyard_permissions/canonical.json').read_bytes()
    provenance = json.loads((directory / 'graveyard_permissions/provenance.json').read_text())
    assert hashlib.sha256(canonical).hexdigest() == provenance['sha256']
    data = {row['name']: row for row in json.loads(canonical)['data']}
    bestow = (directory / 'bestow.json').read_bytes()
    assert hashlib.sha256(bestow).hexdigest() == '503524a2cd52147926782ea8f1e46d991f0069ccd17a583b9fb3ebf710efa876'
    data.update({row['name']: row for row in json.loads(bestow)})
    return data


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('value', (None, (), [], ['Creature'], {'Creature'},
                                 ([],), ({},), ('Unknown',), ('creature',), (True,)),
                         ids=('none', 'empty', 'list', 'mutable-types', 'set',
                              'nested-list', 'nested-dict', 'unknown', 'wrong-case', 'boolean'))
def test_invalid_projection_is_prohibited_before_cache_hashing(rows, seat, value):
    query = typed_query()
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    with pure_scope(state):
        before = dict(query_cache(state))
        assert query(state, seat, Zone.GRAVEYARD, spell_types=value) is True
        assert query_cache(state) == before


@pytest.mark.parametrize('seat', (1, 2))
def test_card_object_is_not_a_projection(rows, seat):
    query = typed_query()
    state = position(seat)
    card = add(state, rows[ADVENTURE], seat, Zone.GRAVEYARD)
    with pure_scope(state):
        before = dict(query_cache(state))
        assert query(state, seat, card.zone, spell_types=card) is True
        assert query_cache(state) == before


@pytest.mark.parametrize('seat', (1, 2))
def test_projection_cannot_be_omitted(rows, seat):
    query = typed_query()
    state = position(seat)
    with pure_scope(state):
        with pytest.raises(TypeError):
            query(state, seat, Zone.GRAVEYARD)
        assert query_cache(state) == {}


@pytest.mark.parametrize('seat', (1, 2))
def test_same_physical_id_faces_and_canonical_tuples_have_distinct_cache_entries(rows, seat):
    query = typed_query()
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    card = add(state, rows[ADVENTURE], seat, Zone.GRAVEYARD)
    creature, sorcery = (select_cast_face(card, face) for face in (0, 1))
    assert creature.id == sorcery.id == card.id
    with pure_scope(state):
        assert query(state, seat, card.zone, spell_types=projected_types(state, creature)) is False
        assert query(state, seat, card.zone, spell_types=projected_types(state, sorcery)) is True
        size = len(query_cache(state))
        assert query(state, seat, card.zone, spell_types=('Creature', 'Creature')) is False
        assert len(query_cache(state)) == size
        assert query(state, seat, Zone.HAND, spell_types=projected_types(state, sorcery)) is False


@pytest.mark.parametrize('seat', (1, 2))
def test_generic_zone_query_is_not_a_typed_or_policy_precheck(rows, seat):
    query = typed_query()
    state = position(seat)
    add(state, rows['Soulless Jailer'], seat, Zone.BATTLEFIELD)
    card = add(state, rows['Negate'], seat, Zone.EXILE)
    with pure_scope(state):
        assert permissions.zone_cast_prohibited(state, seat, card.zone) is False
        assert query(state, seat, card.zone, spell_types=projected_types(state, card)) is True
        assert permissions.zone_cast_prohibited(state, seat, card.zone) is False


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('zone', (Zone.GRAVEYARD, Zone.EXILE))
def test_real_bestow_method_not_original_creature_controls_typed_admission(rows, extra_rows, seat, zone):
    query = typed_query()
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    card = add(state, extra_rows['Leafcrown Dryad'], seat, zone)
    before = pickle.dumps(state, protocol=5)
    creature, aura = (spell_cast_view(card, method) for method in ('base', 'bestow'))
    assert creature.id == aura.id == card.id
    assert creature.types == ['Enchantment', 'Creature'] and aura.types == ['Enchantment']
    assert creature.oracle_text == aura.oracle_text == extra_rows[card.name]['oracle_text']
    assert pickle.dumps(state, protocol=5) == before
    with pure_scope(state):
        assert query(state, seat, zone, spell_types=projected_types(state, creature)) is False
        assert query(state, seat, zone, spell_types=projected_types(state, aura)) is True
        assert can_cast_in_current_timing(state, creature, seat)[0] is True
        assert can_cast_in_current_timing(state, aura, seat)[0] is False


@pytest.mark.parametrize('seat', (1, 2))
def test_effect_resolution_does_not_bypass_typed_prohibition(rows, seat):
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    card = add(state, rows['Negate'], seat, Zone.EXILE)
    with pure_scope(state):
        assert can_cast_in_current_timing(state, card, seat, during_resolution=True)[0] is False


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('zone', (Zone.GRAVEYARD, Zone.EXILE))
def test_complete_effect_cost_offers_use_selected_face_before_return(rows, seat, zone):
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    card = add(state, rows[ADVENTURE], seat, zone)
    creature, sorcery = (select_cast_face(card, face) for face in (0, 1))
    with pure_scope(state):
        assert [option.id for option in collect_cost_options(state, seat, creature, without_mana=True)] == ['base']
        assert collect_cost_options(state, seat, sorcery, without_mana=True) == []


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('mode', ('inactive', 'suppressed'))
def test_typed_query_observes_actual_source_presence_and_suppression(rows, seat, mode):
    query = typed_query()
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat,
        Zone.HAND if mode == 'inactive' else Zone.BATTLEFIELD)
    if mode == 'suppressed':
        add(state, rows['Humility'], seat, Zone.BATTLEFIELD)
    card = add(state, rows['Negate'], seat, Zone.GRAVEYARD)
    with pure_scope(state):
        assert query(state, seat, card.zone, spell_types=projected_types(state, card)) is False


@pytest.mark.parametrize('seat', (1, 2))
def test_existing_cage_all_spell_and_creature_entry_prohibitions_win(rows, extra_rows, seat):
    query = typed_query()
    state = position(seat)
    add(state, extra_rows["Grafdigger's Cage"], 3 - seat, Zone.BATTLEFIELD)
    for zone in (Zone.GRAVEYARD, Zone.LIBRARY):
        creature = add(state, rows[ADVENTURE], seat, zone)
        noncreature = add(state, rows['Negate'], seat, zone)
        land = add(state, rows['Forest'], seat, zone)
        with pure_scope(state):
            for card in (creature, noncreature):
                assert query(state, seat, zone, spell_types=projected_types(state, card)) is True
                assert permissions.zone_cast_prohibited(state, seat, zone) is True
            assert permissions.battlefield_entry_prohibited(state, creature.id) is True
            assert permissions.battlefield_entry_prohibited(state, land.id) is False


@pytest.mark.parametrize('seat', (1, 2))
def test_stack_entry_is_not_graveyard_entry(rows, seat):
    state = position(seat)
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    target = add(state, rows['Shuko'], seat, Zone.HAND)
    state.players[seat].hand.remove(target.id)
    target.zone = Zone.STACK  # Query fixture only; no fabricated stack item or action.
    with pure_scope(state):
        assert permissions.battlefield_entry_prohibited(state, target.id) is False


@pytest.mark.parametrize('seat', (1, 2))
def test_new_query_scope_reobserves_source_without_persistent_cache(rows, seat):
    query = typed_query()
    state = position(seat)
    card = add(state, rows['Negate'], seat, Zone.EXILE)
    with pure_scope(state):
        assert query(state, seat, card.zone, spell_types=projected_types(state, card)) is False
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    with pure_scope(state):
        assert query(state, seat, card.zone, spell_types=projected_types(state, card)) is True


@pytest.mark.parametrize('prefix,suffix,matched', (
    ('', '', True), ('  ', '  ', True), ('', '\nDraw a card.', True),
    ('', ' Draw a card.', False), ('', ' (Draw a card.)', False),
    ('If you control an artifact, ', '', False), ('', ' unless its owner pays {1}.', False),
    ('', ' (Reminder text.)', False), ('', ' and libraries.', False),
))
def test_raw_paragraph_grammar_does_not_erase_unknown_conditions_or_parentheses(rows, prefix, suffix, matched):
    # Synthetic parser strings only: never assign altered Oracle to a gameplay card.
    raw_clauses = getattr(permissions, '_raw_clauses', None)
    assert callable(raw_clauses), 'Complete raw paragraph matching is missing'
    for paragraph in rows['Soulless Jailer']['oracle_text'].splitlines():
        assert (paragraph.lower() in raw_clauses(prefix + paragraph + suffix)) is matched


def test_only_new_branches_use_raw_complete_paragraphs():
    tree = ast.parse(Path(permissions.__file__).read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ('_spell_cast_prohibited', 'battlefield_entry_prohibited'):
        assert name in functions
        calls = {node.func.id for node in ast.walk(functions[name])
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        assert '_raw_clauses' in calls
    assert '_clauses' not in {node.func.id for node in ast.walk(functions['_spell_cast_prohibited'])
                             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
