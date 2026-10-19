"""Real fixture functions and serializers; HTTP/SQL boundaries are inert here."""
import ast
from collections import Counter
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from ai.sideboard_facts import copy_facts
from game_state.serializers import (deserialize_match_snapshot, serialize_match,
                                    serialize_match_snapshot)
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


SYNTHETIC_STOCK_KINDS = (
    'snow_payment', 'non_snow_payment', 'compleated_payment',
    'phyrexian_payment', 'hybrid_payment', 'thoughtseize', 'duress',
    'inquisition', 'despise', 'appetite', 'revealed_discard',
    'each_player_discard', 'company', 'iteration', 'search',
)


# Declarative original-stock expectations, not read from the scene producer.
# Native copy indices refer to the two real seeded 60-card shuffles.
SCENE_STOCK = {
    'snow_payment': ('Forest', {'p1-053': 'Snow-Covered Forest', 'p1-060': 'Icehide Golem'}),
    'non_snow_payment': ('Forest', {'p1-060': 'Icehide Golem'}),
    'compleated_payment': ('Island', {'p1-060': 'Tamiyo, Compleated Sage'}),
    'phyrexian_payment': ('Forest', {'p1-060': 'Mutagenic Growth'}),
    'hybrid_payment': ('Plains', {'p1-060': 'Spectral Procession'}),
    'thoughtseize': ('Swamp', {'p1-060': 'Thoughtseize', 'p2-060': 'Forest',
                            'p2-059': 'Lightning Bolt', 'p2-058': 'Llanowar Elves'}),
    'duress': ('Swamp', {'p1-060': 'Duress', 'p2-060': 'Forest',
                       'p2-059': 'Lightning Bolt', 'p2-058': 'Llanowar Elves'}),
    'inquisition': ('Swamp', {'p1-060': 'Inquisition of Kozilek', 'p2-060': 'Forest',
                            'p2-059': 'Lightning Bolt', 'p2-058': 'Llanowar Elves',
                            'p2-057': 'Serra Angel'}),
    'despise': ('Swamp', {'p1-060': 'Despise', 'p2-060': 'Forest',
                        'p2-059': 'Lightning Bolt', 'p2-058': 'Llanowar Elves',
                        'p2-057': 'Jace, the Mind Sculptor'}),
    'appetite': ('Swamp', {'p1-060': 'Appetite for Brains', 'p2-060': 'Forest',
                         'p2-059': 'Lightning Bolt', 'p2-058': 'Llanowar Elves',
                         'p2-057': 'Serra Angel'}),
    'revealed_discard': ('Swamp', {'p1-060': 'Coercion'}),
    'each_player_discard': ('Swamp', {'p1-060': 'Delirium Skeins'}),
    'company': ('Forest', {'p2-048': 'Grizzly Bears', 'p2-049': 'Llanowar Elves',
                           'p2-050': 'Island', 'p2-051': 'Plains',
                           'p2-052': 'Swamp', 'p2-053': 'Mountain'}),
    'iteration': ('Forest', {'p2-051': 'Lightning Bolt', 'p2-052': 'Counterspell',
                             'p2-053': 'Llanowar Elves'}),
    'search': ('Forest', {'p2-052': 'Llanowar Elves', 'p2-053': 'Grizzly Bears'}),
}


def assert_native_scene_stock(state, kind):
    basic, replacements = SCENE_STOCK[kind]
    expected = {
        f'p{seat}-{index:03d}': {
            'owner': seat, 'stock_key': replacements.get(f'p{seat}-{index:03d}', basic),
        }
        for seat in (1, 2) for index in range(1, 61)
    }
    facts = state.sideboard_facts
    assert set(facts) == {'version', 'game_id', 'complete', 'capture_version',
                          'coverage_ok', 'terminal_winner', 'inventory', 'seats'}
    assert facts['version'] == 1 and facts['game_id'] == state.id
    assert facts['capture_version'] == 3 and facts['coverage_ok'] is True
    assert facts['complete'] is False and facts['terminal_winner'] is None
    assert facts['inventory'] == expected
    assert copy_facts(facts, state) == facts
    for seat in (1, 2):
        actual = Counter()
        for row in state.starting_decks[seat]:
            actual[row['card_name']] += row['quantity']
        assert actual == Counter(binding['stock_key'] for binding in expected.values()
                                 if binding['owner'] == seat)
    for cid, binding in expected.items():
        card = state.cards[cid]
        assert card.owner == binding['owner']
        assert card.characteristic_record['physical']['name'] == binding['stock_key']
        assert card.printed_characteristics.get('name', card.name) == binding['stock_key']
        assert card.card_faces == []


