"""Canonical discard creates the real cleanup trigger through ASGI actions."""
import hashlib
import json

import pytest

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from tests.cleanup_canonical_db4e import canonical_entry
from tests.test_manual_autoplay_collision_http import (
    install_humans, post_action, record_seam, seam_api, stable,
)
from tests.test_temporary_characteristics_http import restore


@pytest.mark.parametrize("seat", [1, 2], ids=["seat1", "seat2"])
def test_canonical_discard_trigger_priority_repeat_cleanup_through_http(seam_api, request, seat):
    api = seam_api
    decks = {seat: [canonical_entry("Island", 60)],
             3 - seat: [canonical_entry("Sangromancer", 1), canonical_entry("Island", 59)]}
    state = MatchFactory.from_decks(decks[1], decks[2], seed=9)
    state.pregame_pending = False
    state.active_player = state.priority_player = seat
    state.step = Step.END_STEP
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    # All printed facts/stock originate at real factory birth. Only the finite
    # initial zone/step poses change; no StackItem or pending choice is injected.
    source = next(card for card in state.cards.values()
                  if card.name == "Sangromancer" and card.owner == 3 - seat)
    getattr(state.players[3 - seat], source.zone.value).remove(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    state.players[3 - seat].battlefield.append(source.id)
    assign_static_order_on_battlefield_entry(state, source.id)
    cid = state.players[seat].library.pop()
    state.cards[cid].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(cid)
    assert len(state.players[seat].hand) == 8 and not state.stack
    assert state.pending_mechanic_choice is None
    controller = install_humans(api, state, seat)
    turn, life = state.turn, state.players[3 - seat].life
    base_revision = controller.revision
    posts = 0

    def action(actor, value):
        nonlocal posts
        response = post_action(api, controller, actor, value)
        posts += 1
        return response

    def pass_once():
        actor = controller.state.priority_player
        response = api.client.get(f"/matches/{state.id}/legal-moves?player_id={actor}")
        assert response.status_code == 200
        assert any(move["type"] == "pass_priority" for move in response.json()["moves"])
        action(actor, {"type": "pass_priority"})

    pass_once()
    pass_once()
    current = controller.state
    assert current.step == Step.CLEANUP and current.turn == turn
    choice = current.pending_mechanic_choice
    assert choice["kind"] == "cleanup_discard" and choice["player_id"] == seat and choice["count"] == 1
    discard = choice["options"][0]
    before = stable(api, controller)
    for actor, ids in [(3 - seat, [discard]), (seat, [discard, discard])]:
        rejected = api.client.post(f"/matches/{state.id}/action", json={
            "player_id": actor, "action": {"type": "choose_mechanic", "card_ids": ids},
        })
        assert rejected.status_code == 422
        assert stable(api, controller) == before
    action(seat, {"type": "choose_mechanic", "card_ids": [discard]})
    current = controller.state
    assert len(current.stack) == 1
    assert current.stack[0].source_card_id == source.id and current.stack[0].controller == 3 - seat
    assert current.stack[0].payload["__trigger_event"] == "discard"
    assert current.cleanup_repeat_required and current.priority_player == seat
    assert current.cards[discard].zone == Zone.GRAVEYARD
    assert current.players[3 - seat].life == life
    controller = restore(api, controller)

    priority_posts = optional_posts = 0
    for _ in range(8):
        current = controller.state
        if not current.stack:
            break
        pending = current.pending_trigger_order
        if pending:
            assert pending["phase"] == "optional" and priority_posts >= 2
            assert pending["current_controller"] == 3 - seat
            action(3 - seat, {"type": "choose_optional_effect",
                              "stack_id": pending["current_stack_id"], "accept": True})
            optional_posts += 1
        else:
            pass_once()
            priority_posts += 1
    current = controller.state
    assert not current.stack and current.pending_trigger_order is None
    assert priority_posts == 2 and optional_posts == 1
    assert current.players[3 - seat].life == life + 3
    assert current.cleanup_repeat_required and current.turn == turn
    pass_once()
    pass_once()
    current = controller.state
    assert current.step == Step.CLEANUP and current.turn == turn
    assert not current.cleanup_repeat_required and current.pending_mechanic_choice is None
    assert len(current.players[seat].hand) == 7
    assert current.players[seat].graveyard.count(discard) == 1
    assert current.players[3 - seat].life == life + 3
    controller = restore(api, controller)
    pass_once()
    pass_once()
    assert controller.state.turn == turn + 1
    assert controller.state.active_player == 3 - seat
    assert controller.state.players[3 - seat].life == life + 3
    assert controller.revision == base_revision + posts
    final = stable(api, controller)
    controller = restore(api, controller)
    assert stable(api, controller) == final
    digest = hashlib.sha256(json.dumps(final, sort_keys=True).encode()).hexdigest()
    record_seam(api, request, seat=seat, accepted_action_posts=posts,
                trigger_priority_posts=priority_posts, explicit_optional_choices=optional_posts,
                life_gain=3, repeat_cleanup_then_next_turn=True,
                atomic_negative_checks=2, state_controller_sql_restored_equal=True,
                final_digest=digest)
