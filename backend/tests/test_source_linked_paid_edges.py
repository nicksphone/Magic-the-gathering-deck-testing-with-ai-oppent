"""NEW paid edge episodes on declared canonical resource boards, both seats."""
from copy import deepcopy

import pytest

from tests.test_source_linked_exile import (
    action, cast, position, next_main, activate, raw_card, FACTS, ROWS,
    BOOMERANG, reference, exile_permission, snap, deserialize_match_snapshot,
    Zone, resolve_top_of_stack,
)
from tests.test_source_linked_exile import RAW
from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def next_main_playing_lands(state, seat):
    turn = state.turn
    for _ in range(400):
        if state.turn > turn and state.active_player == seat and state.step == Step.PRECOMBAT_MAIN and not state.stack:
            return state
        if state.step == Step.UNTAP and not state.stack:
            assert RulesEngine().advance_no_priority_step(state)
            continue
        actor = state.priority_player
        moves = RulesEngine().legal_moves(state, actor)
        land = next((m for m in moves if m['type'] == 'play_land'), None)
        assert not state.pending_mechanic_choice, 'Canonical land-play protocol must not need cleanup discards'
        state = action(state, actor, land or {'type': 'pass_priority'})
    raise AssertionError('Paid land-play turn transition exceeded bound')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['pending_source_departure', 'target_departure', 'stale_reexile'])
def test_paid_pending_and_reference_edges(case, seat):
    state, source = position(seat)
    if case == 'pending_source_departure':
        state = action(state, seat, {'type': 'activate_loyalty', 'card_id': source,
                                    'ability_index': 0, 'targets': {}})
        pending = state.stack[-1].id
        before_cards = deepcopy(state.loyalty_permissions[0]['cards'])
        assert not before_cards
        for _ in range(3):
            bolt = raw_card(state, ROWS['Lightning Bolt'], 3-seat, Zone.HAND)
            state = cast(state, 3-seat, bolt.id, {'target_card_id': source})
        assert state.cards[source].zone == Zone.GRAVEYARD
        assert state.stack[-1].id == pending
        state = deserialize_match_snapshot(snap(state))
        assert resolve_top_of_stack(state)
        refs = state.loyalty_permissions[0]['cards']
        assert len(refs) == 2
        assert all(exile_permission(state, seat, ref['id']) for ref in refs)
        return
    target = raw_card(state, FACTS['Elvish Mystic'], seat, Zone.HAND)
    state = cast(state, seat, target.id)
    if case == 'target_departure':
        state = action(state, seat, {'type': 'activate_loyalty', 'card_id': source,
                                    'ability_index': 1, 'targets': {'target_card_id': target.id}})
        old = reference(state.cards[target.id])
        bounce = raw_card(state, BOOMERANG, 3-seat, Zone.HAND)
        state = cast(state, 3-seat, bounce.id, {'target_card_id': target.id})
        assert state.cards[target.id].zone == Zone.HAND
        assert reference(state.cards[target.id]) != old
        state = deserialize_match_snapshot(snap(state))
        assert resolve_top_of_stack(state)
        assert state.cards[target.id].zone == Zone.HAND
        assert not state.loyalty_permissions[0]['cards']
        assert state.cards[source].loyalty == 2
        return
    state = activate(state, seat, source, 1, {'target_card_id': target.id})
    old = deepcopy(state.loyalty_permissions[0]['cards'])
    assert exile_permission(state, seat, target.id)
    state = cast(state, seat, target.id, from_exile=True)
    assert not exile_permission(state, seat, target.id)
    bounce = raw_card(state, BOOMERANG, seat, Zone.HAND)
    state = cast(state, seat, bounce.id, {'target_card_id': source})
    state = cast(state, seat, source, selected_face_index=1)
    assert len(state.emblems) == 2
    state = activate(state, seat, source, 1, {'target_card_id': target.id})
    assert state.loyalty_permissions[0]['cards'] == old
    current = reference(state.cards[target.id])
    assert current not in old and current in state.loyalty_permissions[1]['cards']
    assert exile_permission(state, seat, target.id)
    assert not exile_permission(state, 3-seat, target.id)
    state = deserialize_match_snapshot(snap(state))
    assert state.loyalty_permissions[0]['cards'] == old
    assert exile_permission(state, seat, target.id)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_empty_graveyard_ultimate(seat):
    # Fixed canonical deck/input, not a hand/zone or loyalty reward injection.
    deck = [{**RAW, 'card_name': RAW['name'], 'quantity': 1},
            {**FACTS['Forest'], 'card_name': 'Forest', 'quantity': 59}]
    state = MatchFactory.from_decks(deck, deck, seed=201)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        player.mana_pool = {'C': 10, 'B': 1, 'R': 1}
    source = next(i for i in state.players[seat].hand if state.cards[i].card_faces)
    state = cast(state, seat, source, selected_face_index=1)
    for _ in range(2):
        state = activate(state, seat, source, 0)
        land = next(i for i in state.players[seat].hand if state.cards[i].name == 'Forest')
        state = action(state, seat, {'type': 'play_land', 'card_id': land})
        state = next_main_playing_lands(state, seat)
    assert state.cards[source].loyalty == 9
    assert all(not p.graveyard for p in state.players.values())
    before = state.players[seat].mana_pool.get('R', 0)
    refs = deepcopy(state.loyalty_permissions[0]['cards'])
    state = activate(state, seat, source, 2)
    assert state.players[seat].mana_pool.get('R', 0) == before + 3
    assert state.loyalty_permissions[0]['cards'] == refs
