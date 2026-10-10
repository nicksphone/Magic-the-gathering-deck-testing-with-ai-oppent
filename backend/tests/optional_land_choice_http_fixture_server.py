"""Owned loopback bridge; paid and handler-only slices remain distinct."""
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import Session
from effects.handlers import put_land_from_hand
from tests.cold_restart_http_fixture import (
    app, authorize, main, engine, Repository, AIAgent, RulesEngine,
    LAND_LABEL as LABEL,
)
from tests.test_optional_land_from_hand_audit import setup


@app.post('/fixture/private-choice')
def fixture(request: Request, family: str, seat: int, slice_only: bool = False):
    authorize(request)
    if family not in {'Growth Spiral', 'Arboreal Grazer'} or seat not in (1, 2):
        raise HTTPException(422, 'Declared canonical family and seat required')
    state, source, land, drawn = setup(family, seat)
    state.id = str(uuid4())
    state.log.append(LABEL)
    if slice_only:
        # Lower-level handler fixture ONLY; never claim this executed a card.
        put_land_from_hand(state, seat, {'optional': True, 'tapped': family == 'Arboreal Grazer'})
        state.log.append('Handler-slice setup; spell compiler is not exercised.')
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {'id': state.id, 'source_id': source.id, 'land_id': land.id,
            'drawn_id': drawn, 'slice_only': slice_only}

