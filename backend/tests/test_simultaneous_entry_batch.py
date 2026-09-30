import pytest

from effects.handlers import create_token
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.engine import RulesEngine


GROUP_ORACLE = (
    "Whenever one or more other Zombies you control enter, "
    "create a 1/1 black Zombie creature token."
)
EACH_ORACLE = "Whenever a creature enters the battlefield under your control, draw a card."


def _state():
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=92)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    for cid, oracle in (("group", GROUP_ORACLE), ("each", EACH_ORACLE)):
        card = CardInstance(
            id=cid, name=cid, owner=1, controller=1, zone=Zone.BATTLEFIELD,
            types=["Enchantment"], oracle_text=oracle,
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
    return state


def _token_triggers(state):
    return ([item for item in state.stack if item.source_card_id == "group"],
            [item for item in state.stack if item.source_card_id == "each"])


def test_two_tokens_enter_as_one_group_event_but_two_individual_entries():
    state = _state()
    create_token(state, 1, {
        "name": "Zombie", "type_line": "Token Creature — Zombie",
        "power": 1, "toughness": 1, "amount": 2,
    })
    group, each = _token_triggers(state)
    assert len(group) == 1
    assert len(each) == 2
    assert len([cid for cid in state.players[1].battlefield if state.cards[cid].is_token]) == 2


def test_human_defender_choices_do_not_split_a_simultaneous_token_event():
    state = _state()
    state.step = Step.DECLARE_ATTACKERS
    state.active_player = state.priority_player = 1
    state.mechanic_choice_players = {1}
    walker = CardInstance(
        id="walker", name="Walker", owner=2, controller=2, zone=Zone.BATTLEFIELD,
        types=["Planeswalker"], loyalty=3,
    )
    state.cards[walker.id] = walker
    state.players[2].battlefield.append(walker.id)
    assign_static_order_on_battlefield_entry(state, walker.id)

    create_token(state, 1, {
        "name": "Zombie", "type_line": "Token Creature — Zombie",
        "power": 1, "toughness": 1, "amount": 2, "tapped_and_attacking": True,
    })
    assert state.pending_mechanic_choice["kind"] == "attacking_token_target"
    RulesEngine().take_action(state, 1, {
        "type": "choose_mechanic", "card_ids": ["player:2"],
    }, reject_invalid=True)
    assert not any(state.cards[cid].is_token for cid in state.players[1].battlefield)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    RulesEngine().take_action(state, 1, {
        "type": "choose_mechanic", "card_ids": ["planeswalker:walker"],
    }, reject_invalid=True)
    group, each = _token_triggers(state)
    assert len(group) == 1
    assert len(each) == 2
    targets = [state.attack_targets[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert sorted(targets) == ["planeswalker:walker", "player:2"]


@pytest.mark.parametrize("effect_key,count_key", [
    ("topdeck_put_creatures_battlefield", "max_creatures"),
    ("topdeck_put_permanents_battlefield", "max_permanents"),
])
def test_topdeck_permanents_enter_as_one_group_event(effect_key, count_key):
    state = _state()
    chosen = state.players[1].library[-2:]
    for cid in chosen:
        card = state.cards[cid]
        card.name = "Zombie"
        card.types = ["Creature"]
        card.type_line = "Creature — Zombie"
        card.mana_cost = "{1}{B}"
        card.power = card.toughness = 2

    resolve_effect(state, 1, effect_key, {
        "top_n": 2, count_key: 2, "mv_max": 3, "selected_card_ids": chosen,
    })
    group, each = _token_triggers(state)
    assert all(cid in state.players[1].battlefield for cid in chosen)
    assert len(group) == 1
    assert len(each) == 2
