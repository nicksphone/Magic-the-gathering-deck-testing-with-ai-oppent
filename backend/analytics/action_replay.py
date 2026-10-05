"""Reconstruct seeded diagnostic actions without AI search or persistence."""
from collections import Counter
from copy import deepcopy
import hashlib
import json

from analytics.replay_tools import first_log_divergence, normalize_log_line
from game_state.state import MatchFactory, Step, pregame_actor
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine


class ReplayMismatch(ValueError):
    def __init__(self, decision, field, expected, actual):
        self.diagnostic = {'decision': decision, 'field': field, 'expected': expected, 'actual': actual}
        super().__init__(f'Recorded-action divergence at decision {decision}: {field}')


def reconstruct_game(deck_a: list[dict], deck_b: list[dict], game: dict) -> dict:
    """Validate roots, checked actions and complete logs; passes are not misplays."""
    if (not isinstance(game, dict) or not {'seed', 'starting_player', 'winner', 'turn', 'ticks', 'log_hash', 'log'} <= game.keys()
            or type(game.get('seed')) is not int or type(game.get('starting_player')) is not int
            or game['starting_player'] not in (1, 2)
            or type(game.get('turn')) is not int or game['turn'] < 1
            or type(game.get('ticks')) is not int or game['ticks'] < 0
            or not (game['winner'] is None or type(game['winner']) is int and game['winner'] in (1, 2))
            or not isinstance(game.get('log_hash'), str)
            or not isinstance(game.get('log'), list)
            or not all(isinstance(line, str) for line in game['log'])):
        raise ValueError('A seeded game, starting player and complete string log are required')
    state = MatchFactory.from_decks(deepcopy(deck_a), deepcopy(deck_b), seed=game['seed'])
    state.active_player = state.priority_player = game['starting_player']
    state.mechanic_choice_players = {1, 2}
    rules = RulesEngine()
    decisions = 0
    counts = {pid: Counter() for pid in (1, 2)}

    def compare(field, expected, actual):
        if expected != actual:
            raise ReplayMismatch(decisions, field, expected, actual)

    for line in game['log']:
        if not line.startswith('AI TRACE '):
            continue
        try:
            trace = json.loads(line[9:])
        except json.JSONDecodeError as error:
            raise ReplayMismatch(decisions, 'trace', 'JSON object', 'invalid JSON') from error
        if (not isinstance(trace, dict) or type(trace.get('pid')) is not int
                or trace['pid'] not in (1, 2) or not isinstance(trace.get('action'), dict)
                or not isinstance(trace['action'].get('type'), str)):
            raise ReplayMismatch(decisions, 'trace', 'actor and action object', 'invalid trace')
        pid = trace['pid']
        compare('actor', pregame_actor(state) if state.pregame_pending else state.priority_player, pid)
        for field, actual in [('turn', state.turn), ('step', str(state.step)),
                              ('active_player', state.active_player), ('priority_player', state.priority_player),
                              ('hand', [state.cards[cid].name for cid in state.players[pid].hand]),
                              ('battlefield', [state.cards[cid].name for cid in state.players[pid].battlefield])]:
            compare(field, trace.get(field), actual)
        legal = rules.legal_moves(state, pid)
        compare('legal_action_types', trace.get('legal_action_types'), sorted({str(move['type']) for move in legal}))
        action = deepcopy(trace['action'])
        counts[pid]['decisions'] += 1
        counts[pid][action.get('type', '<missing>')] += 1
        if (action.get('type') == 'pass_priority' and not state.pregame_pending and not state.stack
                and state.active_player == pid and state.step in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}):
            for kind, field in [('play_land', 'land_pass_opportunities'), ('cast_spell', 'cast_pass_opportunities')]:
                counts[pid][field] += int(any(move['type'] == kind for move in legal))
        state.log.append(line)
        try:
            rules.take_action(state, pid, action, reject_invalid=True)
        except (ActionRejected, KeyError, TypeError, ValueError) as error:
            raise ReplayMismatch(decisions, 'action', 'accepted recorded action', str(error)) from error
        decisions += 1
    actual_log = [normalize_log_line(line) for line in state.log]
    divergence = first_log_divergence(game['log'], actual_log)
    if divergence['index'] != -1:
        raise ReplayMismatch(decisions, 'log', game['log'][divergence['index']:divergence['index']+1], divergence)
    compare('log_hash', game.get('log_hash'), hashlib.sha256('\n'.join(actual_log).encode()).hexdigest())
    for field, actual in [('winner', state.winner), ('turn', state.turn), ('ticks', decisions)]:
        compare(field, game.get(field), actual)
    return {'matched': True, 'decisions': decisions, 'winner': state.winner, 'turn': state.turn,
            'by_seat': {str(pid): dict(counts[pid]) for pid in (1, 2)},
            'inference': 'Action/rules reconstruction only; available casts and passes are not quality verdicts'}
