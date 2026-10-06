"""Real paid shuffles retain static provenance and resolve canonical observers."""
import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.zone_actions import sacrifice_selected
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import SELF, ROWS as BASE, act, execute, position, restart
from tests.test_self_graveyard_replacement_interactions import ROWS
from tests.test_self_graveyard_cost_routing import tower_position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('foreign', [False, True])
@pytest.mark.parametrize('route', ['spell_cost', 'mana_cost'])
def test_actual_probe_static_receipt_and_two_damage_resolution(seat, name, foreign, route, tmp_path):
    if route == 'spell_cost':
        state, card, source, _, action = position(name, seat, 'sacrifice', foreign)
    else:
        state, card, source, _, action = tower_position(seat, name, foreign)
    owner = card.owner
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-owner, Zone.BATTLEFIELD)
    reference = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
    life = state.players[owner].life
    state = execute(state, source, seat, 'sacrifice', action) if route == 'spell_cost' else act(state, seat, action)
    state = restart(state, tmp_path, 'paid-static-receipt')
    receipts = [item for item in state.stack if item.source_card_id == probe.id]
    assert len(receipts) == 1
    cause = receipts[0].payload['__shuffle_cause']
    assert cause['kind'] == 'static' and cause['mechanism'] == 'replacement'
    assert 'stack_id' not in cause
    assert cause['source_card_id'] == card.id and cause['source_card_id'] != source.id
    assert cause['controller'] == seat and cause['source_owner'] == owner
    assert cause['source_zone'] == 'battlefield' and cause['source_reference'] == reference
    assert cause['ability_clause'] == BASE[name]['oracle_text'].splitlines()[cause['ability_index']]
    assert state.cards[card.id].zone == Zone.LIBRARY
    for _ in range(3):
        if not any(item.source_card_id == probe.id for item in state.stack):
            break
        assert resolve_top_of_stack(state)
    assert not any(item.source_card_id == probe.id for item in state.stack)
    assert state.players[owner].life == life - 2
    state = restart(state, tmp_path, 'resolved-probe')
    assert state.players[owner].life == life - 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign', [False, True])
def test_trusted_simultaneous_batch_prepares_all_real_references(seat, foreign, tmp_path):
    state, first, _, death_observer, _ = position('Darksteel Colossus', seat, 'sacrifice')
    second = raw_card(state, BASE['Progenitus'], seat, Zone.BATTLEFIELD)
    if foreign:
        # Controlled retained board, not a claimed naturally played control spell.
        second.owner = 3-seat
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    references = {card.id: {'incarnation': object_incarnation(card),
                            'zone_change_sequence': card.zone_change_sequence}
                  for card in (first, second)}
    assert sacrifice_selected(state, seat, [first.id, second.id])
    state = restart(state, tmp_path, 'simultaneous-static')
    receipts = [item for item in state.stack if item.source_card_id == probe.id]
    assert len(receipts) == 2
    assert {item.payload['__shuffle_cause']['source_card_id'] for item in receipts} == set(references)
    for item in receipts:
        cause = item.payload['__shuffle_cause']
        assert cause['source_reference'] == references[cause['source_card_id']]
        assert cause['kind'] == 'static' and 'stack_id' not in cause
    assert not any(item.source_card_id == death_observer.id for item in state.stack)
