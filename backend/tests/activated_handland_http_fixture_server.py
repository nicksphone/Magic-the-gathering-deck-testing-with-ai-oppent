"""Owned source-only token-authenticated fixtures; actual actions use public routes."""
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import Session
from tests import optional_land_choice_http_fixture_server as base
from tests.test_activated_handland_instruction_audit import setup, FAMILIES

app = base.app


@app.post('/fixture/activated-handland')
def fixture(request: Request, family: str, seat: int, sick: bool = False):
    base.authorize(request)
    if family not in FAMILIES or seat not in (1, 2):
        raise HTTPException(422, 'Declared canonical family and seat required')
    state, source, lands, enemy = setup(family, seat, sick=sick)
    state.id = str(uuid4())
    state.log.append(base.LABEL)
    controller = base.main.MatchController(state=state, rules=base.RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: base.AIAgent(), 2: base.AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    base.main.ACTIVE_MATCHES[state.id] = controller
    with Session(base.engine) as session:
        base.main._persist_active_match(base.Repository(session), controller)
    return {'id': state.id, 'source_id': source.id,
            'land_ids': [land.id for land in lands], 'enemy_id': enemy.id}


@app.post('/fixture/paid-activated-handland')
def paid_cast_fixture(request: Request, family: str, seat: int):
    base.authorize(request)
    if family not in FAMILIES or seat not in (1, 2):
        raise HTTPException(422, 'Declared canonical family and seat required')
    from tests.ai_knowledge_consumer_fixture import position, take
    from tests.test_linked_damage_targets import raw_card
    from tests.test_activated_handland_instruction_audit import ROWS
    from game_state.state import Zone
    state = position('Ramp', 'Tempo', seat)
    state.mechanic_choice_players = {1, 2}
    source = raw_card(state, ROWS[family], seat, Zone.HAND)
    take(state, 'Forest', seat, Zone.BATTLEFIELD)
    take(state, 'Tropical Island', seat, Zone.BATTLEFIELD)
    land = take(state, 'Forest', seat, Zone.HAND)
    state.id = str(uuid4())
    state.log.append(base.LABEL)
    controller = base.main.MatchController(state=state, rules=base.RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={1: base.AIAgent(), 2: base.AIAgent()},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    base.main.ACTIVE_MATCHES[state.id] = controller
    with Session(base.engine) as session:
        base.main._persist_active_match(base.Repository(session), controller)
    return {'id': state.id, 'source_id': source.id, 'land_id': land.id}
