"""Canonical shared position and actual browser route, without HTTP or SQL."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.agent import AIAgent
from game_state.serializers import (deserialize_match_snapshot, serialize_match,
                                    serialize_match_snapshot)
from game_state.state import MatchFactory, Zone
from tests.regression_agent_wave2 import support


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_shared_position_roundtrip_declares_unknown_original_stock(seat):
    state = support.position(seat)
    assert state.id == 'wave2-seed-731'
    assert state.active_player == state.priority_player == seat
    snapshot = serialize_match_snapshot(state)
    assert state.sideboard_facts == snapshot['sideboard_facts'] == {}
    restored = support.resume(state)
    assert serialize_match_snapshot(restored) == snapshot
    assert restored.sideboard_facts == {}
    assert 'sideboard_facts' not in serialize_match(restored)


def browser_position(seat):
    path = Path(__file__).with_name('casting_trigger_browser_fixture.py')
    tree = ast.parse(path.read_text())
    route = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'casting_fixture')
    route.decorator_list = []
    stored = {}

    def persist(_repository, match):
        stored['snapshot'] = serialize_match_snapshot(match.state)
        stored['state'] = match.state

    namespace = {
        'position': support.position, 'add': support.add, 'RULES': support.RULES,
        'Zone': Zone, 'AIAgent': AIAgent, 'MatchController': SimpleNamespace,
        'ACTIVE_MATCHES': {}, 'engine': None,
        'Session': lambda _engine: nullcontext(None), 'Repository': lambda _session: None,
        '_persist_active_match': persist, 'get_match': lambda _id: stored['state'],
    }
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(path), 'exec'), namespace)
    state = namespace['casting_fixture'](seat)
    assert stored['snapshot'] == serialize_match_snapshot(state)
    return state


@pytest.mark.parametrize('seat', [1, 2])
def test_exact_browser_fixture_paid_growth_resumes_and_preserves_order(seat):
    state = browser_position(seat)
    spell = next(state.cards[cid] for cid in state.players[seat].hand
                 if state.cards[cid].name == 'Incremental Growth')
    bears = list(state.players[seat].battlefield)
    assert len(bears) == 3 and all(state.cards[cid].name == 'Grizzly Bears' for cid in bears)
    assert spell.oracle_text == support.ROWS['Incremental Growth']['oracle_text']
    assert spell.mana_cost == support.ROWS['Incremental Growth']['mana_cost']
    assert state.sideboard_facts == {}
    state = support.cast(state, spell, {'target_card_ids': bears})
    assert len(state.stack) == 1 and state.stack[-1].label == 'Incremental Growth'
    assert sum(state.players[seat].mana_pool.values()) == 0
    state = support.settle(support.resume(state))
    assert [state.cards[cid].counters.get('+1/+1', 0) for cid in bears] == [1, 2, 3]
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert state.sideboard_facts == {}
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot


@pytest.mark.parametrize('seat', [1, 2])
def test_native_factory_stock_capture_remains_bound_without_synthetic_id(seat):
    state = MatchFactory.from_decks([support.entry('Mountain', 20)],
                                    [support.entry('Island', 20)], seed=support.SEED)
    original = deepcopy(state.sideboard_facts)
    assert original['capture_version'] == 3 and original['game_id'] == state.id
    assert any(row['owner'] == seat for row in original['inventory'].values())
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.sideboard_facts == original


@pytest.mark.parametrize('seat', [1, 2])
def test_native_factory_id_mismatch_still_rejects_without_erasing_capture(seat):
    state = MatchFactory.from_decks([support.entry('Mountain', 20)],
                                    [support.entry('Island', 20)], seed=support.SEED)
    original = deepcopy(state.sideboard_facts)
    state.id = f'forged-position-seat-{seat}'
    with pytest.raises(ValueError, match='Invalid private sideboard facts'):
        serialize_match_snapshot(state)
    assert state.sideboard_facts == original
