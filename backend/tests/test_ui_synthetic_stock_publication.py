"""Real fixture functions and serializers; HTTP/SQL boundaries are inert here."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
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
    assert state.sideboard_facts == {}
    assert saved['snapshot']['sideboard_facts'] == {}
    restored = deserialize_match_snapshot(saved['snapshot'])
    assert restored.sideboard_facts == {}
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
    assert state.sideboard_facts == {}
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
    changed = 0
    opted = 0
    for block in fn.body:
        assignments = [node for node in ast.walk(block) if isinstance(node, ast.Assign)]
        changes_source = any(isinstance(part, ast.Attribute) and part.attr in {'name', 'card_faces'}
                             for node in assignments for target in node.targets
                             for part in ast.walk(target))
        calls = [node for node in ast.walk(block) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'publish']
        flags = [keyword.value for call in calls for keyword in call.keywords
                 if keyword.arg == 'capture_original_stock']
        if changes_source:
            changed += 1
            assert len(calls) == 1 and len(flags) == 1
            assert isinstance(flags[0], ast.Constant) and flags[0].value is False
        elif flags:
            raise AssertionError('Unmutated original-stock fixture was opted out')
        opted += len(flags)
    assert changed == opted == 10


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
    assert state.sideboard_facts == {}
    assert any(card.name == 'Spectral Procession' for card in state.cards.values())
    deserialize_match_snapshot(serialize_match_snapshot(state))


def test_existing_fixture_projection_rejects_unapproved_body_change():
    from unittest.mock import patch
    from tests.modal_contract_support import canonical_fixture
    path = Path(__file__).with_name('browser_fixture_server.py')
    original = path.read_text()
    assert original.count('spell.name = "Spectral Procession"') == 1
    changed = original.replace('spell.name = "Spectral Procession"',
                               'spell.name = "Unauthorized replacement"')
    with patch.object(Path, 'read_text', return_value=changed):
        with pytest.raises(AssertionError):
            canonical_fixture('hybrid_payment')
