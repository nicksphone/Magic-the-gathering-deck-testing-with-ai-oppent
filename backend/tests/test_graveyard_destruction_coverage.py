"""Complete canonical destruction bodies; bounded inventory, not global certificates."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.graveyard_inventory import public_graveyard_inventory
from rules_engine.oracle_effects import complete_stack_instruction_coverage
from rules_engine.stack_engine import resolve_top_of_stack
from tests.pending_permanent_fullraw import raw_card as canonical_row
from tests.test_empty_hand_attack_witness import ROWS, finish_combat, position
from tests.test_linked_damage_targets import raw_card
from tests.test_public_combat_boundary_audit import response_window


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,cost', [('Murder', 3), ('Go for the Throat', 2)])
def test_native_destruction_paid_target_and_restore(seat, name, cost):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    spell = raw_card(state, canonical_row(name), seat, Zone.HAND)
    target = raw_card(state, canonical_row('Sprite Dragon'), 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'B': 2, 'C': 1}
    before = serialize_match_snapshot(state)
    paid = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell',
        'card_id': spell.id, 'targets': {'target_card_id': target.id}})
    assert paid.stack[-1].effect_key == 'destroy_permanent'
    assert paid.stack[-1].payload['mana_spent'] == cost
    assert sum(paid.players[seat].mana_pool.values()) == 3-cost
    restored = deserialize_match_snapshot(serialize_match_snapshot(paid))
    assert resolve_top_of_stack(restored)
    assert restored.cards[target.id].zone == Zone.GRAVEYARD
    assert restored.cards[spell.id].zone == Zone.GRAVEYARD
    assert not restored.stack
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,kind', [('Murder', 'missing'), ('Murder', 'land'),
    ('Go for the Throat', 'missing'), ('Go for the Throat', 'land'),
    ('Go for the Throat', 'artifact')])
def test_illegal_destruction_target_preserves_payment_and_state(seat, name, kind):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    spell = raw_card(state, canonical_row(name), seat, Zone.HAND)
    target = (raw_card(state, canonical_row('Darksteel Myr'), 3-seat, Zone.BATTLEFIELD)
              if kind == 'artifact' else state.cards[state.players[3-seat].battlefield[0]])
    state.players[seat].mana_pool = {'B': 2, 'C': 1}
    action = {'type': 'cast_spell', 'card_id': spell.id,
              'targets': {} if kind == 'missing' else {'target_card_id': target.id}}
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
@pytest.mark.parametrize('name,body,domain', [
    ('Murder', 'Destroy target creature.', 'target creature'),
    ('Go for the Throat', 'Destroy target nonartifact creature.', 'target nonartifact creature')])
def test_complete_destruction_inventory_actual_attack_and_restore(seat, family, name, body, domain):
    state, source = position(seat, family, counter=True)
    printed = canonical_row(name)
    assert printed['oracle_text'] == body and printed['layout'] == 'normal'
    grave = raw_card(state, printed, 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    announced, _, _ = response_window(state, seat, source)
    actor, _ = decision_view(announced, seat, [])
    inventory = public_graveyard_inventory(actor, seat)
    assert inventory['status'] == 'inert'
    assert next(r['coverage'] for r in inventory['receipts']
                if r['reference']['id'] == grave.id) == {
        'instruction': body, 'source_zone': 'stack', 'effect_key': 'destroy_permanent',
        'payload': {}, 'target_domain': domain, 'residual': ''}
    agent = AIAgent(difficulty='master', archetype='Control')
    assert agent._complete_strategic_combat_leaf(announced, seat) is not None
    decision = agent.choose_action(state, agent.engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'attack' and source in decision.action['attackers']
    done = finish_combat(checked_action(state, agent.engine, seat, decision.action))
    assert done.players[3-seat].life == 20-int(ROWS[family]['power'])
    assert done.cards[grave.id].zone == Zone.GRAVEYARD
    assert done.players[seat].hand == state.players[seat].hand
    assert public_graveyard_inventory(deserialize_match_snapshot(serialize_match_snapshot(actor)), seat) == inventory
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('name', ['Murder', 'Go for the Throat'])
@pytest.mark.parametrize('fault', ['suffix', 'parenthetical', 'condition', 'activated',
                                  'missing-period', 'extra-period'])
def test_destruction_coverage_rejects_original_text_residuals(name, fault):
    state, _ = position(1, 'Sheoldred, the Apocalypse')
    printed = deepcopy(canonical_row(name))
    body = printed['oracle_text']
    # Declared negative fault injection, never a claimed canonical instruction.
    printed['oracle_text'] = {
        'suffix': body + ' Draw a card.',
        'parenthetical': body + ' (You win the game.)',
        'condition': 'If you control a creature, ' + body[0].lower() + body[1:],
        'activated': '{1}: ' + body,
        'missing-period': body.removesuffix('.'),
        'extra-period': body + '.',
    }[fault]
    card = raw_card(state, printed, 2, Zone.GRAVEYARD)
    assert complete_stack_instruction_coverage(card) is None
    assert public_graveyard_inventory(state, 1)['status'] != 'inert'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Murder', 'Go for the Throat'])
@pytest.mark.parametrize('fault', ['keyword', 'grant'])
def test_destruction_inventory_keeps_permission_and_keyword_veto(seat, name, fault):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, canonical_row(name), 3-seat, Zone.GRAVEYARD)
    if fault == 'keyword':
        card.keywords.append('unknown')
    else:
        card.granted_flashback = {'turn': state.turn, 'zone_sequence': card.zone_change_sequence}
    assert public_graveyard_inventory(state, seat)['status'] != 'inert'
