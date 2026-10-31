"""Existential paid rescue branches, not strength estimates or TRAIN labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle
import random

import pytest

from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent
RULES = RulesEngine()


def digest(state):
    return hashlib.sha256(pickle.dumps(state, protocol=5)).hexdigest()


def entry(name, count):
    fixtures = SOURCE / 'tests'
    if name == 'Quick Study':
        base = fixtures / 'fixtures/endstep_draw_loss'
        prov = base / 'provenance.json'
        path = base / 'quick-study.json'
        expected = json.loads(prov.read_bytes())[path.name]['sha256']
    else:
        base = fixtures / 'vraska_full/fixtures'
        prov = base / 'PROVENANCE.json'
        path = base / {'Island': 'island-scryfall-raw.json', 'Mountain': 'mountain.json',
                       'Lightning Bolt': 'lightning-bolt.json'}[name]
        expected = json.loads(prov.read_bytes())['fixture_bytes'][path.name]
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected
    raw = json.loads(data)
    assert raw['object'] == 'card' and raw['name'] == name
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'quantity': count, 'card_name': name,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def fixture(seat):
    entries = [entry('Island', 10), entry('Mountain', 2), entry('Quick Study', 1),
               entry('Lightning Bolt', 1)]
    state = MatchFactory.from_decks(entries, entries, seed=9741)
    assert state.winner is None and not state.failed_draw_players
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_players = {1, 2}
    state.replacement_choice_required = True
    state.turn, state.step = 5, Step.END_STEP
    state.active_player, state.priority_player = 3-seat, seat
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.life = 20
        player.lands_played_this_turn = 1

    def place(name, zone):
        player = state.players[seat]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        getattr(player, zone.value).append(cid)
        state.cards[cid].move_to_zone(zone)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
            state.cards[cid].tapped = state.cards[cid].summoning_sick = False
        return cid

    study = place('Quick Study', Zone.HAND)
    islands = [place('Island', Zone.BATTLEFIELD) for _ in range(3)]
    mountain = place('Mountain', Zone.BATTLEFIELD)
    player = state.players[seat]
    retained = [next(cid for cid in player.library if state.cards[cid].name == name)
                for name in ('Lightning Bolt', 'Mountain')]
    for cid in list(player.library):
        if cid not in retained:
            player.library.remove(cid)
            player.graveyard.append(cid)
            state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    assert len(player.library) == 2
    state.players[3-seat].life = 2
    for cid in islands:
        state = checked_action(state, RULES, seat,
            {'type': 'tap_land_for_mana', 'card_id': cid, 'color': 'U'})
    assert all(state.cards[cid].tapped for cid in islands)
    assert not state.cards[mountain].tapped
    assert state.players[seat].mana_pool.get('U') == 3
    assert sum(state.players[seat].mana_pool.values()) == 3
    return state, study, islands, mountain


def settle(state, trace):
    for _ in range(12):
        if state.winner is not None or not state.stack:
            return state
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order)
        action = {'type': 'pass_priority'}
        trace.append({'actor': state.priority_player, 'action': action})
        state = checked_action(state, RULES, state.priority_player, action)
    raise AssertionError('Native prefix settlement bound')


@pytest.mark.parametrize('seat', [1, 2])
def test_new_private_action_can_rescue_before_compulsory_draw(seat, tmp_path):
    state, study, islands, mountain = fixture(seat)
    before, rng, local = digest(state), random.getstate(), state.rng.getstate()
    moves = RULES.legal_moves(state, seat)
    original_moves = deepcopy(moves)
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == study for move in moves)
    view, _ = decision_view(state, seat, moves)
    assert all(is_unknown(view.cards[cid]) for cid in state.players[seat].library)
    action = complete_action({'type': 'cast_spell', 'card_id': study, 'cost_choice': {'id': 'base'}})
    view_before = digest(view)
    flag = AIAgent('master', 'Control')._draw_cast_loses(view, action, seat)
    assert digest(view) == view_before
    assert digest(state) == before and moves == original_moves
    assert random.getstate() == rng and state.rng.getstate() == local

    trace = [{'actor': seat, 'action': action}]
    paid = checked_action(state, RULES, seat, action)
    assert paid.stack[-1].effect_key == 'draw_cards'
    assert paid.stack[-1].payload['amount'] == 2 and paid.stack[-1].payload['mana_spent'] == 3
    assert sum(paid.players[seat].mana_pool.values()) == 0 and not paid.cards[mountain].tapped
    resolved = settle(paid, trace)
    assert resolved.winner is None and not resolved.players[seat].library
    assert {resolved.cards[cid].name for cid in resolved.players[seat].hand} == {'Lightning Bolt', 'Mountain'}
    while resolved.priority_player != seat:
        assert resolved.priority_player == 3-seat and resolved.step == Step.END_STEP
        trace.append({'actor': resolved.priority_player, 'action': {'type': 'pass_priority'}})
        resolved = checked_action(resolved, RULES, resolved.priority_player, {'type': 'pass_priority'})
    offers = RULES.legal_moves(resolved, seat)
    bolt = next(cid for cid in resolved.players[seat].hand if resolved.cards[cid].name == 'Lightning Bolt')
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == bolt for move in offers)
    bolt_action = complete_action({'type': 'cast_spell', 'card_id': bolt,
        'targets': {'target_player': 3-seat}, 'cost_choice': {'id': 'base'}})
    trace.append({'actor': seat, 'action': bolt_action})
    bolt_paid = checked_action(resolved, RULES, seat, bolt_action)
    assert bolt_paid.stack[-1].payload['mana_spent'] == 1 and bolt_paid.cards[mountain].tapped
    won = settle(bolt_paid, trace)
    assert won.winner == seat and won.players[3-seat].life <= 0
    assert won.step == Step.END_STEP and won.turn == state.turn
    assert not won.failed_draw_players and not won.players[seat].library
    assert digest(state) == before and state.rng.getstate() == local and random.getstate() == rng
    proof = dict(seat=seat, guard_reported_losing=flag, root_sha256=before,
        view_sha256=view_before, actual_native_winner=won.winner,
        actual_opponent_life=won.players[3-seat].life, actual_turn=won.turn,
        actual_step=won.step.value, own_library_empty=True, trace=trace,
        mana_before=dict(state.players[seat].mana_pool), mountain_untapped_before=True,
        quick_study_mana_spent=3, bolt_mana_spent=1, root_moves_rng_pure=True,
        native_log=list(won.log), scope='existential legal rescue, not a strength claim or TRAIN label')
    (tmp_path / f'seat-{seat}.PROOF.json').write_text(json.dumps(proof, indent=2) + '\n')
    assert flag is not True, 'Hard-loss filter crosses a new opaque private-action frontier despite a paid native win'
