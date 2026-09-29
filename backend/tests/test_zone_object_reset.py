"""A card returning to the battlefield is a new object, not its old permanent."""

from effects.handlers import destroy_permanent, exile_all_creatures, exile_permanent, put_green_creature_from_hand, return_creature_from_graveyard_to_battlefield, return_permanent_to_hand, transform_card
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.attachments import attach_if_legal
from rules_engine.continuous import effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state():
    deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=418)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    return state


def test_bounced_creature_loses_old_counters_and_damage_on_reentry():
    state = _state()
    bear = CardInstance(
        id="bear", name="Grizzly Bears", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Creature"], type_line="Creature - Bear", mana_cost="{1}{G}",
        power=2, toughness=2, counters={"+1/+1": 2, "__damage_marked": 1, "__eot_toughness": 1},
    )
    state.cards[bear.id] = bear
    state.players[1].battlefield.append(bear.id)
    return_permanent_to_hand(state, 2, {"target_card_id": bear.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    put_green_creature_from_hand(state, 1, {})

    assert state.cards[bear.id].zone == Zone.BATTLEFIELD
    assert state.cards[bear.id].counters == {}
    assert effective_toughness(state, bear.id) == 2


def test_escape_enters_with_only_its_new_counter():
    state = _state()
    ox = CardInstance(
        id="ox", name="Ox of Agonas", owner=1, controller=1, zone=Zone.GRAVEYARD,
        types=["Creature"], mana_cost="{3}{R}{R}", power=4, toughness=2,
        oracle_text="Escape—{R}{R}, Exile eight other cards from your graveyard.\nThis creature escapes with a +1/+1 counter on it.",
        counters={"+1/+1": 2, "__damage_marked": 1},
    )
    state.cards[ox.id] = ox
    state.players[1].graveyard.append(ox.id)
    for index in range(8):
        card_id = f"fuel-{index}"
        state.cards[card_id] = CardInstance(card_id, "Mountain", 1, 1, Zone.GRAVEYARD, ["Land"])
        state.players[1].graveyard.append(card_id)
    state.players[1].mana_pool["R"] = 2
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == ox.id and move["type"] == "cast_spell")
    RulesEngine().take_action(state, 1, move)
    assert resolve_top_of_stack(state)
    assert ox.zone == Zone.BATTLEFIELD
    assert ox.counters == {"+1/+1": 1}


def test_oracle_counter_persistence_except_hand_or_library():
    state = _state()
    skullbriar = CardInstance(
        id="skullbriar", name="Skullbriar, the Walking Grave", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], mana_cost="{B}{G}", power=1, toughness=1,
        oracle_text="Haste\nWhenever Skullbriar deals combat damage to a player, put a +1/+1 counter on it.\n"
                    "Counters remain on Skullbriar as it moves to any zone other than a player's hand or library.",
        counters={"+1/+1": 3, "__eot_toughness": 1},
    )
    state.cards[skullbriar.id] = skullbriar
    state.players[1].battlefield.append(skullbriar.id)
    destroy_permanent(state, 2, {"target_card_id": skullbriar.id})
    assert skullbriar.zone == Zone.GRAVEYARD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    return_creature_from_graveyard_to_battlefield(state, 1, {"target_card_id": skullbriar.id})
    assert state.cards[skullbriar.id].counters == {"+1/+1": 3}

    return_permanent_to_hand(state, 2, {"target_card_id": skullbriar.id})
    assert state.cards[skullbriar.id].counters == {}
    put_green_creature_from_hand(state, 1, {})
    assert state.cards[skullbriar.id].counters == {}
    state.cards[skullbriar.id].counters["+1/+1"] = 2
    state.cards[skullbriar.id].move_to_zone(Zone.LIBRARY)
    assert state.cards[skullbriar.id].counters == {}


