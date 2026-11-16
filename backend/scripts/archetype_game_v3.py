"""Unchanged real engine/master decisions with compact, exactly replayed traces."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import time

from scripts.archetype_matrix_game import (
    TraceDivergence, actor, admit_decks, cell_decks, initial_state, outcome_for,
)
from scripts.archetype_trace_v3 import (
    CHAIN_KEYS, TRACE_SCHEMA, CpuAccounting, canonical, checkpoint_reasons, digest, record_digest,
)


@dataclass
class Captured:
    value: dict
    sha256: str
    cards_order: list[str]

    @property
    def cards_order_sha256(self):
        return digest(self.cards_order)


def capture(state, accounting):
    from game_state.serializers import serialize_match_snapshot
    with accounting.measure('snapshot'):
        data = canonical(serialize_match_snapshot(state))
        return Captured(json.loads(data), hashlib.sha256(data).hexdigest(), list(state.cards))


def ordered_snapshot(value, cards_order):
    """Read-only view by convention; outer/card maps are fresh and ordered."""
    if (type(value) is not dict or type(value.get('cards')) is not dict
            or type(cards_order) is not list
            or any(type(cid) is not str for cid in cards_order)
            or len(cards_order) != len(value['cards'])
            or len(set(cards_order)) != len(cards_order)
            or set(cards_order) != set(value['cards'])):
        raise ValueError('Exact unique ordered card IDs required')
    result = dict(value)
    result['cards'] = {cid:result['cards'][cid] for cid in cards_order}
    return result


def _plain(value):
    return json.loads(canonical(value))


def _policy(policy):
    if (type(policy) is not dict or type(policy.get('max_ticks')) is not int
            or not 0 <= policy['max_ticks'] <= 10000
            or type(policy.get('max_turns')) is not int or not 1 <= policy['max_turns'] <= 100):
        raise ValueError('Invalid bounded game policy')


def progress(value):
    return {key:value[key] for key in ('turn', 'step', 'active_player', 'priority_player', 'winner')}


def log_delta(before, after):
    old, new = before['log'], after['log']
    keep = 0
    while keep < min(len(old), len(new)) and old[keep] == new[keep]:
        keep += 1
    return {'keep': keep, 'append': new[keep:]}


def _ending(state, steps, policy):
    return (state.winner is not None or steps >= policy['max_ticks']
            or state.turn > policy['max_turns'])


def play_game(deck_a, deck_b, *, seed, game_id, policy, identity, emit,
              accounting=None, choose=None):
    _policy(policy)
    accounting = accounting or CpuAccounting()
    with accounting.measure('setup'):
        from ai.action_contract import complete_action
        from ai.agent import AIAgent
        from ai.deck_analysis import guess_archetype
        from rules_engine.action_validation import ActionRejected, checked_action
        from rules_engine.engine import RulesEngine
        state = initial_state(deck_a, deck_b, seed, game_id)
        rules = RulesEngine()
        agents = ({1:AIAgent(difficulty='master', archetype=guess_archetype(deck_a),
                            opponent_archetype=guess_archetype(deck_b)),
                   2:AIAgent(difficulty='master', archetype=guess_archetype(deck_b),
                            opponent_archetype=guess_archetype(deck_a))} if choose is None else {})
    first = capture(state, accounting)
    emit({'kind':'initial', 'schema':TRACE_SCHEMA, 'identity':_plain(identity),
          'deck_a':_plain(deck_a), 'deck_b':_plain(deck_b), 'seed':seed, 'game_id':game_id,
          'policy':deepcopy(policy), 'snapshot':first.value, 'snapshot_sha256':first.sha256,
          'cards_order':first.cards_order, 'cards_order_sha256':first.cards_order_sha256})
    steps, error = 0, None
    while not _ending(state, steps, policy):
        pid = actor(state)
        with accounting.measure('legal_moves'):
            legal = _plain(rules.legal_moves(state, pid))
        before = capture(state, accounting)
        started = time.monotonic()
        with accounting.measure('ai_decision'):
            decision = (choose(state, deepcopy(legal), pid) if choose is not None else
                        agents[pid].choose_action(state, deepcopy(legal), pid))
        decision_seconds = time.monotonic()-started
        after_decision = capture(state, accounting)
        if (after_decision.sha256 != before.sha256
                or after_decision.cards_order != before.cards_order):
            raise TraceDivergence(steps, ['AI_input_mutation'])
        action = _plain(complete_action(decision.action))
        started = time.monotonic()
        try:
            with accounting.measure('checked_transition'):
                candidate = checked_action(state, rules, pid, action)
        except ActionRejected as exc:
            candidate, error, exception = state, 'rejected_action', type(exc).__name__
        transition_seconds = time.monotonic()-started
        after = capture(candidate, accounting)
        row = {'kind':'rejected' if error else 'action', 'step':steps, 'actor':pid,
               'action':action, 'reasoning':str(decision.reasoning),
               'knowledge_usage':_plain(getattr(decision, 'knowledge_usage', None)),
               'legal_moves_sha256':digest(legal), 'before_sha256':before.sha256,
               'after_sha256':after.sha256, 'rng_sha256':digest(after.value['rng_state']),
               'before_cards_order_sha256':before.cards_order_sha256,
               'after_cards_order_sha256':after.cards_order_sha256,
               'progress':progress(after.value), 'log_delta':log_delta(before.value, after.value),
               'decision_seconds':decision_seconds, 'transition_seconds':transition_seconds}
        if error:
            row['exception_class'] = exception
        reasons = checkpoint_reasons(before.value, after.value, steps,
                                      final=bool(error) or _ending(candidate, steps+1, policy))
        if reasons:
            row.update(checkpoint_reasons=reasons,
                       checkpoint={'before':before.value, 'after':after.value,
                                   'before_cards_order':before.cards_order,
                                   'after_cards_order':after.cards_order})
        emit(row)
        if error:
            break
        state, steps = candidate, steps+1
    outcome = outcome_for(state, steps, policy, error)
    final = capture(state, accounting)
    emit({'kind':'final', 'outcome':outcome, 'snapshot':final.value, 'snapshot_sha256':final.sha256,
          'cards_order':final.cards_order, 'cards_order_sha256':final.cards_order_sha256})
    return outcome


def _authenticated(rows):
    previous, sequence, final = None, 0, False
    try:
        for row in rows:
            if (type(row) is not dict or not CHAIN_KEYS.issubset(row) or final
                    or type(row['sequence']) is not int or row['sequence'] != sequence
                    or row['previous_record_sha256'] != previous
                    or record_digest({k:v for k,v in row.items() if k != 'record_sha256'}) != row['record_sha256']):
                raise ValueError('Trace chain differs')
            sequence += 1
            previous, final = row['record_sha256'], row.get('kind') == 'final'
            yield row
        if not final:
            raise ValueError('No final record')
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise TraceDivergence(max(0, sequence-1), ['record_chain']) from exc


def _keys(row, keys, step):
    if set(row) != set(keys) | CHAIN_KEYS:
        raise TraceDivergence(step, ['record_fields'])


def _check(row, actual, step):
    fields = [key for key,value in actual.items() if digest(row.get(key)) != digest(value)]
    if fields:
        raise TraceDivergence(step, fields)


def replay_trace(records, *, boundary=None, accounting=None):
    from ai.action_contract import complete_action
    from game_state.serializers import deserialize_match_snapshot
    from rules_engine.action_validation import ActionRejected, checked_action
    from rules_engine.engine import RulesEngine
    accounting = accounting or CpuAccounting()
    records = iter(_authenticated(records))
    first = next(records, None)
    if first is None:
        raise TraceDivergence(0, ['initial'])
    _keys(first, ('kind','schema','identity','deck_a','deck_b','seed','game_id','policy',
                  'snapshot','snapshot_sha256','cards_order','cards_order_sha256'), 0)
    if first['kind'] != 'initial' or type(first['schema']) is not int or first['schema'] != TRACE_SCHEMA:
        raise TraceDivergence(0, ['initial'])
    _policy(first['policy'])
    state = initial_state(first['deck_a'], first['deck_b'], first['seed'], first['game_id'])
    initial = capture(state, accounting)
    _check(first, {'snapshot':initial.value,'snapshot_sha256':initial.sha256,
                   'cards_order':initial.cards_order,'cards_order_sha256':initial.cards_order_sha256}, 0)
    rules, steps, error, final = RulesEngine(), 0, None, None
    for row in records:
        if row.get('kind') == 'final':
            final = row
            if next(records, None) is not None:
                raise TraceDivergence(steps, ['after_final'])
            break
        if error or _ending(state, steps, first['policy']) or row.get('kind') not in ('action','rejected'):
            raise TraceDivergence(steps, ['record_kind'])
        required = {'kind','step','actor','action','reasoning','knowledge_usage',
                    'legal_moves_sha256','before_sha256','after_sha256','rng_sha256',
                    'before_cards_order_sha256','after_cards_order_sha256',
                    'progress','log_delta','decision_seconds','transition_seconds'}
        if row['kind'] == 'rejected':
            required.add('exception_class')
        # Checkpoint presence/content is decided from the genuine transition below.
        _keys(row, required | ({'checkpoint','checkpoint_reasons'} if 'checkpoint' in row else set()), steps)
        if any(type(row[key]) not in (int, float) or not 0 <= row[key] <= 1500
               for key in ('decision_seconds','transition_seconds')):
            raise TraceDivergence(steps, ['timing'])
        try:
            normalized_action = complete_action(row['action'])
        except (ActionRejected, TypeError, ValueError) as exc:
            raise TraceDivergence(steps, ['action_contract']) from exc
        if digest(normalized_action) != digest(row['action']):
            raise TraceDivergence(steps, ['action_contract'])
        pid = actor(state)
        with accounting.measure('legal_moves'):
            legal = _plain(rules.legal_moves(state, pid))
        before = capture(state, accounting)
        _check(row, {'step':steps,'actor':pid,'legal_moves_sha256':digest(legal),
                     'before_sha256':before.sha256,
                     'before_cards_order_sha256':before.cards_order_sha256}, steps)
        try:
            with accounting.measure('checked_transition'):
                candidate = checked_action(state, rules, pid, row['action'])
        except (ActionRejected, KeyError, TypeError, ValueError) as exc:
            if not isinstance(exc, ActionRejected) or row['kind'] != 'rejected' or row.get('exception_class') != type(exc).__name__:
                raise TraceDivergence(steps, ['action']) from exc
            candidate, error = state, 'rejected_action'
        else:
            if row['kind'] != 'action':
                raise TraceDivergence(steps, ['action'])
        after = capture(candidate, accounting)
        _check(row, {'after_sha256':after.sha256,'rng_sha256':digest(after.value['rng_state']),
                     'after_cards_order_sha256':after.cards_order_sha256,
                     'progress':progress(after.value),'log_delta':log_delta(before.value,after.value)}, steps)
        reasons = checkpoint_reasons(before.value, after.value, steps,
                                     final=bool(error) or _ending(candidate, steps+1, first['policy']))
        if bool(reasons) != ('checkpoint' in row):
            raise TraceDivergence(steps, ['checkpoint'])
        if reasons:
            _check(row, {'checkpoint_reasons':reasons,
                         'checkpoint':{'before':before.value,'after':after.value,
                                       'before_cards_order':before.cards_order,
                                       'after_cards_order':after.cards_order}}, steps)
        if error:
            continue
        with accounting.measure('serde_restart'):
            restarted = deserialize_match_snapshot(deepcopy(ordered_snapshot(after.value, after.cards_order)))
        restored = capture(restarted, accounting)
        if restored.sha256 != after.sha256 or restored.cards_order != after.cards_order:
            raise TraceDivergence(steps, ['snapshot_roundtrip'])
        if boundary is not None:
            boundary(first, {**row,'before':ordered_snapshot(before.value, before.cards_order),
                             'after':ordered_snapshot(after.value, after.cards_order),'legal_moves':legal})
        state, steps = restarted, steps+1
    if final is None:
        raise TraceDivergence(steps, ['missing_final'])
    _keys(final, ('kind','outcome','snapshot','snapshot_sha256','cards_order','cards_order_sha256'), steps)
    if error is None and not _ending(state, steps, first['policy']):
        raise TraceDivergence(steps, ['early_final'])
    last = capture(state, accounting)
    _check(final, {'outcome':outcome_for(state,steps,first['policy'],error),
                   'snapshot':last.value,'snapshot_sha256':last.sha256,
                   'cards_order':last.cards_order,'cards_order_sha256':last.cards_order_sha256}, steps)
    return {'matched':True,'actions':steps,'status':final['outcome']['status'],
            'restart_roundtrips':steps,'outcome':deepcopy(final['outcome'])}
