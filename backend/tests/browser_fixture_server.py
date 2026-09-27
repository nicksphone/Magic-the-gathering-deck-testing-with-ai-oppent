"""Loopback-only browser fixtures; never mount these routes in production."""
from pathlib import Path
if (Path(__file__).resolve().parents[2] / ".git").exists():
    raise RuntimeError("Run browser fixtures only from an isolated source copy, not the live Git checkout")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from main import ACTIVE_MATCHES, ActionRequest, MatchController, get_match, get_legal_moves, take_action
from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from persistence.db import init_db

init_db()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:15173"], allow_methods=["*"], allow_headers=["*"])


@app.post("/fixture")
def fixture():
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=15)
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
    ACTIVE_MATCHES.clear()
    ACTIVE_MATCHES[state.id] = MatchController(state=state, rules=RulesEngine(), controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    return get_match(state.id)


@app.get("/matches/{match_id}")
def state_view(match_id: str):
    return get_match(match_id)


@app.get("/matches/{match_id}/legal-moves")
def moves(match_id: str, player_id: int | None = None):
    return get_legal_moves(match_id, player_id)


@app.post("/matches/{match_id}/action")
def action(match_id: str, payload: ActionRequest):
    return take_action(match_id, payload, repo=None)
