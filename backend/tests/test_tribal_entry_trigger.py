from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.continuous import effective_power, has_keyword
from rules_engine.engine import RulesEngine
from rules_engine.events import emit_event
from rules_engine.oracle_effects import infer_effect_from_oracle
from rules_engine.stack_engine import resolve_top_of_stack


ORACLE = (
    "Whenever one or more other Elves you control enter, create a 1/1 green Elf Warrior creature token. "
    "This ability triggers only once each turn.\n"
    "{5}{G}{G}: Elves you control get +2/+2 and gain deathtouch until end of turn."
)


def _state():
    deck = [{"quantity": 60, "card_name": "Forest"}]
    state = MatchFactory.from_decks(deck, deck, seed=87)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    source = CardInstance(
        id="watcher", name="Elvish Warmaster", owner=1, controller=1,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line="Creature — Elf Warrior",
        oracle_text=ORACLE, power=2, toughness=2,
    )
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    assign_static_order_on_battlefield_entry(state, source.id)
    return state


def _enter(state, cid, controller, type_line):
    card = CardInstance(
        id=cid, name=cid, owner=controller, controller=controller,
        zone=Zone.BATTLEFIELD, types=["Creature"], type_line=type_line,
        power=1, toughness=1,
    )
    state.cards[cid] = card
    state.players[controller].battlefield.append(cid)
    assign_static_order_on_battlefield_entry(state, cid)
    emit_event(state, "enters_battlefield", {"card_id": cid, "controller": controller})


def test_other_elf_triggers_once_after_irrelevant_entries_and_makes_typed_token():
    state = _state()
    emit_event(state, "enters_battlefield", {"card_id": "watcher", "controller": 1})
    _enter(state, "own-human", 1, "Creature — Human")
    _enter(state, "opponent-elf", 2, "Creature — Elf")
    assert not state.stack
    _enter(state, "own-elf", 1, "Creature — Elf Druid")
    assert len(state.stack) == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    _enter(state, "own-elf-2", 1, "Creature — Elf Warrior")
    assert len(state.stack) == 1
    resolve_top_of_stack(state)
    tokens = [state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 1
    assert tokens[0].type_line == "Token Creature — Elf Warrior"
    assert tokens[0].colors == ["G"]
    assert len(state.stack) == 0


def test_first_trigger_stays_used_if_countered_but_resets_next_turn():
    state = _state()
    _enter(state, "first-elf", 1, "Creature — Elf")
    assert len(state.stack) == 1
    state.stack.clear()
    _enter(state, "second-elf", 1, "Creature — Elf")
    assert not state.stack
    state.trigger_once_seen_this_turn.clear()
    _enter(state, "third-elf", 1, "Creature — Elf")
    assert len(state.stack) == 1


def test_new_battlefield_incarnation_gets_a_new_once_per_turn_allowance():
    state = _state()
    _enter(state, "first-elf", 1, "Creature — Elf")
    state.stack.clear()
    source = state.cards["watcher"]
    state.players[1].battlefield.remove(source.id)
    state.players[1].hand.append(source.id)
    source.move_to_zone(Zone.HAND)
    state.players[1].hand.remove(source.id)
    state.players[1].battlefield.append(source.id)
    source.move_to_zone(Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state, source.id)
    _enter(state, "second-elf", 1, "Creature — Elf")
    assert len(state.stack) == 1


def test_group_entry_pattern_is_not_specific_to_elves():
    state = _state()
    watcher = state.cards["watcher"]
    watcher.oracle_text = (
        "Whenever one or more other Zombies you control enter, "
        "create a 2/2 black Zombie creature token. This ability triggers only once each turn."
    )
    watcher.type_line = "Creature — Zombie"
    _enter(state, "zombie", 1, "Creature — Zombie")
    assert len(state.stack) == 1
    resolve_top_of_stack(state)
    token = next(state.cards[cid] for cid in state.players[1].battlefield if state.cards[cid].is_token)
    assert (token.power, token.toughness, token.colors) == (2, 2, ["B"])
    assert token.type_line == "Token Creature — Zombie"


def test_alternate_controller_clause_order_still_triggers():
    state = _state()
    state.cards["watcher"].oracle_text = ORACLE.replace(
        "other Elves you control enter,", "other Elves enter the battlefield under your control,"
    )
    _enter(state, "elf", 1, "Creature — Elf")
    assert len(state.stack) == 1


def test_tribal_activated_bonus_affects_only_current_matching_creatures():
    state = _state()
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    for _ in range(7):
        cid = state.players[1].library.pop()
        state.players[1].battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
    _enter(state, "human", 1, "Creature — Human")
    _enter(state, "first-elf", 1, "Creature — Elf Druid")
    resolve_top_of_stack(state)
    token = next(cid for cid in state.players[1].battlefield if state.cards[cid].is_token)
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, 1)
                if move.get("type") == "activate_ability" and move.get("card_id") == "watcher")
    rules.take_action(state, 1, move, reject_invalid=True)
    assert state.stack[-1].effect_key == "temporary_pt_buff_all"
    resolve_top_of_stack(state)
    assert effective_power(state, "watcher") == 4
    assert effective_power(state, "first-elf") == 3
    assert effective_power(state, token) == 3
    assert has_keyword(state, token, "deathtouch")
    assert effective_power(state, "human") == 1
    assert not has_keyword(state, "human", "deathtouch")
    assert any("Elves you control get +2/+2" in line for line in state.log)
    _enter(state, "later-elf", 1, "Creature — Elf")
    assert effective_power(state, "later-elf") == 1


def test_generic_creature_team_bonus_does_not_become_a_subtype_filter():
    state = _state()
    ability = CardInstance(
        id="team-ability", name="Team Ability", owner=1, controller=1, zone=Zone.STACK,
        oracle_text="Creatures you control get +1/+1 and gain haste until end of turn.",
    )
    key, payload = infer_effect_from_oracle(state, ability, 1)
    assert key == "temporary_pt_buff_all"
    assert payload["controller_only"] is True
    assert "creature_subtypes" not in payload


def test_static_tribal_anthem_uses_the_same_subtype_singularization():
    state = _state()
    source = state.cards["watcher"]
    source.oracle_text = "Other Zombies you control get +1/+1."
    source.type_line = "Creature — Zombie"
    _enter(state, "zombie", 1, "Creature — Zombie")
    _enter(state, "human", 1, "Creature — Human")
    assert effective_power(state, "watcher") == 2
    assert effective_power(state, "zombie") == 2
    assert effective_power(state, "human") == 1
