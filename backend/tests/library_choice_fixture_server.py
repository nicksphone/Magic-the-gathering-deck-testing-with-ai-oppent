"""NEW route on frozen guarded test-only bridge; no production route edits."""
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import Session

from tests.cold_restart_http_fixture import (
    app, authorize, main, engine, Repository, LABEL, AIAgent, RulesEngine,
)
from tests.test_library_choice_intent_audit import CARDS, ORDER_CARDS, position


@app.post('/fixture/library-choice')
def library_fixture(request: Request, name: str, seat: int, order: bool = False):
    authorize(request)
    if name not in CARDS or seat not in (1, 2) or (order and name not in ORDER_CARDS):
        raise HTTPException(422, 'Declared canonical card, phase and seat required')
    state, source, outside, foreign = position(name, seat, order)
    state.id = str(uuid4())
    state.log.append(LABEL)
    controller = main.MatchController(state=state, rules=RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: AIAgent(), 2: AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {'id': state.id, 'source_id': source, 'outside_ids': outside, 'foreign_hand_id': foreign}
