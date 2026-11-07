"""Canonical declared boards, not full games or fitted-model qualification.

The learned-route test doubles only shortlist/Q; payment and terminal branches
use the native consumer. No winner, event, StackItem or printed text is injected.
"""
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
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.draw_canonical_sidecar import deck_entry
from tests.test_forge_negative_life_diagnostic import canonical_entry
from tests.test_learned_tactical_guard import _route
from training.environment import decode_action, encode_action


RULES = RulesEngine()
FIXTURES = Path(__file__).parent / 'fixtures/endstep_draw_loss'


def raw_entry(filename, quantity=1):
    provenance = json.loads((FIXTURES / 'provenance.json').read_bytes())
    data = (FIXTURES / filename).read_bytes()
    assert hashlib.sha256(data).hexdigest() == provenance[filename]['sha256']
    row = json.loads(data)
    assert row['object'] == 'card'
    return {**row, 'quantity': quantity, 'card_name': row['name']}


def position(seat, remaining=1, sources=(), previous=0, spell='Quick Study', library_names=()):
    entries = [deck_entry('Island', 10), raw_entry('grizzly-bears.json')]
    raw_spells = {'Quick Study': 'quick-study.json', 'Opt': 'opt.json',
                  'Consider': 'consider.json', 'Brainstorm': 'brainstorm.json',
                  'Cloudblazer': 'cloudblazer.json'}
    entries.append(raw_entry(raw_spells[spell]) if spell in raw_spells else deck_entry(spell, 1))
    if spell == 'Cloudblazer':
        from tests.mana_canonical_76 import entry
        entries.append(entry('Plains', 2))
    entries += [canonical_entry(name) if name == 'Platinum Angel' else deck_entry(name, 1)
                for name in sources]
    entries += [deck_entry(name, 1) for name in library_names]
    state = MatchFactory.from_decks(entries, entries, seed=9741)
    assert state.winner is None and not state.failed_draw_players
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.mechanic_choice_players = {1, 2}
    state.replacement_choice_players = {1, 2}
    state.replacement_choice_required = True
    state.turn = 5
    state.active_player, state.priority_player = 3-seat, seat
    state.step = Step.END_STEP
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.life = 20
        player.lands_played_this_turn = 1

    def place(name, owner, zone):
        player = state.players[owner]
        cid = next(cid for cid in player.library if state.cards[cid].name == name)
        player.library.remove(cid)
        getattr(player, zone.value).append(cid)
        state.cards[cid].move_to_zone(zone)
        if zone == Zone.BATTLEFIELD:
            assign_static_order_on_battlefield_entry(state, cid)
            state.cards[cid].tapped = state.cards[cid].summoning_sick = False
        return cid

    cid = place(spell, seat, Zone.HAND)
    for _ in range(3):
        place('Island', seat, Zone.BATTLEFIELD)
    if spell == 'Cloudblazer':
        for _ in range(2):
            place('Plains', seat, Zone.BATTLEFIELD)
        state.step = Step.PRECOMBAT_MAIN
        state.active_player = seat
    bear = place('Grizzly Bears', seat, Zone.BATTLEFIELD)
    for name in sources:
        place(name, 3-seat if name == 'Narset, Parter of Veils' else seat, Zone.BATTLEFIELD)
    player = state.players[seat]
    retained = ([next(x for x in player.library if state.cards[x].name == name) for name in library_names]
                if library_names else player.library[:remaining])
    assert len(retained) == remaining
    for extra in list(player.library):
        if extra in retained:
            continue
        player.library.remove(extra)
        player.graveyard.append(extra)
        state.cards[extra].move_to_zone(Zone.GRAVEYARD)
    state.draws_this_turn[seat] = previous
    state.players[3-seat].life = 2
    return state, cid, bear


def digest(state):
    return hashlib.sha256(pickle.dumps(state, protocol=5)).hexdigest()


def typed(action):
    return decode_action(encode_action(complete_action(action)))


def choose(state, seat):
    before, rng, local = digest(state), random.getstate(), state.rng.getstate()
    moves = RULES.legal_moves(state, seat)
    original = deepcopy(moves)
    action = typed(AIAgent('master', 'Control').choose_action(state, moves, seat).action)
    assert digest(state) == before and moves == original
    assert random.getstate() == rng and state.rng.getstate() == local
    return action


