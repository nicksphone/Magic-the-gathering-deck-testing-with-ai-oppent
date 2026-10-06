"""Owned additional explicit empty-top position; no transformation helper routes."""
from tests import human_transform_fixture_server as base
from fastapi import HTTPException, Request
from sqlmodel import Session
from game_state.state import Zone
from persistence.db import engine
from persistence.repository import Repository

app = base.app


@app.get('/fixture/delver-repair/status')
def status(request: Request):
    return base.status(request)


@app.post('/fixture/delver-repair')
def fixture(request: Request, seat: int, scenario: str, deck_id: int):
    if scenario not in {'cathar-natural', 'delver-reveal', 'delver-decline',
                         'delver-ineligible', 'delver-empty', 'delver-stale'}:
        raise HTTPException(422, 'Declared canonical repair scenario required')
    result = base.fixture(request, seat, 'delver-reveal' if scenario in {'delver-empty', 'delver-stale'} else scenario, deck_id)
    controller = base.owned(result['match']['id'])
    # The frozen audit rebuilt library lists but retained opening-hand zones.
    # Correct this explicit setup invariant, without changing any card facts.
    for player in controller.state.players.values():
        for cid in player.library:
            if controller.state.cards[cid].zone != Zone.LIBRARY:
                controller.state.cards[cid].move_to_zone(Zone.LIBRARY)
    if scenario == 'delver-empty':
        controller = base.owned(result['match']['id'])
        player = controller.state.players[seat]
        for cid in list(player.library):
            controller.state.cards[cid].move_to_zone(Zone.GRAVEYARD)
            player.graveyard.append(cid)
        player.library.clear()
        with Session(engine) as session:
            base.main._persist_active_match(Repository(session), controller)
        result.update(match=base.main.get_match(controller.state.id), top_id=None,
                      additional_setup='Canonical cards moved to own graveyard for an explicit empty library; no historical claim.')
    with Session(engine) as session:
        base.main._persist_active_match(Repository(session), controller)
    return result


@app.get('/fixture/delver-repair/{identifier}/audit')
def audit(identifier: str, request: Request):
    return base.audit(identifier, request)


@app.get('/fixture/delver-repair/actions')
def actions(request: Request, match_id: str):
    return base.actions(request, match_id)
