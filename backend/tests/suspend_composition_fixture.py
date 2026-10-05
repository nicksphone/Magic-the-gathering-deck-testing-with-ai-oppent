"""Owned real-HTTP composition fixture, guarded before importing production main."""
from copy import deepcopy

# Reuse the qualified runner's root/token/SQLite admission guard unchanged.
from tests.suspend_fixture_server import (
    app, main, ROOT, authorize, persist, audit, LABEL,
)
from fastapi import HTTPException, Request
from sqlmodel import Session

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.suspend import instruction
from tests.test_suspend_lifecycle import setup, CARDS, add

CLAIM = 'Explicit canonical Suspend composition fixture; no historical-game claim.'


def owned(match_id, cid):
    match = main.ACTIVE_MATCHES.get(match_id)
    if match is None or CLAIM not in match.state.log:
        raise HTTPException(404, 'Unknown owned composition fixture')
    card = match.state.cards.get(cid)
    if card is None or instruction(card) is None:
        raise HTTPException(422, 'Unknown supported fixture source')
    return match, card


@app.post('/fixture/suspend-composition')
def fixture(request: Request, seat: int, scenario: str):
    authorize(request)
    names = {'burn': 'Rift Bolt', 'creature': 'Errant Ephemeron', 'draw': 'Ancestral Vision',
             'decline': 'Rift Bolt', 'unpayable': 'Rift Bolt'}
    if seat not in (1, 2) or scenario not in names:
        raise HTTPException(422, 'Unknown bounded canonical fixture')
    state, cid = setup(seat, names[scenario])
    state.turn = 1
    state.players[seat].mana_pool = {'R': 1} if names[scenario] == 'Rift Bolt' else {'U': 1, 'C': 1}
    if scenario == 'unpayable': state.players[seat].mana_pool.clear()
    if scenario == 'decline':
        for owner in (1, 2): add(state, 'Ivory Mask', owner, cards=CARDS)
    # A real canonical private opposing hand tests the AI boundary; never a policy input.
    add(state, 'Rift Bolt', 3-seat, Zone.HAND, cards=CARDS)
    state.log += [LABEL, CLAIM]
    deck = [{'card_name': 'Swamp', 'quantity': 60}]
    styles = {seat: 'Midrange', 3-seat: 'Aggro'}
    match = main.MatchController(
        state=state, rules=RulesEngine(), controllers={seat: 'ai', 3-seat: 'human'},
        ai={pid: AIAgent('strong', styles[pid], styles[3-pid]) for pid in (1, 2)},
        mode='player_vs_ai', deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3,
    )
    main.ACTIVE_MATCHES[state.id] = match
    persist(match)
    return {'id': state.id, 'source_id': cid, 'count': instruction(state.cards[cid])[0],
            'claim': CLAIM, 'runtime': str(ROOT)}


@app.get('/fixture/suspend-composition/{match_id}/audit')
def read_audit(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, card = owned(match_id, source_id)
    return {**audit(match, card), 'controllers': match.controllers,
            'ai_config': {pid: {'difficulty': agent.difficulty, 'archetype': agent.archetype,
                               'opponent_archetype': agent.opponent_archetype}
                          for pid, agent in match.ai.items()}}


@app.post('/fixture/suspend-composition/{match_id}/upkeep')
def upkeep(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, card = owned(match_id, source_id)
    with match.mutation_lock:
        state = match.state
        if (card.zone != Zone.EXILE or not card.counters.get('time') or state.stack
                or state.pending_mechanic_choice or state.pending_trigger_order
                or state.pending_replacement_choice):
            raise HTTPException(422, 'Explicit upkeep requires idle suspended source')
        state.active_player = state.priority_player = card.owner
        state.step = Step.UPKEEP
        state.passed_priority.clear()
        state.log.append('Explicit owner-upkeep fixture transition; intervening turns not played.')
        match.rules._apply_step_start_actions(state)
        match.revision += 1
        persist(match)
        return audit(match, card)


@app.post('/fixture/suspend-composition/{match_id}/restore')
def restore(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, card = owned(match_id, source_id)
    with match.mutation_lock:
        before = audit(match, card)['snapshot_sha256']
        persist(match)
        main.ACTIVE_MATCHES.pop(match_id)
        with Session(engine) as session:
            main._restore_active_matches(Repository(session), match_id)
        result = read_audit(match_id, source_id, request)
        assert result['snapshot_sha256'] == before
        return result


@app.get('/fixture/suspend-composition/{match_id}/private-probe')
def private_probe(match_id: str, source_id: str, request: Request):
    authorize(request)
    match, card = owned(match_id, source_id)
    with match.mutation_lock:
        state = match.state
        pid = card.owner
        before = serialize_match_snapshot(state)
        legal = match.rules.legal_moves(deepcopy(state), pid)
        view, offered = decision_view(state, pid, legal)
        hidden = [cid for p in state.players.values() for cid in p.library]
        hidden += state.players[3-pid].hand
        assert hidden and all(is_unknown(view.cards[cid]) for cid in hidden)
        action = complete_action(match.ai[pid].choose_action(state, legal, pid).action)
        checked_action(state, match.rules, pid, action)
        altered = deepcopy(state)
        for player in altered.players.values(): player.library.reverse()
        assert complete_action(AIAgent('strong', 'Midrange', 'Aggro').choose_action(
            altered, match.rules.legal_moves(altered, pid), pid).action) == action
        assert serialize_match_snapshot(state) == before
        assert offered == legal
        return {'action': action, 'opaque_cards': len(hidden), 'root_immutable': True,
                'hidden_order_invariant': True,
                'offered_suspend': any(move.get('type') == 'suspend'
                                       and move.get('card_id') == card.id for move in legal)}
