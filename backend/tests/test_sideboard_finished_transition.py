"""Real checked terminal kernel/transition; trusted phase/pools/draws, no SQL/BO3 claim."""
from collections import Counter
from copy import deepcopy
from importlib.util import find_spec
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai import sideboard_facts as facts
from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory, Step, Zone, draw_card
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from knowledge.profiles import derive_profile, merge_profile_payload
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
import main

RAW = {row['name']: row for row in map(json.loads,
    (Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines())}


class MetadataRows:
    """Offline canonical row descriptor, NOT a SQL repository or ingestion proof."""
    def __init__(self):
        self.rows = {name.casefold(): SimpleNamespace(name=name, scryfall_id=raw['id'],
            oracle_source='scryfall', profiles_json=json.dumps(merge_profile_payload(
                {'card_data': raw, 'rulings_verified': False}, derive_profile(raw))))
            for name, raw in RAW.items()}

    def get_cached_cards_by_names(self, names):
        return {}

    def get_card_knowledge_by_names(self, names):
        return {name.casefold(): self.rows[name.casefold()] for name in names
                if name.casefold() in self.rows}


@pytest.fixture(scope='module')
def metadata():
    return MetadataRows()


def api(name):
    assert hasattr(facts, name), 'missing accepted/completed fact producer: ' + name
    return getattr(facts, name)


def act(game, pid, action):
    before = serialize_match_snapshot(game)
    result = checked_action(game, RulesEngine(), pid, action)
    assert serialize_match_snapshot(game) == before
    api('record_accepted_action')(game, result, pid, action)
    return result


def settle(game):
    for _ in range(40):
        if not game.stack or game.winner is not None:
            return game
        game = act(game, game.priority_player, {'type': 'pass_priority'})
    pytest.fail('Native stack did not settle')


def episode(pid, size, metadata, *, finish=True):
    own = hydrate_deck_cards(metadata, [
        {'card_name': 'Plains', 'quantity': (size-8)//2},
        {'card_name': 'Island', 'quantity': (size-8)//2},
        {'card_name': 'Sheoldred, the Apocalypse', 'quantity': 4},
        {'card_name': 'Lightning Bolt', 'quantity': 4}])
    other = hydrate_deck_cards(metadata, [
        {'card_name': 'Forest', 'quantity': 52},
        {'card_name': 'Llanowar Elves', 'quantity': 4},
        {'card_name': 'Elvish Mystic', 'quantity': 4}])
    side = hydrate_deck_cards(metadata, [{'card_name': 'Supreme Verdict', 'quantity': 4}])
    decks = {pid: own, 3-pid: other}
    game = MatchFactory.from_decks(decks[1], decks[2], seed=13)
    game.pregame_pending = False
    game.step = Step.PRECOMBAT_MAIN
    game.active_player = game.priority_player = 3-pid
    # Explicit trusted low-life/resource starting pose; winner is never injected.
    game.players[3-pid].life = 3
    game.players[3-pid].mana_pool = {'G': 20}
    game.players[pid].mana_pool = {'R': 1}
    for owner in (1, 2):
        for _ in range(len(game.players[owner].library)):
            draw_card(game, owner)
    for _ in range(6):
        menu = RulesEngine().legal_moves(game, 3-pid)
        move = next(move for move in menu if move['type'] == 'cast_spell'
                    and 'Creature' in game.cards[move['card_id']].types)
        game = act(game, 3-pid, {'type': 'cast_spell', 'card_id': move['card_id']})
        assert game.stack[-1].payload['mana_spent'] == 1
        game = settle(game)
    assert len(game.players[3-pid].battlefield) == 6
    if finish:
        # Real priority response with actual paid lethal, not fabricated events.
        bolt = next(cid for cid in game.players[pid].hand if game.cards[cid].name == 'Lightning Bolt')
        game = act(game, 3-pid, {'type': 'pass_priority'})
        game = act(game, pid, {'type': 'cast_spell', 'card_id': bolt,
                              'targets': {'target_player': 3-pid}})
        assert game.stack[-1].payload['mana_spent'] == 1
        game = settle(game)
        assert game.winner == pid and game.players[3-pid].life == 0
    match = main.MatchController(state=game, rules=RulesEngine(),
        controllers={1: 'ai', 2: 'ai'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='ai_vs_ai', deck_ids=(None, None), mainboards=decks,
        sideboards={pid: side, 3-pid: []}, game_number=1,
        current_game_recorded=False, match_complete=False, best_of=3, root_seed=13)
    return match


@pytest.mark.parametrize('pid', [1, 2])
def test_real_terminal_seal_used_entry_and_physical_uncast_summary(pid, metadata):
    match = episode(pid, 60, metadata)
    assert match.state.sideboard_facts['complete'] is False
    main._post_step_finalize(match, None)
    assert match.state.sideboard_facts['complete'] is True
    summary = api('summary_for')(match.state, pid)
    assert summary['qualified'] is True
    assert summary['observed_creature_count'] == 6
    assert summary['held_counts']['Sheoldred, the Apocalypse'] == 4
    assert 'Lightning Bolt' in summary['protected_stock']
    assert 'Lightning Bolt' not in summary['held_counts']
    assert not {'hand', 'library', 'pending_mechanic_choice'} & summary.keys()


@pytest.mark.parametrize('pid', [1, 2])
@pytest.mark.parametrize('size', [60, 64])
def test_actual_transition_selects_knowledge_max3_and_retains_original_size(pid, size, metadata):
    match = episode(pid, size, metadata)
    main._post_step_finalize(match, None)
    assert find_spec('ai.sideboard_policy'), 'missing consumed knowledge planner'
    from ai import sideboard_policy as policy
    original = Counter({row['card_name']: row['quantity'] for row in match.mainboards[pid]})
    original.update({row['card_name']: row['quantity'] for row in match.sideboards[pid]})
    with patch.object(policy, 'plan_swaps', wraps=policy.plan_swaps) as selected, \
            patch.object(main, 'plan_sideboard', side_effect=AssertionError('valid knowledge fell back')):
        main._start_next_game_state(match, repo=metadata)
    assert selected.call_count == 1
    assert match.game_number == 2 and match.state.winner is None
    current = Counter({row['card_name']: row['quantity'] for row in match.mainboards[pid]})
    assert sum(current.values()) == size
    assert current['Supreme Verdict'] == 3 and current['Sheoldred, the Apocalypse'] == 1
    assert current['Lightning Bolt'] == 4  # Used/lethal entry protected in its entirety.
    assert all(qty <= 4 for name, qty in current.items() if name not in {'Plains', 'Island'})
    assert current + Counter({row['card_name']: row['quantity'] for row in match.sideboards[pid]}) == original
    assert not match.state.sideboard_facts['complete']
    serialize_match_snapshot(match.state)  # Reused match ID must also bind new-game facts.


@pytest.mark.parametrize('pid', [1, 2])
def test_real_finished_private_roundtrip_can_still_select_route_without_public_facts(pid, metadata):
    match = episode(pid, 60, metadata)
    main._post_step_finalize(match, None)
    raw = serialize_match_snapshot(match.state)
    match.state = deserialize_match_snapshot(deepcopy(raw))
    assert api('summary_for')(match.state, pid)['qualified'] is True
    public = main._serialize_match_controller(match)
    assert 'sideboard_facts' not in public
    main._start_next_game_state(match, repo=metadata)
    assert any(row['card_name'] == 'Supreme Verdict' for row in match.mainboards[pid])


@pytest.mark.parametrize('pid', [1, 2])
def test_live_unfinished_and_old_unknown_history_cannot_authorize_cuts(pid, metadata):
    match = episode(pid, 60, metadata, finish=False)
    assert api('seal_game')(match.state) is False
    assert api('summary_for')(match.state, pid)['qualified'] is False
    before = deepcopy((match.mainboards, match.sideboards))
    main._ai_sideboard_for_next_game(match, metadata)
    assert (match.mainboards, match.sideboards) == before
    raw = serialize_match_snapshot(match.state)
    del raw['sideboard_facts']
    match.state = deserialize_match_snapshot(raw)
    assert api('summary_for')(match.state, pid)['qualified'] is False
    main._ai_sideboard_for_next_game(match, metadata)
    assert (match.mainboards, match.sideboards) == before


@pytest.mark.parametrize('pid', [1, 2])
def test_valid_empty_and_explicit_auto_off_do_not_use_legacy(pid, metadata):
    match = episode(pid, 60, metadata)
    main._post_step_finalize(match, None)
    assert find_spec('ai.sideboard_policy'), 'missing consumed knowledge planner'
    from ai import sideboard_policy as policy
    before = deepcopy((match.mainboards, match.sideboards))
    with patch.object(policy, 'plan_swaps', return_value=[]), \
            patch.object(main, 'plan_sideboard', side_effect=AssertionError('empty fell back')):
        main._ai_sideboard_for_next_game(match, metadata)
    assert (match.mainboards, match.sideboards) == before
    assert hasattr(match, 'auto_sideboard'), 'missing actual transition flag'
    assert match.auto_sideboard is True
    match.auto_sideboard = False
    with patch.object(policy, 'plan_swaps', side_effect=AssertionError('disabled still planned')):
        main._ai_sideboard_for_next_game(match, metadata)
    assert (match.mainboards, match.sideboards) == before


@pytest.mark.parametrize('pid', [1, 2])
def test_both_hydrations_are_staged_before_either_board_assignment(pid, metadata):
    match = episode(pid, 60, metadata)
    main._post_step_finalize(match, None)
    before = deepcopy((match.mainboards, match.sideboards))
    calls = []
    def hydrate(repo, deck):
        calls.append(deck)
        if len(calls) == 2:
            raise ValueError('declared test failure on side hydration')
        return hydrate_deck_cards(repo, deck)
    with patch('card_data.hydration.hydrate_deck_cards', side_effect=hydrate):
        with pytest.raises(ValueError):
            main._ai_sideboard_for_next_game(match, metadata)
    assert len(calls) == 2
    assert (match.mainboards, match.sideboards) == before
