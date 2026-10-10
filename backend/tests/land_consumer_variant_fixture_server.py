"""New canonical land fixtures on unchanged source-only loopback guard."""
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import Session

from tests.cold_restart_http_fixture import (
    app, authorize, main, engine, Repository, LABEL, AIAgent, RulesEngine,
)
from tests.land_consumer_variant_support import VARIANTS, setup


@app.post('/fixture/land-consumer')
def fixture(request: Request, variant: str, seat: int):
    authorize(request)
    if variant not in VARIANTS or seat not in (1, 2):
        raise HTTPException(422, 'Declared canonical family and seat required')
    env, action, _, ids = setup(variant, seat)
    state = env._state
    state.id = str(uuid4()); state.log.append(LABEL)
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {'id': state.id, 'chosen_action': action, **ids}
