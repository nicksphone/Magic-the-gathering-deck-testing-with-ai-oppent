"""Actual offered-action rollout audit; canonical paid states, no policy substitution."""
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import random
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from effects import registry
from rules_engine.engine import RulesEngine
from nadu_support import snapshot, conservation
from test_ai_granted_equip import prepare, digest


def observe_choice(state, seat):
    legal = RulesEngine().legal_moves(state, seat)
    before = snapshot(state)
    rng = random.getstate()
    agent = AIAgent(difficulty='master_plus', archetype='Ramp', opponent_archetype='Ramp')
    deltas, playouts, reveals = [], [], []
    scope = []
    delta = AIAgent._rollout_delta
    playout = AIAgent._rollout_playout
    handler = registry.EFFECT_HANDLERS['reveal_top_conditional']

    def observe_delta(self, projected, move, player):
        row = {'move': deepcopy(move), 'root_stack_keys': [i.effect_key for i in projected.stack],
               'caller': inspect.stack()[1].function}
        deltas.append(row)
        scope.append('rollout_delta')
        try:
            row['score'] = delta(self, projected, move, player)
            return row['score']
        finally:
            scope.pop()

    def observe_playout(self, projected, player, plies):
        before_library = {pid: len(p.library) for pid, p in projected.players.items()}
        before_hand = {pid: len(p.hand) for pid, p in projected.players.items()}
        scope.append('rollout_playout')
        try:
            score = playout(self, projected, player, plies)
            playouts.append({'plies': plies, 'score': score, 'library_before': before_library,
                            'library_after': {pid: len(p.library) for pid, p in projected.players.items()},
                            'hand_before': before_hand,
                            'hand_after': {pid: len(p.hand) for pid, p in projected.players.items()}})
            return score
        finally:
            scope.pop()

    def observe_reveal(projected, controller, payload):
        player = projected.players[controller]
        if not player.library:
            return handler(projected, controller, payload)
        card = projected.cards[player.library[-1]]
        row = {'scope': scope[:], 'opaque_top': is_unknown(card),
               'top_types': list(card.types), 'instruction': payload['instruction'],
               'controller': controller, 'library_before': len(player.library),
               'hand_before': len(player.hand),
               'callsites': [f.function for f in inspect.stack()[1:9]]}
        result = handler(projected, controller, payload)
        row.update({'library_after': len(player.library), 'hand_after': len(player.hand),
                    'resolved_destination': card.zone.value})
        reveals.append(row)
        return result

    with patch.object(AIAgent, '_rollout_delta', observe_delta), \
         patch.object(AIAgent, '_rollout_playout', observe_playout), \
         patch.dict(registry.EFFECT_HANDLERS, {'reveal_top_conditional': observe_reveal}):
        chosen = agent.choose_action(state, legal, seat)
    assert snapshot(state) == before and random.getstate() == rng
    return chosen.action, {'offered': legal, 'actual_selected': chosen.action,
                           'reasoning': chosen.reasoning, 'rollout_delta_calls': deltas,
                           'rollout_playout_calls': playouts, 'actual_reveal_handler_calls': reveals,
                           'root_private_rng_unchanged': True}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('boundary', ['offered_equip', 'announced_equip'])
def test_actual_choice_does_not_rollout_opaque_reveal_as_nonland(seat, boundary):
    p, _, _ = prepare(seat, 'one_slot')
    if boundary == 'announced_equip':
        p.act(seat, {'type': 'equip', 'card_id': p.ids['shuko'], 'target_card_id': p.ids['elf']})
        assert [i.effect_key for i in p.state.stack] == ['equip_attachment', 'reveal_top_conditional']
    actor = p.state.priority_player
    evidence = {'seat': seat, 'actor': actor, 'boundary': boundary,
                'canonical_paid_setup': True, 'setup_actions': p.actions,
                'input_gameplay_injection': False, 'hidden_swap_label': 'test-only public-equivalent counterfactual'}
    try:
        action, actual = observe_choice(p.state, actor)
        evidence['actual'] = actual
        alternative = deepcopy(p.state)
        view, _ = decision_view(p.state, actor, RulesEngine().legal_moves(p.state, actor))
        candidates = [cid for cid in alternative.players[seat].library if is_unknown(view.cards[cid])]
        first = candidates[-1]
        second = next(cid for cid in candidates if
                      ('Land' in alternative.cards[cid].types) != ('Land' in alternative.cards[first].types))
        library = alternative.players[seat].library
        a, b = library.index(first), library.index(second)
        library[a], library[b] = library[b], library[a]
        conservation(alternative)
        second_view, _ = decision_view(alternative, actor, RulesEngine().legal_moves(alternative, actor))
        public_a, public_b = snapshot(view), snapshot(second_view)
        for public in (public_a, public_b):
            for player in public['players'].values():
                player['library'] = sorted(player['library'])
        assert public_a == public_b
        second_action, counterfactual = observe_choice(alternative, actor)
        evidence['counterfactual'] = counterfactual
        assert action == second_action
        opaque_rollout = [row for result in (actual, counterfactual)
                          for row in result['actual_reveal_handler_calls']
                          if row['opaque_top']]
        evidence['actual_opaque_rollout_count'] = len(opaque_rollout)
        assert not opaque_rollout, 'Any AI simulation executed opaque conditional top as nonland'
    except BaseException as error:
        evidence['failure'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        (Path(os.environ['NADU_EVIDENCE'])/f'rollout-{seat}-{boundary}.json').write_text(
            json.dumps(evidence, indent=2, sort_keys=True)+'\n')
