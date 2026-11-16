"""Stream complete private engine transitions and replay them without AI rerolls."""
from copy import deepcopy
import json
import time

from scripts.archetype_matrix_plan import digest


class TraceDivergence(ValueError):
    def __init__(self, step, fields):
        self.step, self.fields = step, fields
        super().__init__(f'Replay diverged at step {step}: {", ".join(fields)}')


def plain(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def snapshot(state):
    from game_state.serializers import serialize_match_snapshot
    return plain(serialize_match_snapshot(state))


def initial_state(deck_a, deck_b, seed, game_id):
    from game_state.state import MatchFactory
    state = MatchFactory.from_decks(deepcopy(deck_a), deepcopy(deck_b), seed=seed, game_id=game_id)
    state.mechanic_choice_players = {1, 2}
    return state


def actor(state):
    from game_state.state import pregame_actor
    return pregame_actor(state) if state.pregame_pending else state.priority_player


def outcome_for(state, steps, policy, error=None):
    status, termination, winner = 'tick_limit', 'tick_limit', None
    if error is not None:
        status, termination = 'error', error
    elif state.winner is not None:
        if state.winner in (1, 2):
            winner = state.winner
            loser = 3 - winner
            status = 'resolved'
            termination = ('deck_out' if loser in state.failed_draw_players else
                           'life' if state.players[loser].life <= 0 else 'other_rules')
        else:
            status, termination = 'draw', 'engine_draw'
    elif state.turn > policy['max_turns']:
        status, termination = 'turn_limit', 'turn_limit'
    return {'status': status, 'winner': winner, 'termination': termination,
            'accepted_actions': steps, 'turn': state.turn}


def play_game(deck_a, deck_b, *, seed, game_id, policy, emit, choose=None):
    from ai.action_contract import complete_action
    from ai.agent import AIAgent
    from ai.deck_analysis import guess_archetype
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine
    state = initial_state(deck_a, deck_b, seed, game_id)
    rules = RulesEngine()
    agents = ({1: AIAgent(difficulty='master', archetype=guess_archetype(deck_a),
                         opponent_archetype=guess_archetype(deck_b)),
               2: AIAgent(difficulty='master', archetype=guess_archetype(deck_b),
                         opponent_archetype=guess_archetype(deck_a))} if choose is None else {})
    emit({'kind': 'initial', 'schema': 1, 'deck_a': plain(deck_a), 'deck_b': plain(deck_b),
          'seed': seed, 'game_id': game_id, 'policy': deepcopy(policy), 'snapshot': snapshot(state)})
    steps, error = 0, None
    while state.winner is None and steps < policy['max_ticks'] and state.turn <= policy['max_turns']:
        pid = actor(state)
        legal = plain(rules.legal_moves(state, pid))
        before = snapshot(state)
        started = time.monotonic()
        decision = (choose(state, deepcopy(legal), pid) if choose is not None else
                    agents[pid].choose_action(state, deepcopy(legal), pid))
        decision_seconds = time.monotonic()-started
        if digest(snapshot(state)) != digest(before):
            raise TraceDivergence(steps, ['AI_input_mutation'])
        action = plain(complete_action(decision.action))
        row = {'step': steps, 'actor': pid, 'legal_moves': legal, 'action': action,
               'reasoning': str(decision.reasoning),
               'knowledge_usage': plain(getattr(decision, 'knowledge_usage', None)), 'before': before}
        transition_started = time.monotonic()
        try:
            candidate = checked_action(state, rules, pid, action)
        except ActionRejected as exc:
            emit({'kind': 'rejected', **row, 'exception_class': type(exc).__name__})
            error = 'rejected_action'
            break
        transition_seconds = time.monotonic()-transition_started
        emit({'kind': 'action', **row, 'after': snapshot(candidate),
              'decision_seconds': decision_seconds, 'transition_seconds': transition_seconds})
        state, steps = candidate, steps + 1
    outcome = outcome_for(state, steps, policy, error)
    emit({'kind': 'final', 'outcome': outcome, 'snapshot': snapshot(state)})
    return outcome


def replay_trace(records, *, boundary=None):
    """Full actor/legal/state/RNG replay; boundary observes selected real actions."""
    from game_state.serializers import deserialize_match_snapshot
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine
    records = iter(records)
    first = next(records, None)
    if not isinstance(first, dict) or first.get('kind') != 'initial':
        raise TraceDivergence(0, ['initial'])
    state = initial_state(first['deck_a'], first['deck_b'], first['seed'], first['game_id'])
    if digest(snapshot(state)) != digest(first['snapshot']):
        raise TraceDivergence(0, ['initial_snapshot'])
    rules, steps, error, final = RulesEngine(), 0, None, None
    for row in records:
        if row.get('kind') == 'final':
            final = row
            if next(records, None) is not None:
                raise TraceDivergence(steps, ['after_final'])
            break
        if error is not None or row.get('kind') not in ('action', 'rejected'):
            raise TraceDivergence(steps, ['record_kind'])
        pid = actor(state)
        legal = plain(rules.legal_moves(state, pid))
        fields = [key for key, actual in (('step', steps), ('actor', pid),
                  ('legal_moves', legal), ('before', snapshot(state)))
                  if digest(row.get(key)) != digest(actual)]
        if fields:
            raise TraceDivergence(steps, fields)
        try:
            candidate = checked_action(state, rules, pid, row['action'])
        except (ActionRejected, KeyError, TypeError, ValueError) as exc:
            if (not isinstance(exc, ActionRejected) or row['kind'] != 'rejected'
                    or type(exc).__name__ != row.get('exception_class')):
                raise TraceDivergence(steps, ['action']) from exc
            error = 'rejected_action'
            continue
        if row['kind'] != 'action' or digest(snapshot(candidate)) != digest(row.get('after')):
            raise TraceDivergence(steps, ['after'])
        restarted = deserialize_match_snapshot(deepcopy(row['after']))
        if digest(snapshot(restarted)) != digest(row['after']):
            raise TraceDivergence(steps, ['snapshot_roundtrip'])
        if boundary is not None:
            boundary(first, row)
        state, steps = restarted, steps + 1
    if final is None:
        raise TraceDivergence(steps, ['missing_final'])
    if (error is None and state.winner is None
            and state.turn <= first['policy']['max_turns']
            and steps < first['policy']['max_ticks']):
        raise TraceDivergence(steps, ['early_final'])
    expected = outcome_for(state, steps, first['policy'], error)
    fields = [key for key, actual in (('outcome', expected), ('snapshot', snapshot(state)))
              if digest(final.get(key)) != digest(actual)]
    if fields:
        raise TraceDivergence(steps, fields)
    return {'matched': True, 'actions': steps, 'status': expected['status'],
            'restart_roundtrips': steps}


def admit_decks(matrix):
    """Canonical shipped seed rows only, including sideboard admission (not play)."""
    from card_data.hydration import ready_for_match
    from card_data.seed_cards import seed_card_payload
    from rules_engine.coverage import deck_pair_coverage
    admitted = {}
    for name, text in matrix['decks'].items():
        main, all_rows, sideboard = [], [], False
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(('#', ';', '//')):
                continue
            if line.casefold().rstrip(':') in ('sideboard', 'sb'):
                sideboard = True
                continue
            if line.casefold().rstrip(':') in ('mainboard', 'maindeck', 'deck'):
                sideboard = False
                continue
            count, card = line.split(maxsplit=1)
            metadata = seed_card_payload(card)
            if not metadata or not ready_for_match(metadata):
                raise ValueError('Deck lacks canonical ready seed data')
            row = {**deepcopy(metadata), 'card_name': card, 'quantity': int(count)}
            all_rows.append(row)
            if not sideboard:
                main.append(row)
        if sum(row['quantity'] for row in main) < 60:
            raise ValueError('Canonical mainboard is too small')
        if deck_pair_coverage(all_rows, [])['known_unsupported_cards']:
            raise ValueError('Deck failed the unchanged known-gap screen')
        admitted[name] = main
    return admitted


def cell_decks(admitted, cell):
    rows = [admitted[cell['deck_a']], admitted[cell['deck_b']]]
    if type(cell['deck_a_seat']) is not int or cell['deck_a_seat'] not in (1, 2):
        raise ValueError('Physical seat must be 1 or 2')
    return deepcopy(rows if cell['deck_a_seat'] == 1 else rows[::-1])
