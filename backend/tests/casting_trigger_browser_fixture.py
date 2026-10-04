"""Canonical bounded positions; loopback-only disposable browser fixture API."""
from pathlib import Path

if (Path(__file__).resolve().parents[2] / '.git').exists():
    raise RuntimeError('Use an isolated source copy, never a live worktree')

from tests.browser_fixture_server import app, ACTIVE_MATCHES, MatchController, get_match, _persist_active_match
from tests.regression_agent_wave2.support import position, add, RULES
from game_state.state import Zone
from ai.agent import AIAgent
from persistence.db import engine
from persistence.repository import Repository
from sqlmodel import Session


@app.post('/fixture/casting-trigger')
def casting_fixture(seat: int = 1):
    if seat not in {1, 2}:
        raise ValueError('invalid fixture seat')
    state = position(seat)
    add(state, 'Incremental Growth', seat)
    for _ in range(3):
        add(state, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool.update(G=2, U=3)
    match = MatchController(
        state=state, rules=RULES, controllers={1: 'human', 2: 'human'},
        ai={1: AIAgent(), 2: AIAgent()}, mode='human_vs_human',
        deck_ids=(None, None), mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False, best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    with Session(engine) as session:
        _persist_active_match(Repository(session), match)
    return get_match(state.id)