def cast_and_settle(state, seat, cid):
    before = digest(state)
    result = checked_action(state, RULES, seat, typed({'type': 'cast_spell', 'card_id': cid}))
    assert digest(state) == before
    assert result.stack[-1].payload['mana_spent'] == (3 if state.cards[cid].name == 'Quick Study' else 2)
    for _ in range(32):
        assert not (result.pending_mechanic_choice or result.pending_replacement_choice
                    or result.pending_trigger_order), 'Unresolved choices are not terminal proof'
        if result.winner is not None or not result.stack:
            return result
        result = checked_action(result, RULES, result.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native settlement bound')


def through_next_draw(state, seat):
    for _ in range(32):
        if state.winner is not None or (state.active_player == seat and state.step == Step.DRAW and not state.stack):
            return state
        assert not (state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order)
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Native next-draw bound')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('remaining', [1, 2])
def test_teacher_declines_native_losing_draw_and_pass_really_wins(seat, remaining):
    state, cid, bear = position(seat, remaining)
    lost = cast_and_settle(state, seat, cid)
    assert lost.winner == (3-seat if remaining == 1 else None)
    lost = through_next_draw(lost, seat)
    assert lost.winner == 3-seat and seat in lost.failed_draw_players
    won = checked_action(state, RULES, seat, {'type': 'pass_priority'})
    attacked = False
    for _ in range(80):
        if won.winner is not None:
            break
        actor = won.priority_player
        if won.active_player == seat and won.step == Step.DECLARE_ATTACKERS and not won.attackers_declared:
            assert actor == seat
            action = {'type': 'attack', 'attackers': [bear]}
            attacked = True
        else:
            action = {'type': 'pass_priority'}
        won = checked_action(won, RULES, actor, action)
    assert attacked and won.winner == seat and won.players[3-seat].life == 0
    assert len(won.players[seat].library) == remaining-1
    chosen = choose(state, seat)
    if remaining == 1:
        assert chosen['type'] == 'pass_priority'
    else:
        view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
        assert AIAgent('master', 'Control')._draw_cast_loses(
            view, typed({'type': 'cast_spell', 'card_id': cid}), seat) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('remaining,sources,previous,drawn,immediate_loss,next_loss', [
    (1, (), 0, 1, True, True),
    (2, (), 0, 2, False, True),
    (3, (), 0, 2, False, False),
    (2, ('Thought Reflection',), 0, 2, True, True),
    (4, ('Thought Reflection',), 0, 4, False, True),
    (5, ('Thought Reflection',), 0, 4, False, True),
    (6, ('Thought Reflection',), 0, 4, False, False),
    (1, ('Thought Reflection', 'Spirit of the Labyrinth'), 0, 1, False, True),
    (2, ('Thought Reflection', 'Spirit of the Labyrinth'), 0, 1, False, False),
    (1, ('Narset, Parter of Veils',), 0, 1, False, True),
    (2, ('Narset, Parter of Veils',), 0, 1, False, False),
    (0, ('Spirit of the Labyrinth',), 1, 0, False, True),
    (1, ('Spirit of the Labyrinth',), 1, 0, False, False),
    (1, ('Platinum Angel',), 0, 1, False, False),
])
def test_native_draw_boundaries_not_printed_count_bans(seat, remaining, sources, previous, drawn, immediate_loss, next_loss):
    state, cid, _ = position(seat, remaining, sources, previous)
    result = cast_and_settle(state, seat, cid)
    assert result.draws_this_turn.get(seat, 0) - previous == drawn
    assert result.winner == (3-seat if immediate_loss else None)
    result = through_next_draw(result, seat)
    assert result.winner == (3-seat if next_loss else None)
    action = choose(state, seat)
    if next_loss and not immediate_loss:
        view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
        assert AIAgent('master', 'Control')._draw_cast_loses(
            view, typed({'type': 'cast_spell', 'card_id': cid}), seat) is None
    else:
        assert (action['type'] == 'cast_spell' and action.get('card_id') == cid) is not immediate_loss


@pytest.mark.parametrize('seat', [1, 2])
def test_count_only_loss_guard_is_hidden_library_swap_and_root_rng_pure(seat):
    state, cid, _ = position(seat, 2, ('Thought Reflection',),
                             library_names=('Vision Skeins', 'Stinkweed Imp'))
    # Public counts and all real printed inputs remain fixed; only private order changes.
    swapped = deepcopy(state)
    for player in swapped.players.values():
        player.library.reverse()
    assert [state.cards[x].name for x in state.players[seat].library] != [
        swapped.cards[x].name for x in swapped.players[seat].library]
    before, other = digest(state), digest(swapped)
    assert choose(state, seat) == choose(swapped, seat) == typed({'type': 'pass_priority'})
    view, moves = decision_view(state, seat, RULES.legal_moves(state, seat))
    assert all(is_unknown(view.cards[x]) for player in view.players.values() for x in player.library)
    offered = next(move for move in moves if move.get('card_id') == cid and move['type'] == 'cast_spell')
    vbefore = digest(view)
    assert AIAgent('master', 'Control')._bad_shared_draw_cast(view, offered, seat)
    assert digest(view) == vbefore and digest(state) == before and digest(swapped) == other


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('remaining', [1, 2, 3])
def test_learned_route_cannot_reselect_paid_proven_draw_loss(monkeypatch, seat, remaining):
    state, cid, _ = position(seat, remaining)
    cast = complete_action({'type': 'cast_spell', 'card_id': cid, 'cost_choice': {'id': 'base'}})
    wait = complete_action({'type': 'pass_priority'})
    assert cast_and_settle(state, seat, cid).winner == (3-seat if remaining == 1 else None)
    action, calls = _route(monkeypatch, state, seat, [cast, wait],
                           {'Quick Study': 0.9, 'pass_priority': -0.9})
    assert calls['state_packs']
    assert action == (wait if remaining == 1 else cast)


@pytest.mark.parametrize('seat', [1, 2])
def test_unresolved_replacement_order_is_not_a_proven_loss(seat):
    state, cid, _ = position(seat, 2, ('Thought Reflection', 'Thought Reflection'))
    cast = typed({'type': 'cast_spell', 'card_id': cid})
    paid = checked_action(state, RULES, seat, cast)
    for _ in range(4):
        if paid.pending_replacement_choice:
            break
        paid = checked_action(paid, RULES, paid.priority_player, {'type': 'pass_priority'})
    assert paid.pending_replacement_choice['player_id'] == seat
    assert len(paid.pending_replacement_choice['options']) == 2
    view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
    assert AIAgent('master', 'Control')._draw_cast_loses(view, cast, seat) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Opt', 'Consider', 'Brainstorm'])
def test_cantrip_private_continuations_are_unknown_not_certified_safe(seat, spell):
    state, cid, _ = position(seat, 1, spell=spell)
    cast = typed({'type': 'cast_spell', 'card_id': cid})
    view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
    assert AIAgent('master', 'Control')._draw_cast_loses(view, cast, seat) is None
    result = checked_action(state, RULES, seat, cast)
    assert result.stack[-1].payload['mana_spent'] == 1
    for _ in range(32):
        if result.winner is not None:
            break
        pending = result.pending_mechanic_choice or result.pending_replacement_choice or result.pending_trigger_order
        if pending:
            actor = pending.get('player_id', pending.get('current_controller'))
            result = checked_action(result, RULES, actor, choose(result, actor))
        elif result.stack:
            result = checked_action(result, RULES, result.priority_player, {'type': 'pass_priority'})
        else:
            break
    else:
        raise AssertionError('Cantrip native continuation bound')
    # This records the residual scope: UNKNOWN is not an assertion of safety.
    result = through_next_draw(result, seat)
    assert result.winner == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('spell', ['Opt', 'Consider', 'Brainstorm', 'Cloudblazer'])
def test_zero_library_native_draw_program_is_not_missed_by_body_compiler(seat, spell):
    state, cid, _ = position(seat, 0, spell=spell)
    cast = typed({'type': 'cast_spell', 'card_id': cid})
    result = checked_action(state, RULES, seat, cast)
    assert result.stack[-1].payload['mana_spent'] == (5 if spell == 'Cloudblazer' else 1)
    for _ in range(16):
        if result.winner is not None:
            break
        assert not (result.pending_mechanic_choice or result.pending_replacement_choice or result.pending_trigger_order)
        result = checked_action(result, RULES, result.priority_player, {'type': 'pass_priority'})
    assert result.winner == 3-seat
    view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
    assert AIAgent('master', 'Control')._draw_cast_loses(view, cast, seat) is True


@pytest.mark.parametrize('seat', [1, 2])
def test_real_paid_entry_gain_then_draw_program_has_opaque_terminal_proof(seat):
    from ai.pending_effects import settled_public_position
    state, cid, _ = position(seat, 1, spell='Cloudblazer')
    state = checked_action(state, RULES, seat, typed({'type': 'cast_spell', 'card_id': cid}))
    assert state.stack[-1].payload['mana_spent'] == 5
    for _ in range(4):
        if state.stack and state.stack[-1].effect_key == 'effect_sequence':
            break
        state = checked_action(state, RULES, state.priority_player, {'type': 'pass_priority'})
    item = state.stack[-1]
    assert item.source_card_id == cid
    assert [step['effect_key'] for step in item.payload['effects']] == ['gain_life', 'draw_cards']
    assert [step['payload']['amount'] for step in item.payload['effects']] == [2, 2]
    view, _ = decision_view(state, seat, RULES.legal_moves(state, seat))
    before, rng, local = digest(view), random.getstate(), view.rng.getstate()
    native = deepcopy(state)
    for _ in range(8):
        if native.winner is not None:
            break
        native = checked_action(native, RULES, native.priority_player, {'type': 'pass_priority'})
    assert native.winner == 3-seat and native.players[seat].life == 22
    forecast = settled_public_position(view, seat, opaque_draw_counts=True)
    assert forecast is not None and forecast.winner == 3-seat
    assert forecast.players[seat].life == 22
    assert digest(view) == before and random.getstate() == rng and view.rng.getstate() == local


@pytest.mark.parametrize('seat', [1, 2])
def test_native_winning_shared_draw_is_not_globally_banned(seat):
    state, cid, _ = position(seat, 2, spell='Vision Skeins')
    opponent = state.players[3-seat]
    for extra in list(opponent.library)[1:]:
        opponent.library.remove(extra)
        opponent.graveyard.append(extra)
        state.cards[extra].move_to_zone(Zone.GRAVEYARD)
    result = cast_and_settle(state, seat, cid)
    assert result.winner == seat
    assert choose(state, seat)['card_id'] == cid
