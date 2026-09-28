"""Loopback-only browser fixtures; never mount these routes in production."""
from pathlib import Path
if (Path(__file__).resolve().parents[2] / ".git").exists():
    raise RuntimeError("Run browser fixtures only from an isolated source copy, not the live Git checkout")
from main import app, ACTIVE_MATCHES, MatchController, get_match, _persist_active_match
from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from persistence.db import init_db, engine
from persistence.repository import Repository
from sqlmodel import Session

init_db()

@app.post("/fixture")
def fixture(pregame: bool = False, modal: bool = False, modal_mana: int = 3, face_kind: str = ""):
    if face_kind == "iteration":
        from effects.registry import resolve_effect
        deck = [{"quantity": 60, "card_name": "Forest", "type_line": "Basic Land - Forest"}]
        state = MatchFactory.from_decks(deck, deck, seed=32)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.replacement_choice_required = True
        state.replacement_choice_players = {2}
        for cid, name, cost, types in zip(state.players[2].library[-3:],
            ["Lightning Bolt", "Counterspell", "Llanowar Elves"],
            ["{R}", "{U}{U}", "{G}"], [["Instant"], ["Instant"], ["Creature"]]):
            card = state.cards[cid]
            card.name, card.mana_cost, card.types = name, cost, types
        resolve_effect(state, 2, "look_top_choose", {"top_n": 3})
        return publish(state, deck)
    if face_kind == "bo3":
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=31)
        state.winner = 1
        state.score = {1: 1, 2: 0}
        publish(state, deck)
        match = ACTIVE_MATCHES[state.id]
        match.current_game_recorded = True
        match.root_seed = 31
        with Session(engine) as session:
            _persist_active_match(Repository(session), match)
        return get_match(state.id)
    if face_kind in {"trigger", "cast_trigger"}:
        import json
        rows = json.loads((Path(__file__).parent / "fixtures/permanent_spell_context.json").read_text())
        deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
        state = MatchFactory.from_decks(deck, deck, seed=17)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {2}
        state.players[2].mana_pool.update({"G": 3, "C": 12 if face_kind == "cast_trigger" else 3})

        for cid, name, owner, zone in (
            ("cast-source" if face_kind == "cast_trigger" else "sage",
             "Ulamog, the Infinite Gyre" if face_kind == "cast_trigger" else "Reclamation Sage", 2, Zone.HAND),
            ("ring", "Sol Ring", 2, Zone.BATTLEFIELD),
            ("copter", "Smuggler's Copter", 1, Zone.BATTLEFIELD),
        ):
            row = rows[name]
            card = CardInstance(
                id=cid, name=name, owner=owner, controller=owner, zone=zone,
                types=row["type_line"].split(" — ")[0].split(),
                type_line=row["type_line"], oracle_text=row["oracle_text"],
                mana_cost=row["mana_cost"],
                power=int(row["power"]) if row["power"] else None,
                toughness=int(row["toughness"]) if row["toughness"] else None,
            )
            state.cards[cid] = card
            getattr(state.players[owner], zone.value).append(cid)
        return publish(state, deck)
    if modal or face_kind:
        import json
        name = {"land": "Bala Ged Recovery // Bala Ged Sanctuary", "adventure": "Bonecrusher Giant // Stomp"}.get(face_kind, "Wandering Archaic // Explore the Vastlands")
        raw = json.loads((Path(__file__).parent / "fixtures/modal_spell_faces.json").read_text())[name]
        deck = [{"quantity": 60, "card_name": raw["name"], **raw["card_faces"][0], "layout": raw["layout"], "card_faces": raw["card_faces"]}]
        state = MatchFactory.from_decks(deck, deck, seed=9)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.active_player = state.priority_player = 2
        state.step = Step.PRECOMBAT_MAIN
        state.players[2].mana_pool["C"] = modal_mana
        if face_kind == "adventure":
            state.players[2].mana_pool["R"] = 4
        return publish(state, deck)
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=15)
    if pregame:
        state.kept_hands = {1}
        state.priority_player = 2
        state.mulligan_count[2] = 1
        return publish(state, deck)
    state.pregame_pending = False
    state.active_player = state.priority_player = 2
    state.step = Step.PRECOMBAT_MAIN
    state.players[2].hand = []
    state.players[2].mana_pool.update({"G": 3, "R": 3})

    def add(cid, name, zone, types, cost="", text="", power=None, toughness=None, type_line=""):
        card = CardInstance(id=cid, name=name, owner=2, controller=2, zone=zone, types=types, mana_cost=cost, oracle_text=text, power=power, toughness=toughness, type_line=type_line.replace(" - ", " \u2014 "), summoning_sick=False)
        state.cards[cid] = card
        getattr(state.players[2], zone.value).append(cid)
        return card

    add("forest", "Forest", Zone.HAND, ["Land"], type_line="Basic Land - Forest")
    add("pyromancer", "Prodigal Pyromancer", Zone.BATTLEFIELD, ["Creature"], "{2}{R}", "{T}: Prodigal Pyromancer deals 1 damage to any target.", 1, 1)
    add("bear", "Grizzly Bears", Zone.BATTLEFIELD, ["Creature"], "{1}{G}", power=2, toughness=2)
    add("copter", "Smuggler's Copter", Zone.BATTLEFIELD, ["Artifact"], "{2}", "Flying\nCrew 1", 3, 3, "Artifact - Vehicle")
    add("shock", "Shock", Zone.EXILE, ["Instant"], "{R}", "Shock deals 2 damage to any target.")
    state.players[2].exile_play_until["shock"] = state.turn
    walker = add("walker", "Realmwalker", Zone.BATTLEFIELD, ["Creature"], "{2}{G}", "You may cast creature spells of the chosen type from the top of your library.", 2, 3)
    walker.chosen_creature_type = "Elf"
    add("elf", "Llanowar Elves", Zone.LIBRARY, ["Creature"], "{G}", "{T}: Add {G}.", 1, 1, "Creature - Elf Druid")
    return publish(state, deck)


def publish(state, deck):
    ACTIVE_MATCHES.clear()
    ACTIVE_MATCHES[state.id] = MatchController(state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    with Session(engine) as session:
        _persist_active_match(Repository(session), ACTIVE_MATCHES[state.id])
    return get_match(state.id)
