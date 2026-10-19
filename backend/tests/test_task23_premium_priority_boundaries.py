"""Rating-seam protocol negatives; real engine menus, no invented game events."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.keyword_effects import add_keyword_effect
from tests.test_task23_numeric_priority_baseline import position
from tests.vraska_full import test_full_vraska as rules


def menu(seat):
    state, removal, value, engine, opponent = position(seat, 'Llanowar Elves')
    state.players[3 - seat].battlefield.remove(engine)
    state.players[3 - seat].library.append(engine)
    state.cards[engine].move_to_zone(rules.Zone.LIBRARY)
    own = rules.add(state, rules.BEAR, seat, rules.Zone.BATTLEFIELD, old_board=True)
    legal = RulesEngine().legal_moves(state, seat)
    move = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == removal)
    return state, move, own.id, opponent, engine


@pytest.mark.parametrize('seat', [1, 2])
def test_rating_cannot_enter_materializer_or_friendly_choice_policy(seat, monkeypatch):
    from ai import pending_effects
    state, move, own, opponent, _ = menu(seat)
    actor = AIAgent(archetype='Midrange')
    before = serialize_match_snapshot(state)
    original_move = deepcopy(move)
    original = pending_effects.unproductive_destroy_targets
    observed = []

    def unavailable(*args, **kwargs):
        pytest.fail('Advisory ranking entered an action/choice projection')

    def watched(*args, **kwargs):
        assert kwargs['candidates'] == {opponent}
        assert kwargs['own_choice_action'] is None
        observed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(actor, '_materialize_action', unavailable)
    monkeypatch.setattr(actor, 'choose_action', unavailable)
    monkeypatch.setattr(pending_effects, 'friendly_destruction_profit', unavailable)
    monkeypatch.setattr(pending_effects, 'unproductive_destroy_targets', watched)
    assert actor._premium_removal_priority(state, move, seat) is False
    assert observed and own in {t['id'] for t in move['target_hints']['creature_targets']}
    assert move == original_move and serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['friendly', 'foreign', 'nonbf', 'missing_cost', 'unknown_cost',
                                'complex_cost', 'mode', 'conditional', 'compound', 'unknown_tail'])
def test_unsupported_or_explicit_nonopponent_context_is_entire_legacy(seat, kind, monkeypatch):
    from rules_engine import oracle_effects
    state, move, own, opponent, nonbf = menu(seat)
    move = deepcopy(move)
    if kind == 'friendly': move['targets'] = {'target_card_id': own}
    elif kind == 'foreign': move['targets'] = {'target_card_id': 'unoffered-reference'}
    elif kind == 'nonbf':
        move['target_hints']['creature_targets'] = [{'id': nonbf, 'name': state.cards[nonbf].name}]
        move['targets'] = {'target_card_id': nonbf}
    elif kind == 'missing_cost': move.pop('cost_options')
    elif kind == 'unknown_cost': move['cost_options'][0]['unknown_payment'] = True
    elif kind == 'complex_cost': move['cost_options'][0]['sacrifice_creatures'] = 1
    elif kind == 'mode': move['targets'] = {'mode_text': 'Destroy target creature.'}
    elif kind in {'conditional', 'compound'}:
        # Inert effect-classification boundary, NOT a real conditional spell.
        key = 'conditional_instruction' if kind == 'conditional' else 'effect_sequence'
        monkeypatch.setattr(oracle_effects, 'infer_effect_from_oracle', lambda *a, **k: (key, {}))
    else:
        # Deliberately stale/unsupported source input, NOT canonical RAW intake.
        state.cards[move['card_id']].oracle_text += '\nUnknown follow-up.'
    before = serialize_match_snapshot(state)
    actor = AIAgent(archetype='Midrange')
    assert actor._premium_removal_priority(state, move, seat) is None
    assert actor._cast_bias(state, move, seat) == 2.0
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_explicit_productive_opponent_selection_is_retained(seat):
    state, move, _, opponent, _ = menu(seat)
    # Add the genuine canonical high-tier competing source, not a forced move.
    from tests.test_task23_checked_removal_baseline import add_profiled
    from tests.test_ai_knowledge_profile_consumer import RAW
    add_profiled(state, RAW['Zulaport Cutthroat'], 3 - seat, rules.Zone.BATTLEFIELD)
    move = next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'cast_spell' and m['card_id'] == move['card_id'])
    move = {**move, 'targets': {'target_card_id': opponent}}
    assert AIAgent(archetype='Midrange')._premium_removal_priority(state, move, seat) is False


@pytest.mark.parametrize('seat', [1, 2])
def test_indestructible_productivity_and_source_sensitive_legality_stay_engine_owned(seat):
    from rules_engine.action_validation import ActionRejected
    state, move, _, opponent, _ = menu(seat)
    add_keyword_effect(state, opponent, ['indestructible'])
    assert AIAgent(archetype='Midrange')._premium_removal_priority(state, move, seat) is None
    add_keyword_effect(state, opponent, ['hexproof'])
    legal = RulesEngine().legal_moves(state, seat)
    current = next(m for m in legal if m['type'] == 'cast_spell' and m['card_id'] == move['card_id'])
    assert opponent not in {t['id'] for t in current['target_hints']['creature_targets']}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        rules.act(state, seat, {'type': 'cast_spell', 'card_id': move['card_id'],
                               'targets': {'target_card_id': opponent}})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_covered_mask_does_not_become_empty_permission(seat, monkeypatch):
    from ai import pending_effects
    state, move, _, _, _ = menu(seat)
    monkeypatch.setattr(pending_effects, 'covered_removal_targets', lambda *args: None)
    assert AIAgent(archetype='Midrange')._premium_removal_priority(state, move, seat) is None
