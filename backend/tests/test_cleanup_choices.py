from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.zone_actions import discard_selected
from ai.agent import AIAgent


def setup(player_id=1):
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=9)
    state.pregame_pending = False
    state.active_player = state.priority_player = player_id
    state.step = Step.END_STEP
    state.replacement_choice_required = True
    state.replacement_choice_players = {player_id}
    player = state.players[player_id]
    cid = player.library.pop()
    player.hand.append(cid)
    state.cards[cid].zone = Zone.HAND
    return state, RulesEngine()


def test_ai_cleanup_discards_excess_land_instead_of_first_spell():
    state, engine = setup()
    state.replacement_choice_required = False
    state.replacement_choice_players = set()
    state.mechanic_choice_players = {1}
    player = state.players[1]
    spell_id = player.hand[0]
    state.cards[spell_id].name = "Counterspell"
    state.cards[spell_id].types = ["Instant"]
    state.cards[spell_id].mana_cost = "{U}{U}"
    for _ in range(5):
        cid = player.library.pop()
        player.battlefield.append(cid)
        state.cards[cid].zone = Zone.BATTLEFIELD
    engine.next_step(state)
    assert state.pending_mechanic_choice["kind"] == "cleanup_discard"
    action = AIAgent(archetype="Control").choose_action(state, engine.legal_moves(state, 1), 1).action
    assert action["card_ids"] != [spell_id]
    engine.take_action(state, 1, action, reject_invalid=True)
    assert spell_id in player.hand
    assert len(player.hand) == 7
    assert state.pending_mechanic_choice is None


def test_human_cleanup_choice_is_owned_validated_and_resumable_before_expiry():
    state, engine = setup(2)
    creature = CardInstance(id="bear", name="Grizzly Bears", owner=2, controller=2, zone=Zone.BATTLEFIELD, types=["Creature"], power=2, toughness=2, counters={"__eot_toughness": 1, "__damage_marked": 2})
    state.cards[creature.id] = creature
    state.players[2].battlefield.append(creature.id)
    engine.next_step(state)
    assert state.pending_mechanic_choice["kind"] == "cleanup_discard"
    assert state.priority_player == 2
    assert creature.counters["__damage_marked"] == 2
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    cid = state.players[2].hand[0]
    before = serialize_match_snapshot(state)
    for player_id, ids in [(1, [cid]), (2, [cid, cid]), (2, ["missing"])]:
        engine.take_action(state, player_id, {"type": "choose_mechanic", "card_ids": ids})
        assert serialize_match_snapshot(state) == before
    engine.next_step(state)
    assert state.turn == 1
    engine.take_action(state, 2, {"type": "choose_mechanic", "card_ids": [cid]})
    assert len(state.players[2].hand) == 7
    assert state.cards[creature.id].zone == Zone.BATTLEFIELD
    assert state.cards[creature.id].counters == {}
    assert state.pending_mechanic_choice is None
    assert not state.cleanup_repeat_required


def test_cleanup_discard_trigger_grants_priority_then_repeats_cleanup():
    state, engine = setup()
    trigger = CardInstance(id="sangromancer", name="Sangromancer", owner=2, controller=2, zone=Zone.BATTLEFIELD, types=["Creature"], power=3, toughness=3, oracle_text="Whenever an opponent discards a card, you gain 3 life.")
    state.cards[trigger.id] = trigger
    state.players[2].battlefield.append(trigger.id)
    engine.next_step(state)
    assert not state.stack
    cid = state.players[1].hand[0]
    engine.take_action(state, 1, {"type": "choose_mechanic", "card_ids": [cid]})
    assert len(state.stack) == 1
    assert state.stack[0].payload["__trigger_event"] == "discard"
    assert state.cleanup_repeat_required
    assert state.priority_player == 1
    resolve_top_of_stack(state)
    assert state.players[2].life == 23
    for _ in range(2):
        engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.step == Step.CLEANUP
    assert state.turn == 1
    assert not state.cleanup_repeat_required
    for _ in range(2):
        engine.take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.turn == 2


def test_discard_shared_operation_preserves_zone_owner_and_atomic_rejection():
    state, _ = setup()
    cid = state.players[1].hand[0]
    state.cards[cid].owner = 2
    before = serialize_match_snapshot(state)
    assert not discard_selected(state, 1, [cid, "missing"])
    assert serialize_match_snapshot(state) == before
    assert discard_selected(state, 1, [cid])
    assert cid in state.players[2].graveyard
    assert cid not in state.players[1].graveyard


def test_no_ordinary_cleanup_casting_or_activation():
    state, engine = setup()
    engine.next_step(state)
    cid = state.players[1].hand[0]
    engine.take_action(state, 1, {"type": "choose_mechanic", "card_ids": [cid]})
    assert engine.legal_moves(state, 1) == [{"type": "pass_priority"}]
    hand = list(state.players[1].hand)
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": hand[0]})
    assert state.players[1].hand == hand


def test_cleanup_stabilizes_cascading_state_based_actions_before_priority():
    state, engine = setup()
    lord = CardInstance(id="lord", name="Elvish Clancaller", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature - Elf Druid", power=1, toughness=1, oracle_text="Other Elf creatures you control get +1/+1.", counters={"-1/-1": 1, "__eot_toughness": 1})
    elf = CardInstance(id="elf", name="Llanowar Elves", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature - Elf Druid", power=1, toughness=1, counters={"-1/-1": 1})
    state.cards.update({lord.id: lord, elf.id: elf})
    state.players[1].battlefield.extend([lord.id, elf.id])
    engine.next_step(state)
    engine.take_action(state, 1, {"type": "choose_mechanic", "card_ids": [state.players[1].hand[0]]})
    assert lord.zone == Zone.GRAVEYARD
    assert elf.zone == Zone.GRAVEYARD
    assert state.cleanup_repeat_required
    assert not state.cleanup_pending