def projected_fixture():
    path = Path(__file__).with_name('browser_fixture_server.py')
    tree = ast.parse(path.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'fixture', 'publish'}]
    assert len(functions) == 2
    for node in functions:
        node.decorator_list = []
    saved = {}

    def persist(_repository, match):
        saved['state'] = match.state
        saved['snapshot'] = serialize_match_snapshot(match.state)

    def get_match(match_id):
        state = saved['state']
        assert state.id == match_id
        saved['public'] = serialize_match(state)
        return state

    namespace = {
        '__file__': str(path), 'Path': Path, 'ACTIVE_MATCHES': {},
        'AIAgent': AIAgent, 'RulesEngine': RulesEngine,
        'MatchFactory': MatchFactory, 'CardInstance': CardInstance,
        'StackItem': StackItem, 'Step': Step, 'Zone': Zone,
        'MatchController': SimpleNamespace, 'engine': None,
        'Session': lambda _engine: nullcontext(None),
        'Repository': lambda _session: None,
        '_persist_active_match': persist, 'get_match': get_match,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace, saved


@pytest.mark.parametrize('kind', SYNTHETIC_STOCK_KINDS)
def test_every_explicit_factory_source_mutation_publishes_unknown_stock(kind):
    namespace, saved = projected_fixture()
    state = namespace['fixture'](face_kind=kind)
    assert_native_scene_stock(state, kind)
    assert saved['snapshot']['sideboard_facts'] == state.sideboard_facts
    restored = deserialize_match_snapshot(saved['snapshot'])
    assert_native_scene_stock(restored, kind)
    assert serialize_match_snapshot(restored) == saved['snapshot']
    assert 'sideboard_facts' not in saved['public']


def test_exact_hybrid_browser_cast_still_pays_three_white_lands():
    namespace, saved = projected_fixture()
    state = namespace['fixture'](face_kind='hybrid_payment')
    spell = next(state.cards[cid] for cid in state.players[1].hand
                 if state.cards[cid].name == 'Spectral Procession')
    from rules_engine.costs import collect_cost_options
    options = collect_cost_options(state, 1, spell)
    assert len(options) == 1 and options[0].mana_cost == spell.mana_cost
    state = checked_action(state, RulesEngine(), 1, {
        'type': 'cast_spell', 'card_id': spell.id,
        'hybrid_choices': ['W', 'W', 'W'],
        'cost_choice': {'id': options[0].id},
    })
    assert len(state.stack) == 1 and state.stack[0].label == 'Spectral Procession'
    assert len([state.cards[cid] for cid in state.players[1].battlefield
                if state.cards[cid].name == 'Plains' and state.cards[cid].tapped]) == 3
    assert state.cards[spell.id].mana_cost == '{2/W}{2/W}{2/W}'
    assert state.cards[spell.id].oracle_text == 'Create three 1/1 white Spirit creature tokens with flying.'
    assert_native_scene_stock(state, 'hybrid_payment')
    deserialize_match_snapshot(serialize_match_snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_default_publisher_preserves_native_v3_stock_and_checked_land(seat):
    namespace, saved = projected_fixture()
    deck = [{'quantity': 60, 'card_name': 'Plains'}]
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=31)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    original = deepcopy(state.sideboard_facts)
    namespace['publish'](state, deck)
    assert state.sideboard_facts == original and original['capture_version'] == 3
    assert saved['snapshot']['sideboard_facts'] == original
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'play_land', 'card_id': state.players[seat].hand[0],
    })
    assert state.sideboard_facts['capture_version'] == 3
    deserialize_match_snapshot(serialize_match_snapshot(state))


@pytest.mark.parametrize('seat', [1, 2])
def test_default_publisher_does_not_hide_forged_original_owner(seat):
    namespace, _ = projected_fixture()
    deck = [{'quantity': 60, 'card_name': 'Plains'}]
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=31)
    cid = state.players[seat].hand[0]
    state.cards[cid].owner = 3-seat
    original = deepcopy(state.sideboard_facts)
    with pytest.raises(ValueError, match='Invalid sideboard inventory binding'):
        namespace['publish'](state, deck)
    assert state.sideboard_facts == original


