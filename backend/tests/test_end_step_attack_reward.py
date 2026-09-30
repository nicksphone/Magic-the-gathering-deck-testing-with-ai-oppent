from effects.handlers import add_counters, create_token
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.combat import declare_attackers
from rules_engine.continuous import effective_power
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack


FRONT = (
    "At the beginning of your end step, put an invitation counter on this enchantment. "
    "If you attacked with two or more creatures this turn, draw a card. Otherwise, "
    "create a 1/1 white Human creature token. Then if this enchantment has three or more "
    "invitation counters on it, transform it."
)
FACES = [
    {"name": "Wedding Announcement", "type_line": "Enchantment", "mana_cost": "{2}{W}", "oracle_text": FRONT},
    {"name": "Wedding Festivity", "type_line": "Enchantment", "oracle_text": "Creatures you control get +1/+1."},
]


def _state():
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Plains"}],
        [{"quantity": 60, "card_name": "Plains"}], seed=73,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.DECLARE_ATTACKERS
    wedding = CardInstance(
        id="wedding", name="Wedding Announcement", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Enchantment"], oracle_text=FRONT,
        card_faces=FACES, layout="transform", selected_face_index=0,
    )
    state.cards[wedding.id] = wedding
    state.players[1].battlefield.append(wedding.id)
    assign_static_order_on_battlefield_entry(state, wedding.id)
    return state, wedding.id


def _bear(state, card_id):
    bear = CardInstance(id=card_id, name="Grizzly Bears", owner=1, controller=1,
                        zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2,
                        summoning_sick=False)
    state.cards[card_id] = bear
    state.players[1].battlefield.append(card_id)
    assign_static_order_on_battlefield_entry(state, card_id)


def _end_step(state):
    state.step = Step.END_STEP
    emit_event(state, "begin_step", {"step": "end_step", "active_player": 1})
    assert len(state.stack) == 1
    resolve_top_of_stack(state)


def test_no_attack_creates_token_then_transforms_only_on_third_resolution():
    state, wedding = _state()
    for count in (1, 2, 3):
        _end_step(state)
        assert state.cards[wedding].counters.get("invitation") == count
        assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == count
        assert state.cards[wedding].selected_face_index == (1 if count == 3 else 0)
    token = next(cid for cid in state.players[1].battlefield if state.cards[cid].is_token)
    assert effective_power(state, token) == 2


def test_two_declared_attackers_draw_even_after_they_leave_and_source_enters_later():
    state, wedding = _state()
    state.players[1].battlefield.remove(wedding)
    state.players[1].hand.append(wedding)
    state.cards[wedding].move_to_zone(Zone.HAND)
    for cid in ("bear-a", "bear-b"):
        _bear(state, cid)
    declare_attackers(state, ["bear-a", "bear-b"])
    assert state.declared_attackers_this_turn[1] == 2
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    for cid in ("bear-a", "bear-b"):
        state.players[1].battlefield.remove(cid)
        state.players[1].graveyard.append(cid)
        state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    state.players[1].hand.remove(wedding)
    state.players[1].battlefield.append(wedding)
    state.cards[wedding].move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, wedding)
    before = len(state.players[1].hand)
    _end_step(state)
    assert len(state.players[1].hand) == before + 1
    assert not any(state.cards[cid].is_token for cid in state.players[1].battlefield)


def test_token_put_onto_battlefield_attacking_does_not_count_as_declared_attacker():
    state, _ = _state()
    _bear(state, "bear")
    declare_attackers(state, ["bear"])
    create_token(state, 1, {"name": "Human", "power": 1, "toughness": 1, "tapped_and_attacking": True})
    assert len(state.attackers) == 2
    assert state.declared_attackers_this_turn[1] == 1
    _end_step(state)
    assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == 2


def test_extra_counters_do_not_transform_until_end_step_trigger_resolves():
    state, wedding = _state()
    add_counters(state, 1, {"target_card_id": wedding, "counter": "invitation", "amount": 3})
    assert state.cards[wedding].selected_face_index == 0
    _end_step(state)
    assert state.cards[wedding].selected_face_index == 1


def test_departed_source_trigger_still_makes_token_but_cannot_buff_new_incarnation():
    state, wedding = _state()
    state.step = Step.END_STEP
    emit_event(state, "begin_step", {"step": "end_step", "active_player": 1})
    state.players[1].battlefield.remove(wedding)
    state.players[1].hand.append(wedding)
    state.cards[wedding].move_to_zone(Zone.HAND)
    state.players[1].hand.remove(wedding)
    state.players[1].battlefield.append(wedding)
    state.cards[wedding].move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, wedding)
    resolve_top_of_stack(state)
    assert state.cards[wedding].counters.get("invitation", 0) == 0
    assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == 1


def test_declared_attacker_history_resets_at_new_turn():
    state, _ = _state()
    _bear(state, "bear")
    declare_attackers(state, ["bear"])
    assert state.declared_attackers_this_turn[1] == 1
    state.step = Step.CLEANUP
    RulesEngine().next_step(state)
    assert state.active_player == 2
    assert state.declared_attackers_this_turn == {1: 0, 2: 0}
