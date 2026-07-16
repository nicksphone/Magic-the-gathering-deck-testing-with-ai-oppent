from effects.handlers import deal_damage
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine import combat


def _state() -> object:
    return MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=29)


def test_target_player_can_have_damage_prevention_override() -> None:
    state = _state()
    lock = CardInstance(
        id="player-lock", name="Player Lock", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Enchantment"], oracle_text="Damage that would be dealt to you can't be prevented.",
    )
    state.cards[lock.id] = lock
    state.players[1].battlefield.append(lock.id)
    state.players[1].prevent_damage_shield = 5
    before = state.players[1].life
    deal_damage(state, 2, {"target_player": 1, "amount": 3})
    assert state.players[1].life == before - 3


def test_target_permanent_can_have_damage_prevention_override() -> None:
    state = _state()
    lock = CardInstance(
        id="permanent-lock", name="Permanent Lock", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Enchantment"], oracle_text="Damage that would be dealt to permanents you control can't be prevented.",
    )
    target = CardInstance(
        id="target", name="Target Creature", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Creature"], toughness=4,
    )
    state.cards[lock.id] = lock
    state.cards[target.id] = target
    state.players[1].battlefield.extend([lock.id, target.id])
    target.counters["__prevent_damage_shield"] = 5
    deal_damage(state, 2, {"target_card_id": target.id, "amount": 3})
    assert target.counters.get("__damage_marked") == 3


def test_combat_only_override_applies_to_combat_damage() -> None:
    state = _state()
    lock = CardInstance(
        id="combat-lock", name="Combat Lock", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Enchantment"], oracle_text="Combat damage can't be prevented.",
    )
    attacker = CardInstance(
        id="attacker", name="Attacker", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Creature"], power=2, toughness=2,
    )
    state.cards[lock.id] = lock
    state.cards[attacker.id] = attacker
    state.players[1].battlefield.extend([lock.id, attacker.id])
    state.players[2].prevent_damage_shield = 5
    before = state.players[2].life
    combat._deal_unblocked_damage(state, "player:2", 2, attacker.id)
    assert state.players[2].life == before - 2


def test_named_source_override_does_not_unlock_other_sources() -> None:
    state = _state()
    source = CardInstance(
        id="source", name="Source Creature", owner=1, controller=1, zone=Zone.BATTLEFIELD,
        types=["Creature"], oracle_text="Damage dealt by this creature can't be prevented.",
    )
    other = CardInstance(id="other", name="Other Source", owner=1, controller=1, zone=Zone.BATTLEFIELD, types=["Creature"])
    state.cards[source.id] = source
    state.cards[other.id] = other
    state.players[1].battlefield.extend([source.id, other.id])
    state.players[2].prevent_damage_shield = 5
    before = state.players[2].life
    deal_damage(state, 1, {"target_player": 2, "amount": 2, "__source_card_id": source.id})
    assert state.players[2].life == before - 2
    deal_damage(state, 1, {"target_player": 2, "amount": 2, "__source_card_id": other.id})
    assert state.players[2].life == before - 2
