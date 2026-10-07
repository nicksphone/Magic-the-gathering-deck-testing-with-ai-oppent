"""Bounded public receipts and actual canonical continuations, not card certificates."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from ai.information import decision_view
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.events import public_trigger_clause_coverage
from rules_engine.graveyard_inventory import public_graveyard_inventory
from rules_engine.oracle_effects import complete_stack_instruction_coverage
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_empty_hand_attack_witness import ROWS, position, finish_combat
from tests.test_graveyard_inventory_feasibility import CARDS
from tests.test_linked_damage_targets import raw_card
from tests.test_public_combat_boundary_audit import response_window


data = (Path(__file__).parent / 'fixtures/graveyard_inventory_audit/divination.json').read_bytes()
assert hashlib.sha256(data).hexdigest() == 'c7e97ec83cb179f7e460982b8e88c3cc10738c45841e3462af93ecd51a5dc5ca'
DIVINATION = json.loads(data)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Sheoldred, the Apocalypse', 'Torrential Gearhulk'])
@pytest.mark.parametrize('raw', [ROWS['Lightning Bolt'], DIVINATION], ids=['damage', 'draw'])
def test_complete_public_inventory_actual_attack_and_snapshot(seat, family, raw):
    state, source = position(seat, family, counter=True)
    grave = raw_card(state, raw, 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    agent = AIAgent(difficulty='master', archetype='Control')
    announced, _, _ = response_window(state, seat, source)
    actor, _ = decision_view(announced, seat, [])
    inventory = public_graveyard_inventory(actor, seat)
    assert inventory['status'] == 'inert'
    assert any(r['reference']['id'] == grave.id for r in inventory['receipts'])
    assert agent._complete_strategic_combat_leaf(announced, seat) is not None
    decision = agent.choose_action(state, agent.engine.legal_moves(state, seat), seat)
    assert decision.action['type'] == 'attack' and source in decision.action['attackers']
    done = finish_combat(checked_action(state, agent.engine, seat, decision.action))
    assert done.players[3-seat].life == 20-int(ROWS[family]['power'])
    assert done.players[seat].hand == state.players[seat].hand
    assert {cid: done.cards[cid].tapped for cid in state.players[seat].battlefield if 'Land' in state.cards[cid].types} == {
        cid: state.cards[cid].tapped for cid in state.players[seat].battlefield if 'Land' in state.cards[cid].types}
    assert public_graveyard_inventory(deserialize_match_snapshot(serialize_match_snapshot(actor)), seat) == inventory
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Reassembling Skeleton', 'Woe Strider', 'Nether Traitor', 'Past in Flames', 'Gravecrawler'])
def test_uncovered_or_interactive_graveyard_not_inert(seat, family):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    raw_card(state, CARDS[family], 3-seat, Zone.GRAVEYARD)
    before = serialize_match_snapshot(state)
    assert public_graveyard_inventory(state, seat)['status'] != 'inert'
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['delayed_triggers', 'staged_triggers', 'pending_entry_counters',
    'linked_exiles', 'pending_mechanic_choice', 'pending_trigger_order', 'graveyard_permission_uses'])
def test_uncovered_context_veto_even_without_current_offers(seat, field):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    # Fault-injection context, not a fabricated canonical ability or event.
    setattr(state, field, {'uncovered': True} if isinstance(getattr(state, field), dict)
            or getattr(state, field) is None else [{'uncovered': True}])
    assert public_graveyard_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['suffix', 'unknown-keyword', 'grant', 'stale-face', 'extra-state',
    'missing-oracle', 'type-mismatch', 'extra-card', 'duplicate', 'stale-membership',
    'missing-layout', 'missing-faces', 'unknown-player', 'unknown-land-keyword',
    'missing-name', 'missing-cost', 'null-counters', 'null-effects',
    'null-staging', 'null-player-zone'])
def test_metadata_and_functional_unknowns_veto(seat, fault):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    card = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    if fault == 'suffix': card.oracle_text += '\nUnknown continuation.'
    elif fault == 'unknown-keyword': card.keywords.append('unknown')
    elif fault == 'grant': card.granted_flashback = {'turn': state.turn, 'zone_sequence': card.zone_change_sequence}
    elif fault == 'stale-face': card.selected_face_index = 1
    elif fault == 'extra-state': state.uncovered_permission = {'source': card.id}
    elif fault == 'missing-oracle': card.oracle_text = None
    elif fault == 'type-mismatch': card.type_line = 'Creature'
    elif fault == 'extra-card': card.uncovered_grant = True
    elif fault == 'duplicate': state.players[3-seat].graveyard.append(card.id)
    elif fault == 'stale-membership': card.move_to_zone(Zone.EXILE)
    elif fault == 'missing-layout': card.layout = ''
    elif fault == 'missing-faces': card.card_faces = None
    elif fault == 'unknown-player': state.players[3-seat].uncovered_permission = True
    elif fault == 'unknown-land-keyword': state.cards[state.players[3-seat].battlefield[0]].keywords = ['unknown']
    elif fault == 'missing-name': card.name = ''
    elif fault == 'missing-cost': card.mana_cost = None
    elif fault == 'null-counters': card.counters = None
    elif fault == 'null-effects': card.keyword_effects = None
    elif fault == 'null-staging': state.staged_triggers = None
    elif fault == 'null-player-zone': state.players[3-seat].battlefield = None
    assert public_graveyard_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Additional instruction.', '\nDraw a card.', ' If you do, draw a card.'])
def test_whole_instruction_and_domain_unknown_suffix(seat, suffix):
    state, source = position(seat, 'Torrential Gearhulk')
    source = state.cards[source]
    clause = source.oracle_text.splitlines()[-1]
    assert public_trigger_clause_coverage(source, clause)
    assert public_trigger_clause_coverage(source, clause + suffix) is None
    card = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    assert complete_stack_instruction_coverage(card)
    card.oracle_text += suffix
    assert complete_stack_instruction_coverage(card) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('draw_owner', ['controller', 'opponent'])
@pytest.mark.parametrize('depart', [False, True])
def test_native_draw_life_sequence_retains_source_controller_after_departure(seat, draw_owner, depart):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    source_card = state.cards[source]
    clause = source_card.oracle_text.splitlines()[1 if draw_owner == 'controller' else 2]
    receipt = public_trigger_clause_coverage(source_card, clause)
    assert receipt and receipt['source_reference'] == {'id': source,
        'incarnation': object_incarnation(source_card), 'zone_change_sequence': source_card.zone_change_sequence}
    recipient = seat if draw_owner == 'controller' else 3-seat
    before = state.players[recipient].life
    resolve_effect(state, recipient, 'draw_cards', {'amount': 1})
    assert len(state.stack) == 1 and state.stack[-1].controller == seat
    assert state.stack[-1].effect_key == receipt['effect_key']
    if depart:
        # Trusted native bounce after the real draw trigger, not a claimed paid response.
        resolve_effect(state, 3-seat, 'return_permanent_to_hand', {'target_card_id': source})
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(restored)
    assert restored.players[recipient].life == before + (2 if recipient == seat else -2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('decline', [False, True])
def test_paid_native_self_entry_optional_cast_and_exile_sequence(seat, decline):
    state, source = position(seat, 'Torrential Gearhulk')
    # Funded setup: move the canonical source to hand, then actually pay its cast.
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source})
    card = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool = {'U': 2, 'C': 4}
    state.mechanic_choice_players = {seat}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source})
    assert resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.stack[-1].effect_key == 'cast_from_graveyard'
    assert state.stack[-1].payload['exile_after_cast'] is True
    assert not resolve_top_of_stack(state)  # Actual optional cast owns a paused resolution.
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    if decline:
        state = checked_action(state, RulesEngine(), seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
        assert state.cards[card.id].zone == Zone.GRAVEYARD and not state.stack
    else:
        state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': card.id,
            'from_graveyard': True, 'targets': {'target_player': 3-seat}})
        assert state.stack[-1].payload['__exile_instead_of_graveyard'] is True
        life = state.players[3-seat].life
        assert resolve_top_of_stack(state)
        assert state.cards[card.id].zone == Zone.EXILE and state.players[3-seat].life == life-3


def test_pure_guard_precollection_aliases_and_audit():
    import socket, sqlite3, sqlite3.dbapi2, _sqlite3
    for connect in (sqlite3.connect, sqlite3.dbapi2.connect, _sqlite3.connect):
        with pytest.raises(AssertionError): connect(':memory:')
    with pytest.raises(AssertionError): socket.create_connection(('127.0.0.1', 1))
    import sys
    for event in ('sqlite3.connect', 'socket.connect'):
        with pytest.raises(AssertionError): sys.audit(event, None)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['wrong-subject', 'conditional', 'wrong-life-recipient', 'suffix'])
def test_full_draw_subject_and_body_negatives(seat, fault):
    state, source = position(seat, 'Sheoldred, the Apocalypse')
    source = state.cards[source]
    clause = source.oracle_text.splitlines()[1]
    if fault == 'wrong-subject': clause = clause.replace('you draw', 'a player draws')
    elif fault == 'conditional': clause = clause.replace(', you gain', ', if you control a creature, you gain')
    elif fault == 'wrong-life-recipient': clause = clause.replace('you gain', 'they lose')
    elif fault == 'suffix': clause += ' Draw a card.'
    assert public_trigger_clause_coverage(source, clause) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('departure', ['source-bounce', 'target-exile-return'])
def test_native_self_entry_reference_after_real_paid_source_cast(seat, departure):
    state, source = position(seat, 'Torrential Gearhulk')
    resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source})
    card = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    state.players[seat].mana_pool = {'U': 2, 'C': 4}
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source})
    assert resolve_top_of_stack(state)
    trigger = state.stack[-1]
    assert trigger.effect_key == 'cast_from_graveyard'
    card = state.cards[card.id]
    assert trigger.payload['target_card_id'] == card.id
    reference = [object_incarnation(state.cards[card.id]), state.cards[card.id].zone_change_sequence]
    if departure == 'source-bounce':
        # Trusted native bounce response, not a causal paid Unsummon certificate.
        resolve_effect(state, seat, 'return_permanent_to_hand', {'target_card_id': source})
    else:
        # Trusted old-object probe: exact native exile, then explicit reentry.
        resolve_effect(state, seat, 'exile_from_graveyard', {'target_card_id': card.id})
        state.players[seat].exile.remove(card.id)
        card.move_to_zone(Zone.GRAVEYARD)
        state.players[seat].graveyard.append(card.id)
        assert [object_incarnation(state.cards[card.id]), state.cards[card.id].zone_change_sequence] != reference
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    if departure == 'source-bounce':
        assert state.cards[source].zone == Zone.HAND
        assert state.cards[card.id].zone == Zone.STACK
        assert state.stack[-1].payload['__exile_instead_of_graveyard'] is True
    else:
        assert not state.stack and state.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('affordable', [False, True])
def test_public_external_grant_source_veto_is_not_an_affordability_query(seat, affordable):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    raw_card(state, CARDS['Snapcaster Mage'], 3-seat, Zone.BATTLEFIELD)
    for cid in state.players[3-seat].battlefield:
        if 'Land' in state.cards[cid].types:
            state.cards[cid].tapped = not affordable
    assert public_graveyard_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
def test_hidden_identity_does_not_supply_inventory_coverage(seat):
    state, _ = position(seat, 'Sheoldred, the Apocalypse')
    raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.GRAVEYARD)
    first, _ = decision_view(state, seat, [])
    before = public_graveyard_inventory(first, seat)
    hidden_id = state.players[3-seat].library[0]
    state.cards[hidden_id].name = CARDS['Snapcaster Mage']['name']
    state.cards[hidden_id].oracle_text = CARDS['Snapcaster Mage']['oracle_text']
    second, _ = decision_view(state, seat, [])
    assert not second.cards[hidden_id].name and not second.cards[hidden_id].oracle_text
    assert public_graveyard_inventory(second, seat) == before
