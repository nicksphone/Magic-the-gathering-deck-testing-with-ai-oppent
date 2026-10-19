"""Canonical static replacement shuffle observers; no synthetic stack cause."""
import pytest

from game_state.state import Zone
from rules_engine.zone_actions import sacrifice_selected
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import SELF, act, execute, position, restart
from tests.test_self_graveyard_replacement_interactions import ROWS


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
@pytest.mark.parametrize('observer_name', ['Psychogenic Probe', "Cosi's Trickster"])
def test_actual_paid_static_replacement_causes_observer_trigger(seat, name, observer_name, tmp_path):
    state, card, source, _, action = position(name, seat, 'sacrifice')
    observer = raw_card(state, ROWS[observer_name], 3-seat, Zone.BATTLEFIELD)
    state = execute(state, source, seat, 'sacrifice', action)
    state = restart(state, tmp_path, 'actual-static-cause')
    assert state.cards[card.id].zone == Zone.LIBRARY
    receipts = [item for item in state.stack if item.source_card_id == observer.id]
    assert len(receipts) == 1
    assert receipts[0].payload['__shuffle_player'] == seat
    assert not state.cards[observer.id].counters


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_shared_replacement_observes_static_ability_without_stack_source(seat, name, tmp_path):
    state, card, source, _, _ = position(name, seat, 'sacrifice')
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    assert sacrifice_selected(state, seat, [card.id])
    state = restart(state, tmp_path, 'shared-static-cause')
    assert state.cards[card.id].zone == Zone.LIBRARY
    assert not any(item.source_card_id in {card.id, source.id} for item in state.stack)
    assert len([item for item in state.stack if item.source_card_id == cosi.id]) == 1
    assert len([item for item in state.stack if item.source_card_id == probe.id]) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_actual_tower_static_replacement_requires_both_observers(seat, name, tmp_path):
    state, card, _, _, _ = position(name, seat, 'sacrifice')
    tower = raw_card(state, ROWS['Phyrexian Tower'], seat, Zone.BATTLEFIELD)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {}
    state = act(state, seat, {'type': 'activate_mana_ability', 'card_id': tower.id,
                            'ability_index': 1, 'color': 'B',
                            'payment_choices': {'sacrifice_card_ids': [card.id]}})
    state = restart(state, tmp_path, 'tower-static-cause')
    assert state.players[seat].mana_pool.get('B') == 2
    assert state.cards[card.id].zone == Zone.LIBRARY
    assert not any(item.source_card_id in {tower.id, card.id} for item in state.stack)
    for observer in (probe, cosi):
        assert len([item for item in state.stack if item.source_card_id == observer.id]) == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', SELF)
def test_suppressed_static_ability_neither_shuffles_nor_triggers_observers(seat, name):
    state, card, source, _, action = position(name, seat, 'sacrifice')
    raw_card(state, ROWS['Humility'], 3-seat, Zone.BATTLEFIELD)
    probe = raw_card(state, ROWS['Psychogenic Probe'], 3-seat, Zone.BATTLEFIELD)
    cosi = raw_card(state, ROWS["Cosi's Trickster"], 3-seat, Zone.BATTLEFIELD)
    state = execute(state, source, seat, 'sacrifice', action)
    assert state.cards[card.id].zone == Zone.GRAVEYARD
    assert not any(item.source_card_id in {probe.id, cosi.id} for item in state.stack)
