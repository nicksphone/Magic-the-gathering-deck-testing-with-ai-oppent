from ai.agent import AIAgent
from card_data.fallback_cards import fallback_card_payload
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


def _survey_state():
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck, deck, seed=823)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    payload = fallback_card_payload("Cartographer's Survey")
    assert payload is not None
    survey = CardInstance(
        "survey", payload["name"], 1, 1, Zone.STACK, ["Sorcery"],
        mana_cost=payload["mana_cost"], oracle_text=payload["oracle_text"],
    )
    state.cards[survey.id] = survey
    top = state.players[1].library[-7:]
    creature = state.cards[top[-1]]
    creature.name = "Grizzly Bears"
    creature.types = ["Creature"]
    creature.type_line = "Creature — Bear"
    creature.mana_cost = "{1}{G}"
    return state, survey, top


def test_survey_chooses_only_lands_at_resolution_and_forces_tapped_entry() -> None:
    state, survey, top = _survey_state()
    spec = build_ability_spec(state, survey, 1)
    assert spec.effect.key == "topdeck_put_permanents_battlefield"
    assert spec.effect.payload == {
        "top_n": 7, "max_permanents": 2, "bottom_random": True,
        "bottom_any_order": False, "allowed_type": "Land", "tapped": True,
    }
    state.mechanic_choice_players = {1}
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert state.pending_mechanic_choice["kind"] == "topdeck_put"
    assert set(state.pending_mechanic_choice["options"]) == set(top[:-1])
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "card_ids": top[:2]})
    assert set(top[:2]) <= set(state.players[1].battlefield)
    assert all(state.cards[cid].tapped for cid in top[:2])
    assert set(top[2:]) <= set(state.players[1].library)
    assert len(state.players[1].library) == 51
    assert state.cards[top[-1]].zone == Zone.LIBRARY


def test_survey_ai_uses_the_same_legal_choice_window() -> None:
    state, survey, top = _survey_state()
    state.mechanic_choice_players = {1}
    spec = build_ability_spec(state, survey, 1)
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    legal = RulesEngine().legal_moves(state, 1)
    decision = AIAgent(archetype="Ramp").choose_action(state, legal, 1)
    chosen = decision.action["card_ids"]
    assert len(chosen) == 2
    assert set(chosen) <= set(top[:-1])
    state = checked_action(state, RulesEngine(), 1, decision.action)
    assert set(chosen) <= set(state.players[1].battlefield)
    assert all(state.cards[cid].tapped for cid in chosen)
