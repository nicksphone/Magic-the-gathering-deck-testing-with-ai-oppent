"""Real paid canonical Saga through native turn progression, before mixed entry."""
from copy import deepcopy

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from tests.test_graveyard_self_activation_product import position, FAMILIES, raw_card, act, snapshot
from tests.test_resident_entry_counter_provider import BALLISTA
from test_mixed_entry_origin_audit import ROWS, finish_priority, record


@pytest.mark.parametrize('seat', [1, 2])
def test_strict_paid_fenrir_next_cast_publishes_real_delayed_trigger(request, seat):
    state, _ = position(seat, FAMILIES[0])
    # Explicit constructed starting board, using existing full hydrated Islands.
    # These are not claimed historical land plays or newly drawn resources.
    for cid in list(state.players[seat].library[:4]):
        card = state.cards[cid]
        assert card.name == 'Island'
        state.players[seat].library.remove(cid)
        state.players[seat].battlefield.append(cid)
        card.move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cid)
        card.summoning_sick = False
    source = raw_card(state, ROWS['Summon: Fenrir'], seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 2}
    initial = snapshot(state)
    state = finish_priority(act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}}))
    assert state.cards[source.id].zone == Zone.BATTLEFIELD
    assert state.cards[source.id].counters['__lore'] == 1
    steps = []
    chapter = None
    for _ in range(96):
        chapter = next((item for item in state.stack if item.source_card_id == source.id
                        and item.payload.get('__chapter_number') == 2), None)
        if chapter:
            break
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        steps.append({'turn': state.turn, 'step': state.step.value,
                      'actor': state.priority_player, 'action': {'type': 'pass_priority'}})
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert chapter is not None, 'Native turn path did not reach the second Saga chapter'
    original_frame = deepcopy(chapter.__dict__)
    source_pre = {'incarnation': object_incarnation(state.cards[source.id]),
                  'zone_change_sequence': state.cards[source.id].zone_change_sequence}
    state = finish_priority(state)
    assert state.pending_entry_counters and state.pending_entry_counters[0]['amount'] == 1
    generated = deepcopy(state.pending_entry_counters)
    card = raw_card(state, BALLISTA, seat, Zone.HAND)
    state.replacement_choice_players = {seat}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                             'targets': {'x_value': 2}})
    assert state.cards[card.id].zone == Zone.STACK
    assert not any(state.players[seat].mana_pool.values())
    record(request, scope='strict delayed-cast-trigger upstream prerequisite, not final mixed ordering',
           initial=initial, native_phase_actions=steps, chapter_frame=original_frame,
           measured_source_pre=source_pre, generated=generated, after_next_cast=snapshot(state))
    assert len(state.stack) >= 2, (
        'When-you-next-cast trigger was flattened into an entry seed; no real trigger above the paid spell')
