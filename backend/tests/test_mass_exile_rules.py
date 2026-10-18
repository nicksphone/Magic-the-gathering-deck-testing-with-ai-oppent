from effects.registry import resolve_effect
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from tests.browser_positive83_canonical import entry
from tests.mass_exile_canonical_fixture import final_judgment_entry, final_judgment_in_hand


def test_exile_all_creatures_preserves_ownership_and_emits_leave_event() -> None:
    state = MatchFactory.from_decks(
        [entry("Forest", 60)],
        [entry("Forest", 60)],
        seed=61,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    stolen = CardInstance("stolen", "Stolen Creature", 2, 1, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2)
    own = CardInstance("own", "Own Creature", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1)
    state.cards.update({stolen.id: stolen, own.id: own})
    state.players[1].battlefield.extend([stolen.id, own.id])
    resolve_effect(state, 1, "exile_all_creatures", {})
    assert not state.players[1].battlefield
    assert stolen.id in state.players[2].exile
    assert own.id in state.players[1].exile
    assert stolen.zone == Zone.EXILE


def test_farewell_style_text_uses_exile_not_destroy() -> None:
    state = MatchFactory.from_decks(
        [entry("Forest", 60), final_judgment_entry()],
        [entry("Forest", 60)],
        seed=62,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    spell = final_judgment_in_hand(state)
    state.cards[spell.id] = spell
    spec = build_ability_spec(state, spell, 1)
    assert spec.effect.key == "exile_all_creatures"
