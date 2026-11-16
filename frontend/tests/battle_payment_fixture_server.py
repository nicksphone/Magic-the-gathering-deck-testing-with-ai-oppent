"""Disposable UI wrapper; existing fixture servers and production routes unchanged."""
from typing import Literal

from fastapi import HTTPException
from sqlmodel import Session

import main
from persistence.db import engine
from persistence.repository import Repository
from tests.battle_payment_browser_fixture import midgame, unsupported_midgame
from tests.battle_browser_routing_fixture import routing_midgame
from tests.ui_v2_fixture_server import app, publish


@app.post("/fixture/battle-payment")
def battle_payment(seat: int = 1,
                   mode: Literal["human_vs_human", "player_vs_ai"] = "human_vs_human"):
    if seat not in (1, 2):
        raise HTTPException(422, "Expected seat one or two")
    state, ids = midgame(seat)
    return publish_midgame(state, ids, seat, mode)


@app.post("/fixture/battle-payment/unsupported")
def unsupported(seat: int = 1):
    if seat not in (1, 2):
        raise HTTPException(422, "Expected seat one or two")
    state, ids = unsupported_midgame(seat)
    return publish_midgame(state, ids, seat, "human_vs_human")


@app.post("/fixture/battle-payment/routing")
def routing(seat: int = 1, case: Literal["partial", "player", "blocked"] = "partial"):
    if seat not in (1, 2):
        raise HTTPException(422, "Expected seat one or two")
    state, ids = routing_midgame(seat, blocked=case == "blocked")
    return publish_midgame(state, ids, seat, "human_vs_human")


def publish_midgame(state, ids, seat, mode):
    publish(state, state.starting_decks[seat], mainboards=state.starting_decks)
    controller = main.ACTIVE_MATCHES[state.id]
    controller.mode = mode
    controller.controllers = {pid: "human" if mode == "human_vs_human" or pid == seat else "ai"
                              for pid in (1, 2)}
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {"match": main.get_match(state.id), **ids,
            "scope": "declared canonical midgame"}
