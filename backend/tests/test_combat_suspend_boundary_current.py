"""Actual inert/interactive public boundaries and bounded known-gap diagnostics."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.graveyard_inventory import public_graveyard_inventory
from rules_engine.targeting import stack_object_kind
from tests.test_empty_hand_attack_witness import ROWS, position
from tests.test_linked_damage_targets import raw_card

LINKED_GAPS = ['controller-linked damage targets', 'conditional land-entry damage']


@pytest.mark.parametrize('seat', [1, 2])
def test_inert_full_canonical_graveyard_bolt_preserves_root_and_matches_checked_damage(seat, tmp_path):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    bolt = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    engine, agent = RulesEngine(), AIAgent(difficulty='master')
    action = {'type': 'attack', 'attackers': [source]}
    announced = checked_action(state, engine, seat, action)
    public, _ = decision_view(announced, seat, [])
    inventory = public_graveyard_inventory(public, seat)
    assert inventory['status'] == 'inert'
    offered = checked_action(announced, engine, seat, {'type': 'pass_priority'})
    moves = engine.legal_moves(offered, 3-seat)
    assert not any(m.get('card_id') == bolt.id and m['type'] == 'cast_spell' for m in moves)
    leaf = agent._complete_strategic_combat_leaf(announced, seat)
    assert leaf is not None
    actual = announced
    for _ in range(20):
        if actual.winner is not None or actual.step == Step.END_COMBAT:
            break
        actual = checked_action(actual, engine, actual.priority_player, {'type': 'pass_priority'})
    assert actual.step == leaf.step == Step.END_COMBAT
    assert leaf.id == actual.id == state.id
    assert leaf.players[3-seat].life == actual.players[3-seat].life == 16
    assert leaf.winner == actual.winner is None and leaf.step == actual.step
    assert actual.cards[bolt.id].zone == leaf.cards[bolt.id].zone == Zone.GRAVEYARD
    prefix = agent._strategic_position_score(announced, seat)
    assert agent._strategic_state_score(announced, seat, 0, prefix + 7) == pytest.approx(
        agent._strategic_position_score(leaf, seat) + 7)
    assert serialize_match_snapshot(state) == before
    (tmp_path / 'inert-actual-trace.json').write_text(json.dumps({
        'root_id': state.id, 'seat': seat, 'canonical_graveyard_name': bolt.name,
        'inventory': inventory, 'offered_actual_responses': moves,
        'announced': action, 'prefix_score': prefix,
        'leaf_score': agent._strategic_position_score(leaf, seat),
        'actual_life': actual.players[3-seat].life, 'root_unchanged': True}, indent=2))


@pytest.mark.parametrize('seat', [1, 2])
def test_full_canonical_paid_graveyard_flashback_response_is_not_passed_away(seat, tmp_path):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    deluge = raw_card(state, ROWS['Memory Deluge'], 3-seat, Zone.GRAVEYARD)
    # Explicit canonical primitive funding; retain all original nine Mountains.
    raw_card(state, ROWS['Island'], 3-seat, Zone.BATTLEFIELD)
    raw_card(state, ROWS['Island'], 3-seat, Zone.BATTLEFIELD)
    before = serialize_match_snapshot(state)
    engine, agent = RulesEngine(), AIAgent(difficulty='master')
    announced = checked_action(state, engine, seat, {'type': 'attack', 'attackers': [source]})
    public, _ = decision_view(announced, seat, [])
    inventory = public_graveyard_inventory(public, seat)
    assert inventory['status'] == 'interactive'
    assert agent._complete_strategic_combat_leaf(announced, seat) is None
    offered = checked_action(announced, engine, seat, {'type': 'pass_priority'})
    moves = engine.legal_moves(offered, 3-seat)
    assert any(m['type'] == 'cast_spell' and m.get('card_id') == deluge.id and m.get('from_graveyard')
               for m in moves)
    action = {'type': 'cast_spell', 'card_id': deluge.id, 'from_graveyard': True,
              'cost_choice': {'id': 'flashback'}}
    paid = checked_action(offered, engine, 3-seat, action)
    item = paid.stack[-1]
    assert item.source_card_id == deluge.id and item.payload['mana_spent'] == 7
    assert item.payload['__flashback'] is True and stack_object_kind(paid, item) == 'spell'
    assert agent._complete_strategic_combat_leaf(paid, seat) is None
    assert serialize_match_snapshot(state) == before
    (tmp_path / 'interactive-actual-trace.json').write_text(json.dumps({
        'root_id': state.id, 'seat': seat, 'inventory': inventory,
        'offered_actual_responses': moves, 'paid_action': action,
        'mana_spent': item.payload['mana_spent'], 'typed_kind': 'spell', 'root_unchanged': True}, indent=2))


def canonical(name):
    seed = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_bytes())
    return {**seed['cards'][name], 'card_name': name, 'card_data_sources': ['offline_seed']}


@pytest.mark.parametrize('name', ['Soul-Scar Mage', 'Searing Blaze'])
def test_current_known_gap_diagnostics_not_unconditional_execution_certificates(name):
    row = canonical(name)
    before = deepcopy(row)
    legacy = known_unsupported_mechanics(row['oracle_text'], card_name=name)
    contextual = known_unsupported_mechanics(row['oracle_text'], card_name=name, canonical_context=row)
    assert legacy == ([] if name == 'Soul-Scar Mage' else LINKED_GAPS)
    assert contextual == []
    # Unknown context does not become the sourced complete-body exception.
    assert known_unsupported_mechanics(row['oracle_text'], card_name=name, canonical_context={}) == legacy
    assert row == before


@pytest.mark.parametrize('bad', ['source', 'layout', 'cost', 'remaining_body'])
def test_complete_linked_damage_diagnostic_does_not_clear_unbacked_or_unaccounted_context(bad):
    row = canonical('Searing Blaze')
    if bad == 'source':
        row['card_data_sources'] = []
    elif bad == 'layout':
        row['layout'] = 'unknown'
    elif bad == 'cost':
        row['mana_cost'] = '{1}{R}'
    else:
        # Diagnostic adversary only: canonical raw bytes never edited or renamed.
        row['oracle_text'] += '\nAn unaccounted extra instruction.'
    before = deepcopy(row)
    assert known_unsupported_mechanics(row['oracle_text'], card_name=row['card_name'],
                                      canonical_context=row) == LINKED_GAPS
    assert row == before
