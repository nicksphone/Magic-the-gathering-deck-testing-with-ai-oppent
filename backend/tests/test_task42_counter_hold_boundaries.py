"""Public urgency/knowledge boundaries; only altered-carrier cases are protocol fixtures."""
from copy import deepcopy
import ast
import inspect
import json
import textwrap

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, assign_static_order_on_battlefield_entry
from knowledge.service import estimate_for
from rules_engine.entry_counters import prospective_entry_ability_view
from rules_engine.engine import RulesEngine
from tests.test_ai_knowledge_profile_consumer import RAW
from tests.test_task23_checked_removal_baseline import add_profiled
from tests.test_task42_checked_interaction_hold import announced, base
from tests.vraska_full import test_full_vraska as rules


def choice(state, seat):
    before = serialize_match_snapshot(state)
    actor = AIAgent(difficulty='strong', archetype='Control')
    result = actor.choose_action(state, RulesEngine().legal_moves(state, seat), seat)
    assert serialize_match_snapshot(state) == before
    return result.action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['missing', 'malformed', 'stale', 'effective_type', 'suppressed', 'trigger_limits'])
def test_unknown_or_changed_advice_keeps_genuine_legacy_decision(seat, kind):
    if kind == 'trigger_limits':
        state, counter = base(seat)
        source = add_profiled(state, RAW['Dreadhorde Butcher'], 3 - seat, rules.Zone.HAND)
        state.players[3 - seat].mana_pool = {'B': 1, 'R': 1}
        state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
        state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
        source = source.id
        estimate = estimate_for(state.cards[source])
        assert estimate.tier == 1
        assert 'trigger_conditions_and_frequency_not_evaluated' in estimate.limits
    else:
        state, counter, source = announced(seat, 'Llanowar Elves')
        card = state.cards[source]
        if kind == 'missing':
            card.knowledge_snapshot = {}
        elif kind == 'malformed':
            card.knowledge_snapshot = {'unexpected': True}
        elif kind == 'stale':
            card.oracle_text += '\n'
        elif kind == 'effective_type':
            card.types.append('Artifact')  # Altered visible carrier, not a paid type-change certificate.
        else:
            cards = json.loads((rules.ROOT.parent / 'fixtures/ability_suppression.json').read_bytes())
            raw = next(row for row in cards if row['name'] == 'Humility')
            constructor = raw | {key: raw.get(key) or '' for key in ('power', 'toughness', 'loyalty')}
            added = rules.add(state, constructor, seat, rules.Zone.BATTLEFIELD, old_board=True)
            assert added.oracle_text == raw['oracle_text']
            assign_static_order_on_battlefield_entry(state, added.id)
            assert prospective_entry_ability_view(state, card, card.controller)['printed_suppressed']
        actor = AIAgent(difficulty='strong', archetype='Control')
        assert actor._printed_major_threat(state, card) is None
    before = serialize_match_snapshot(state)
    legacy = deepcopy(state)
    for card in legacy.cards.values():
        card.knowledge_snapshot = {}
    assert choice(state, seat) == choice(legacy, seat)
    if kind == 'trigger_limits':
        assert choice(state, seat)['card_id'] == counter
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_one_power_haste_at_one_life_is_not_held_as_safe(seat):
    state, counter = base(seat)
    for cid in list(state.players[seat].battlefield):
        state.players[seat].battlefield.remove(cid)
        state.players[seat].library.append(cid)
        state.cards[cid].move_to_zone(rules.Zone.LIBRARY)
    state.players[seat].life = 1
    source = add_profiled(state, RAW['Dreadhorde Butcher'], 3 - seat, rules.Zone.HAND)
    state.players[3 - seat].mana_pool = {'B': 1, 'R': 1}
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    assert estimate_for(state.cards[source.id]).tier == 1
    action = choice(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == counter
    saved = rules.settle(rules.act(state, seat, action))
    assert saved.cards[source.id].zone == rules.Zone.GRAVEYARD and saved.winner is None
    # Actual checked counterfactual shows the terminal public attack, not a score.
    danger = rules.settle(rules.act(state, seat, {'type': 'pass_priority'}))
    for _ in range(20):
        if danger.step == rules.Step.DECLARE_ATTACKERS:
            break
        danger = rules.act(danger, danger.priority_player, {'type': 'pass_priority'})
    assert danger.step == rules.Step.DECLARE_ATTACKERS and danger.turn == state.turn
    danger = rules.act(danger, 3 - seat, {'type': 'attack', 'attackers': [source.id]})
    for _ in range(30):
        if danger.winner is not None:
            break
        danger = rules.act(danger, danger.priority_player, {'type': 'pass_priority'})
    assert danger.winner == 3 - seat and danger.players[seat].life <= 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['public_pressure', 'late'])
