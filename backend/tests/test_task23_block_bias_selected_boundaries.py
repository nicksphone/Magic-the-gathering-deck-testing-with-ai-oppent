"""Chosen-allocation tariff controls; inert malformed replies are not native actions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import assign_static_order_on_battlefield_entry
from rules_engine.continuous import printed_abilities_suppressed
from tests.test_task23_block_bias_offered_mana_baseline import position
from tests.vraska_full.test_full_vraska import add, Zone


def block_move(moves):
    return next(move for move in moves if move['type'] == 'block')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_existing_materializer_plan_is_priced_without_menu_or_rng_mutation(seat, monkeypatch):
    root, moves, _, safe, _ = position(seat, 12, 3)
    before, original_moves = serialize_match_snapshot(root), deepcopy(moves)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    original = actor._materialize_action_without_resources
    observed = []

    def observe(state, move, player_id, **kwargs):
        action = original(state, move, player_id, **kwargs)
        observed.append(deepcopy(action))
        return action

    monkeypatch.setattr(actor, '_materialize_action_without_resources', observe)
    assert actor._block_bias(root, block_move(moves), seat) == pytest.approx(3.8)
    assert len(observed) == 1 and safe in str(observed[0]['blocks'])
    assert serialize_match_snapshot(root) == before and moves == original_moves


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['string', 'list'])
def test_actual_provided_finite_allocation_excludes_unused_mana_tariffs(seat, style):
    root, moves, attacker, safe, _ = position(seat, 12, 3)
    move = {**block_move(moves), 'blocks': {attacker: safe if style == 'string' else [safe]}}
    before, original = serialize_match_snapshot(root), deepcopy(move)
    assert AIAgent(difficulty='strong', archetype='Midrange')._block_bias(root, move, seat) == pytest.approx(3.8)
    assert serialize_match_snapshot(root) == before and move == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['none', 'wrong_type', 'missing', 'not_dict', 'integer', 'tuple',
                                 'mixed', 'foreign', 'unoffered', 'duplicate', 'invalid_flag'])
def test_inert_invalid_allocation_keeps_whole_legacy_offered_tariff(seat, kind, monkeypatch):
    root, moves, attacker, safe, _ = position(seat, 12, 3)
    action = {'type': 'block', 'blocks': {attacker: [safe]}}
    if kind == 'none': action = None
    elif kind == 'wrong_type': action['type'] = 'pass_priority'
    elif kind == 'missing': action.pop('blocks')
    elif kind == 'not_dict': action['blocks'] = []
    elif kind == 'integer': action['blocks'][attacker] = 1
    elif kind == 'tuple': action['blocks'][attacker] = (safe,)
    elif kind == 'mixed': action['blocks'][attacker] = [safe, 1]
    elif kind == 'foreign': action['blocks'][attacker] = [attacker]
    elif kind == 'unoffered': action['blocks'][attacker] = [root.players[seat].library[0]]
    elif kind == 'duplicate': action['blocks'][attacker] = [safe, safe]
    else: action['_invalid_ai_choice'] = True
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    monkeypatch.setattr(actor, '_materialize_action_without_resources', lambda *args, **kwargs: action)
    before = serialize_match_snapshot(root)
    assert actor._block_bias(root, block_move(moves), seat) == pytest.approx(-6.7)
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_empty_provided_allocation_uses_existing_no_block_sentinel(seat):
    from rules_engine.engine import RulesEngine
    from tests.test_task23_block_material_baseline import position as material_position
    root, _, _, attacker, _, _ = material_position(seat, ('engine', 'vanilla'))
    root.cards[attacker].counters.clear()
    root.cards[attacker].counters['+1/+1'] = 1
    move = block_move(RulesEngine().legal_moves(root, seat))
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    before = serialize_match_snapshot(root)
    assert actor._materialize_action_without_resources(root, move, seat)['blocks'] == {}
    assert actor._block_bias(root, move, seat) == -0.8
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_inert_known_empty_return_does_not_reward_legacy_offered_profit(seat, monkeypatch):
    root, moves, _, _, _ = position(seat, 12, 3)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    monkeypatch.setattr(actor, '_materialize_action_without_resources',
                        lambda *args, **kwargs: {'type': 'block', 'blocks': {}})
    before = serialize_match_snapshot(root)
    assert actor._block_bias(root, block_move(moves), seat) == -0.8
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_chosen_mana_creature_costs_one_existing_tariff_not_all_offered(seat):
    root, moves, attacker, _, mana = position(seat, 12, 3)
    move = {**block_move(moves), 'blocks': {attacker: [mana[0]]}}
    before = serialize_match_snapshot(root)
    assert AIAgent(difficulty='strong', archetype='Midrange')._block_bias(root, move, seat) == pytest.approx(0.3)
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_full_humility_suppresses_chosen_printed_mana_retention(seat):
    root, moves, attacker, _, mana = position(seat, 12, 3)
    data = json.loads((Path(__file__).parent / 'fixtures/ability_suppression.json').read_bytes())
    raw = next(card for card in data if card['name'] == 'Humility')
    resident = add(root, raw | {key: raw.get(key) or '' for key in ('power', 'toughness', 'loyalty')},
                   3 - seat, Zone.BATTLEFIELD, old_board=True)
    assign_static_order_on_battlefield_entry(root, resident.id)
    assert all(printed_abilities_suppressed(root, cid) for cid in mana)
    move = {**block_move(moves), 'blocks': {attacker: [mana[0]]}}
    before = serialize_match_snapshot(root)
    assert AIAgent(difficulty='strong', archetype='Midrange')._block_bias(root, move, seat) == pytest.approx(3.6)
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_live_mana_reader_keeps_selected_legacy_raw_price(seat, monkeypatch):
    from rules_engine import mana as mana_rules
    root, moves, attacker, _, mana = position(seat, 12, 3)
    move = {**block_move(moves), 'blocks': {attacker: [mana[0]]}}

    def unknown(*args, **kwargs):
        raise ValueError('inert unavailable mana estimate')

    monkeypatch.setattr(mana_rules, 'repeatable_nonland_mana_outputs', unknown)
    before = serialize_match_snapshot(root)
    assert AIAgent(difficulty='strong', archetype='Midrange')._block_bias(root, move, seat) == pytest.approx(0.3)
    assert serialize_match_snapshot(root) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('violation', ['tapped', 'noncreature', 'decayed', 'flying', 'menace', 'capacity'])
def test_inert_provided_illegal_allocation_uses_complete_legacy_price(seat, violation, monkeypatch):
    """Stale/provided plans are protocol probes, not actual chooser outputs."""
    from ai.pending_effects import simulation_checked_action
    from rules_engine.action_validation import ActionRejected
    from rules_engine.keyword_effects import add_keyword_effect
    from tests.test_ai_terminal_draw_product import raw
    root, moves, attacker, safe, _ = position(seat, 12, 3)
    move = deepcopy(block_move(moves))
    groups = {attacker: [safe]}
    if violation == 'tapped':
        root.cards[safe].tapped = True
    elif violation == 'noncreature':
        # Explicit inert surface change; no claim of a paid type-changing effect.
        root.cards[safe].types = ['Artifact']
    elif violation == 'decayed':
        add_keyword_effect(root, safe, ['decayed'])
    elif violation in {'flying', 'menace'}:
        add_keyword_effect(root, attacker, [violation])
    else:
        # Trusted existing-board combat posture; not a fabricated spell/event.
        second = add(root, raw('grizzly-bears'), 3-seat, Zone.BATTLEFIELD, old_board=True)
        root.attackers.append(second.id)
        root.attack_targets[second.id] = 'player:' + str(seat)
        move['attackers'].append({'id': second.id, 'name': second.name})
        groups[second.id] = [safe]
    before = serialize_match_snapshot(root)
    actor = AIAgent(difficulty='strong', archetype='Midrange')
    with pytest.raises(ActionRejected):
        simulation_checked_action(root, actor.engine, seat, {'type': 'block', 'blocks': groups})
    assert serialize_match_snapshot(root) == before
    # Same-state exact legacy tariff witness: unavailable allocation, no score override.
    monkeypatch.setattr(actor, '_materialize_action_without_resources', lambda *a, **k: None)
    legacy = actor._block_bias(root, move, seat)
    monkeypatch.setattr(actor, '_materialize_action_without_resources',
                        lambda *a, **k: {'type': 'block', 'blocks': deepcopy(groups)})
    assert actor._block_bias(root, move, seat) == pytest.approx(legacy)
    assert serialize_match_snapshot(root) == before