def test_transformed_card_returns_to_printed_front_face_after_bounce():
    state = _state()
    delver = CardInstance(
        id="delver", name="Delver of Secrets", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature — Human Wizard",
        mana_cost="{U}", power=1, toughness=1, layout="transform",
        card_faces=[
            {"name": "Delver of Secrets", "type_line": "Creature — Human Wizard", "mana_cost": "{U}",
             "power": "1", "toughness": "1", "oracle_text": "At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this way, transform this creature."},
            {"name": "Insectile Aberration", "type_line": "Creature — Human Insect", "mana_cost": "",
             "power": "3", "toughness": "2", "oracle_text": "Flying", "image_uri": None},
        ],
    )
    state.cards[delver.id] = delver
    state.players[1].battlefield.append(delver.id)
    transform_card(state, 1, {"target_card_id": delver.id, "face_index": 1})
    assert delver.name == "Insectile Aberration"
    return_permanent_to_hand(state, 2, {"target_card_id": delver.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    delver = state.cards[delver.id]
    assert delver.name == "Delver of Secrets"
    assert delver.selected_face_index == 0
    assert delver.power == delver.toughness == 1


def test_equipment_and_target_leave_break_old_attachment():
    state = _state()
    bear = CardInstance("bear", "Grizzly Bears", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    sword = CardInstance(
        "sword", "Short Sword", 1, 1, Zone.BATTLEFIELD, ["Artifact"],
        mana_cost="{1}", type_line="Artifact — Equipment",
        oracle_text="Equipped creature gets +1/+1.\nEquip {1} ({1}: Attach to target creature you control. Equip only as a sorcery.)",
    )
    state.cards.update({bear.id: bear, sword.id: sword})
    state.players[1].battlefield.extend([bear.id, sword.id])
    assert attach_if_legal(state, sword.id, bear.id)

    return_permanent_to_hand(state, 2, {"target_card_id": sword.id})
    assert sword.attached_to is None
    state.players[1].mana_pool["C"] = 1
    RulesEngine().take_action(state, 1, {"type": "cast_spell", "card_id": sword.id}, reject_invalid=True)
    assert resolve_top_of_stack(state)
    assert sword.zone == Zone.BATTLEFIELD and sword.attached_to is None

    assert attach_if_legal(state, sword.id, bear.id)
    return_permanent_to_hand(state, 2, {"target_card_id": bear.id})
    assert sword.attached_to is None


def test_single_exile_clears_old_counters_and_combat_state():
    state = _state()
    spider = CardInstance(
        "spider", "Giant Spider", 1, 1, Zone.BATTLEFIELD, ["Creature"],
        power=2, toughness=4,
        counters={"+1/+1": 1, "__eot_power": 2, "__damage_marked": 3},
    )
    state.cards[spider.id] = spider
    state.players[1].battlefield.append(spider.id)
    exile_permanent(state, 2, {"target_card_id": spider.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[spider.id].zone == Zone.EXILE
    assert state.cards[spider.id].counters == {}


def test_batch_exile_collects_old_state_then_resets_new_zone(monkeypatch):
    state = _state()
    skullbriar = CardInstance(
        "skullbriar", "Skullbriar, the Walking Grave", 1, 1, Zone.BATTLEFIELD,
        ["Creature"], power=1, toughness=1,
        oracle_text="Counters remain on Skullbriar as it moves to any zone other than a player's hand or library.",
        counters={"+1/+1": 2, "__damage_marked": 1},
    )
    spider = CardInstance(
        "spider", "Giant Spider", 2, 2, Zone.BATTLEFIELD, ["Creature"],
        power=2, toughness=4, counters={"+1/+1": 1, "__eot_toughness": 2},
    )
    for card in (skullbriar, spider):
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)

    import rules_engine.events as events
    collect = events._collect_triggers
    observed = {}

    def capture(state, event, payload):
        if event == "leaves_battlefield":
            observed[payload["card_id"]] = dict(state.cards[payload["card_id"]].counters)
        return collect(state, event, payload)

    monkeypatch.setattr(events, "_collect_triggers", capture)
    exile_all_creatures(state, 1, {})
    assert observed[skullbriar.id]["+1/+1"] == 2
    assert observed[spider.id]["__eot_toughness"] == 2
    assert skullbriar.zone == spider.zone == Zone.EXILE
    assert skullbriar.counters == {"+1/+1": 2}
    assert spider.counters == {}