def test_public_pressure_or_existing_late_horizon_preserves_counter(seat, kind):
    state, counter, source = announced(seat, 'Llanowar Elves')
    if kind == 'public_pressure':
        add_profiled(state, rules.BEAR, 3 - seat, rules.Zone.BATTLEFIELD)
    else:
        state.turn = 14
    action = choice(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == counter
    result = rules.settle(rules.act(state, seat, action))
    assert result.cards[source].zone == rules.Zone.GRAVEYARD
    assert result.cards[counter].zone == rules.Zone.GRAVEYARD and result.winner is None


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_tier_two_creature_keeps_existing_counter_decision(seat):
    state, counter = base(seat)
    source = add_profiled(state, RAW['Atraxa, Grand Unifier'], 3 - seat, rules.Zone.HAND)
    state.players[3 - seat].mana_pool = {'C': 3, 'G': 1, 'W': 1, 'U': 1, 'B': 1}
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    assert estimate_for(state.cards[source.id]).tier == 2
    action = choice(state, seat)
    assert action['type'] == 'cast_spell' and action['card_id'] == counter
    result = rules.settle(rules.act(state, seat, action))
    assert result.cards[source.id].zone == rules.Zone.GRAVEYARD and result.winner is None


def test_additive_hold_gate_is_explicitly_a_genuine_spell_only():
    tree = ast.parse(textwrap.dedent(inspect.getsource(AIAgent._choose_action)))
    gate = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                and any(isinstance(statement, ast.Assign) and isinstance(statement.value, ast.BoolOp)
                        and any(isinstance(target, ast.Name) and target.id == 'hold_printed_low'
                                for target in statement.targets) for statement in node.body))
    assert "stack_object_kind(state, item) == 'spell'" in ast.unparse(gate.test)


def test_additive_hold_gate_remains_inside_original_single_stack_window():
    tree = ast.parse(textwrap.dedent(inspect.getsource(AIAgent._choose_action)))
    single = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                  and ast.unparse(node.test) == 'len(stack_items) == 1')
    assert any(isinstance(node, ast.Name) and node.id == 'hold_printed_low'
               for statement in single.body for node in ast.walk(statement))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('archetype', ['Control', 'Counter-heavy'])
def test_actual_forest_paid_low_tier_is_held_with_real_island_counter_payment(seat, archetype):
    state, counter = base(seat)
    state.players[seat].mana_pool = {}
    islands = [add_profiled(state, RAW['Island'], seat, rules.Zone.BATTLEFIELD).id for _ in range(2)]
    forest = add_profiled(state, RAW['Forest'], 3 - seat, rules.Zone.BATTLEFIELD)
    source = add_profiled(state, RAW['Llanowar Elves'], 3 - seat, rules.Zone.HAND)
    state = rules.act(state, 3 - seat, {'type': 'tap_land_for_mana', 'card_id': forest.id, 'color': 'G'})
    assert state.cards[forest.id].tapped and state.players[3 - seat].mana_pool['G'] == 1
    state = rules.act(state, 3 - seat, {'type': 'cast_spell', 'card_id': source.id})
    assert state.stack[-1].payload['mana_spent'] == 1
    assert sum(state.players[3 - seat].mana_pool.values()) == 0
    state = rules.act(state, 3 - seat, {'type': 'pass_priority'})
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'cast_spell' and move['card_id'] == counter for move in moves)
    actor = AIAgent(difficulty='strong', archetype=archetype)
    decision = actor.choose_action(state, moves, seat)
    assert decision.action['type'] == 'pass_priority'
    held = rules.settle(rules.act(state, seat, decision.action))
    assert held.cards[source.id].zone == rules.Zone.BATTLEFIELD
    assert held.cards[counter].zone == rules.Zone.HAND
    assert all(not held.cards[cid].tapped for cid in islands)

    # Payability is demonstrated by a real checked alternative, not a menu flag.
    paid = rules.act(state, seat, {'type': 'cast_spell', 'card_id': counter,
                                 'targets': {'target_stack_id': state.stack[-1].id}})
    assert paid.stack[-1].payload['mana_spent'] == 2
    assert all(paid.cards[cid].tapped for cid in islands)
    assert sum(paid.players[seat].mana_pool.values()) == 0
    paid = rules.settle(paid)
    assert paid.cards[source.id].zone == rules.Zone.GRAVEYARD
    assert paid.cards[counter].zone == rules.Zone.GRAVEYARD
    assert serialize_match_snapshot(state) == before

    # Same public window: nonintrinsic/animated/unknown permanents stay legacy.
    for kind in ('creature_land', 'effectful_land', 'unknown_land'):
        guarded = deepcopy(state)
        if kind == 'creature_land':
            add_profiled(guarded, RAW['Dryad Arbor'], 3 - seat, rules.Zone.BATTLEFIELD)
        elif kind == 'effectful_land':
            cave = add_profiled(guarded, RAW['Cavern of Souls'], 3 - seat, rules.Zone.BATTLEFIELD)
            cave.chosen_creature_type = 'Elf'  # Declared prior choice; not the Forest payment source.
        else:
            # Same typed opaque carrier as decision_view, not canonical gameplay.
            unknown = CardInstance(forest.id, '', 3 - seat, 3 - seat, rules.Zone.BATTLEFIELD,
                                   mana_cost=None, summoning_sick=False)
            unknown.ai_unknown = True
            guarded.cards[forest.id] = unknown
        original = serialize_match_snapshot(guarded)
        guarded_actor = AIAgent(difficulty='strong', archetype=archetype)
        guarded_choice = guarded_actor.choose_action(guarded, RulesEngine().legal_moves(guarded, seat), seat)
        if kind == 'unknown_land':
            legacy = deepcopy(guarded)
            legacy.cards[source.id].knowledge_snapshot = {}
            legacy_choice = AIAgent(difficulty='strong', archetype=archetype).choose_action(
                legacy, RulesEngine().legal_moves(legacy, seat), seat)
            assert guarded_choice.action == legacy_choice.action
        else:
            assert guarded_choice.action['type'] == 'cast_spell' and guarded_choice.action['card_id'] == counter
        assert serialize_match_snapshot(guarded) == original
