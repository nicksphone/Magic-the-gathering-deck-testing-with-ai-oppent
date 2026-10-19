"""Actual settlement of both wins; an artifact creates a competing Naturalize."""
import json
import os
from pathlib import Path

from ai.agent import AIAgent
from ai.pending_effects import unanswered_action_wins
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.loyalty_destruction_diagnostic_support import artifact_creature, source
from tests.test_ineffective_destruction import settled_state
from tests.test_pending_removal import add_card
from tests.test_self_removal import canonical_cards
from game_state.state import Zone


def test_actual_competing_cast_and_loyalty_both_settle_a_win_without_policy_repair(tmp_path):
    state, _, held = settled_state()
    add_card(state, 'Bastion of Remembrance', Zone.BATTLEFIELD)
    victim = artifact_creature(state)
    walker = source(state)
    # Preserve the historical artifact-fixture collision, not the final fixture.
    walker.oracle_text = '-3: Destroy target artifact or enchantment.'
    state.players[2].life = 1
    engine = RulesEngine()
    moves = engine.legal_moves(state, 1)
    ai = AIAgent(archetype='Midrange')
    before = serialize_match_snapshot(state)
    chosen = ai.choose_action(state, moves, 1).action
    loyalty_move = next(m for m in moves if m.get('card_id') == walker.id)
    loyalty = ai._materialize_action(state, {**loyalty_move, 'targets': {'target_card_id': victim.id}},
                                      1, allow_friendly_target=True)
    assert chosen['type'] == 'cast_spell' and chosen['card_id'] == held
    assert chosen['targets']['target_card_id'] == victim.id
    assert loyalty['type'] == 'activate_loyalty' and loyalty['card_id'] == walker.id
    assert unanswered_action_wins(state, 1, chosen) is True
    assert unanswered_action_wins(state, 1, loyalty) is True
    assert serialize_match_snapshot(state) == before
    settled = []
    for action in (chosen, loyalty):
        branch = checked_action(state, engine, 1, action)
        assert serialize_match_snapshot(state) == before
        paid = dict(branch.stack[-1].payload)
        for _ in range(12):
            if branch.winner is not None or not branch.stack:
                break
            branch = checked_action(branch, engine, branch.priority_player, {'type': 'pass_priority'})
        assert branch.winner == 1 and branch.players[2].life == 0
        settled.append({'action': action, 'winner': branch.winner,
                        'opponent_life': branch.players[2].life,
                        'source_zone': branch.cards[action['card_id']].zone.value,
                        'walker_loyalty': branch.cards[walker.id].loyalty,
                        'mana_spent': paid.get('mana_spent'),
                        'kind': paid.get('__announced_stack_kind')})
    trace = {'root_unchanged': True, 'victim_name': victim.name, 'victim_types': victim.types,
             'victim_owner_controller': [victim.owner, victim.controller],
             'winning_cast_before_loyalty_in_public_moves':
                 next(i for i, m in enumerate(moves) if m.get('card_id') == held)
                 < moves.index(loyalty_move), 'settled': settled}
    (tmp_path / 'competition-trace.json').write_text(json.dumps(trace, indent=2))
    if destination := os.environ.get('MTG_COMPETITION_TRACE'):
        Path(destination).write_text(json.dumps(trace, indent=2))