@pytest.mark.parametrize('kind', ['land', 'adventure', 'split', 'aftermath'])
def test_canonical_face_stock_remains_captured_not_blanket_unknown(kind):
    namespace, saved = projected_fixture()
    state = namespace['fixture'](face_kind=kind)
    assert state.sideboard_facts['capture_version'] == 3
    assert state.sideboard_facts['inventory']
    assert saved['snapshot']['sideboard_facts'] == state.sideboard_facts
    deserialize_match_snapshot(saved['snapshot'])


def test_all_printed_source_mutation_branches_have_explicit_optout_and_only_those():
    path = Path(__file__).with_name('browser_fixture_server.py')
    fn = next(node for node in ast.parse(path.read_text()).body
              if isinstance(node, ast.FunctionDef) and node.name == 'fixture')
    # Retain the historical node name; real birth inputs no longer need retags.
    assert set(SCENE_STOCK) == set(SYNTHETIC_STOCK_KINDS)
    for block in fn.body:
        assignments = [node for node in ast.walk(block) if isinstance(node, ast.Assign)]
        changes_source = any(isinstance(part, ast.Attribute) and part.attr in {'name', 'card_faces'}
                             for node in assignments for target in node.targets
                             for part in ast.walk(target))
        calls = [node for node in ast.walk(block) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'publish']
        flags = [keyword.value for call in calls for keyword in call.keywords
                 if keyword.arg == 'capture_original_stock']
        assert changes_source is False
        assert flags == []


@pytest.mark.parametrize('flag', [0, 'False'])
def test_explicit_publication_flag_rejects_non_boolean_without_mutation(flag):
    namespace, saved = projected_fixture()
    deck = [{'quantity': 60, 'card_name': 'Plains'}]
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=31)
    before = serialize_match_snapshot(state)
    with pytest.raises(TypeError, match='capture_original_stock must be bool'):
        namespace['publish'](state, deck, capture_original_stock=flag)
    assert saved == {}
    assert serialize_match_snapshot(state) == before


def test_existing_pinned_fixture_projection_retains_explicit_stock_contract():
    from tests.modal_contract_support import canonical_fixture
    state = canonical_fixture('hybrid_payment')
    assert_native_scene_stock(state, 'hybrid_payment')
    assert any(card.name == 'Spectral Procession' for card in state.cards.values())
    deserialize_match_snapshot(serialize_match_snapshot(state))


def test_existing_fixture_projection_rejects_unapproved_body_change():
    from unittest.mock import patch
    from tests import modal_contract_support as support
    path = Path(__file__).with_name('browser_fixture_server.py')
    original = path.read_text()
    marker = 'scene_decks(921, "Plains", {1: {60: "Spectral Procession"}})'
    assert original.count(marker) == 1
    changed = original.replace(marker, marker.replace('Spectral Procession', 'Unauthorized replacement'))
    calls = []

    def forbidden_birth(*args, **kwargs):
        calls.append('constructor')
        raise AssertionError('Constructor must not be reached')

    def forbidden_consumer(*args, **kwargs):
        calls.append('consumer')
        raise AssertionError('Consumer must not be reached')

    read_text = Path.read_text

    def substitute(subject, *args, **kwargs):
        return changed if subject == path else read_text(subject, *args, **kwargs)

    with patch.object(Path, 'read_text', substitute), \
            patch.object(support.MatchFactory, 'from_decks', side_effect=forbidden_birth), \
            patch.object(support, 'RulesEngine', side_effect=forbidden_consumer):
        with pytest.raises(AssertionError):
            support.canonical_fixture('hybrid_payment')
    assert calls == []


def test_explicit_publisher_optout_is_unknown_stock_negative_protocol():
    from tests.browser_positive83_canonical import entry
    namespace, saved = projected_fixture()
    deck = [entry('Plains', 60)]
    state = MatchFactory.from_decks(deck, deepcopy(deck), seed=31)
    before = serialize_match_snapshot(state)
    assert before['sideboard_facts']['capture_version'] == 3
    assert len(before['sideboard_facts']['inventory']) == 120
    namespace['publish'](state, deck, capture_original_stock=False)
    assert state.sideboard_facts == {}
    assert saved['snapshot'] == {**before, 'sideboard_facts': {}}
    restored = deserialize_match_snapshot(saved['snapshot'])
    assert restored.sideboard_facts == {}
    assert serialize_match_snapshot(restored) == saved['snapshot']
    assert 'sideboard_facts' not in saved['public']
