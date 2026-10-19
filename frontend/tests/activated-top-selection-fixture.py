"""Disposable loopback fixture setup; all tested actions use the real HTTP API."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ['MTG_OFFICER_RUNTIME']).resolve()
if (ROOT / '.git').exists():
    raise RuntimeError('Requires the isolated Officer source copy')
if RUNTIME.parent != Path(tempfile.gettempdir()).resolve() or not RUNTIME.name.startswith('mtg-officer-http-'):
    raise RuntimeError('Requires a new, local Officer test runtime')
RUNTIME.mkdir(parents=True, exist_ok=True)
DATABASE = RUNTIME / 'officer-test.sqlite'
os.environ['MTG_DATABASE_PATH'] = str(DATABASE)
sys.path.insert(0, str(ROOT / 'backend'))
BOOTSTRAP_DATABASES = frozenset()


def guard(event, args):
    if event == 'sqlite3.connect' and os.fspath(args[0]) not in (
            {str(DATABASE), DATABASE.as_uri() + '?mode=ro'} | BOOTSTRAP_DATABASES):
        raise RuntimeError('Attempt to access a foreign database')
    if event == 'socket.connect' and isinstance(args[1], tuple) and args[1][0] not in {'127.0.0.1', '::1', 'localhost'}:
        raise RuntimeError('Non-loopback network access is forbidden')


sys.addaudithook(guard)
from sqlmodel import Session
from persistence import db

from card_data import placeholders, sync

placeholders.CACHE_DIR = sync.CACHE_DIR = RUNTIME / 'card-images'
import main
from fastapi import HTTPException
from ai.agent import AIAgent
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_activated_top_selection import position

NATIVE_INITIALIZE_CAPACITY = main.initialize_resource_capacity


def initialize_owned_capacity(owner, backup):
    """Authorize only the native owner's exact bootstrap backup, for its call lifetime."""
    global BOOTSTRAP_DATABASES
    owner.require(ready=False)
    expected = DATABASE.with_name(DATABASE.name + '.before-capacity-' + owner.epoch + '.db')
    if owner.engine is not db.engine or owner.path != DATABASE or backup != expected:
        raise RuntimeError('Foreign capacity bootstrap')
    BOOTSTRAP_DATABASES = frozenset({str(backup), backup.as_uri() + '?mode=ro'})
    try:
        return NATIVE_INITIALIZE_CAPACITY(owner, backup)
    finally:
        BOOTSTRAP_DATABASES = frozenset()


main.initialize_resource_capacity = initialize_owned_capacity
app = main.app


@app.post('/fixture/officer')
def officer(seat: int = 1, eligible: bool = True, ai: bool = False):
    if seat not in (1, 2):
        raise HTTPException(422, 'Invalid seat')
    names = ('savannah-lions', 'militia-bugler', 'serra-angel', 'opt') if eligible else ('opt', 'serra-angel', 'forest', 'opt')
    state, source, outside, top = position(seat, names, prefix=False)
    state.id = str(uuid.uuid4())
    deck = [{'quantity': 60, 'card_name': 'Forest'}]
    controller = main.MatchController(
        state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={1: AIAgent(difficulty='strong'), 2: AIAgent(difficulty='strong')},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    if ai:
        # Setup an authentic unresolved choice, then switch only seat ownership.
        controller.rules.take_action(state, seat, {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0}, reject_invalid=True)
        for _ in range(2):
            controller.rules.take_action(state, state.priority_player, {'type': 'pass_priority'}, reject_invalid=True)
        controller.controllers[seat] = 'ai'
        controller.mode = 'player_vs_ai'
    with Session(db.engine) as session:
        main._persist_active_match(Repository(session), controller)
    return {'match': main.get_match(state.id), 'seat': seat, 'eligible': eligible,
            'source_id': source.id, 'top_ids': top, 'outside_ids': outside,
            'labels': {cid: state.cards[cid].name for cid in top}}


@app.get('/fixture/officer-status/{match_id}')
def status(match_id: str):
    controller = main.ACTIVE_MATCHES[match_id]
    state = controller.state
    return {'libraries': {pid: p.library for pid, p in state.players.items()},
            'observations': state.card_observations, 'draws': state.draws_this_turn,
            'failed_draws': list(state.failed_draw_players), 'trigger_staging': state.trigger_staging,
            'pending': state.pending_mechanic_choice,
            'database': str(DATABASE), 'pid': os.getpid()}


if __name__ == '__main__':
    import uvicorn
    # Require native ownership/bootstrap/admission and fenced drain/close on exit.
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('MTG_OFFICER_PORT', '10237')), lifespan='on')
