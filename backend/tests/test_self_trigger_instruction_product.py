"""Bounded compiler contracts and real canonical paid continuation episodes."""
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Zone
from rules_engine import oracle_effects
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_trigger_instruction_compilation_audit import (
    FAMILIES, KOZILEK, position, pending, passes, item_for, compilation_trace,
)
from tests.test_self_graveyard_replacement_audit import act, snap, restart
from tests.test_linked_damage_targets import raw_card

FIXTURE = Path(__file__).parent / 'fixtures/trigger_instruction_product'
PROVENANCE = json.loads((FIXTURE / 'provenance.json').read_text())
ROWS = {}
for entry in PROVENANCE['cards']:
    data = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    row = json.loads(data)
    assert row['object'] == 'card' and row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row


@pytest.mark.parametrize('token,count', [('a', 1), ('one', 1), ('two', 2), ('three', 3),
                                      ('four', 4), ('ten', 10), ('0', 0), ('12', 12)])
@pytest.mark.parametrize('compound', [False, True])
def test_complete_instruction_contract_counts_and_order(token, count, compound):
    # Grammar units, not rewritten Oracle assigned to a fictional card.
    body = ('You gain 2 life and ' if compound else '') + f'draw {token} cards.'
    result = oracle_effects.compile_draw_life_instruction(body)
    draw = {'effect_key': 'draw_cards', 'payload': {'amount': count}}
    expected = ('effect_sequence', {'effects': [
        {'effect_key': 'gain_life', 'payload': {'amount': 2}}, draw,
    ]}) if compound else ('draw_cards', {'amount': count})
    assert result == expected


@pytest.mark.parametrize('body', [
    'Draw a card. Destroy target creature.',
    'You gain 2 life and draw two cards, then discard a card.',
    'You gain 2 life and draw two cards and scry 1.',
    'You gain 2 life and draw two cards if you control a creature.',
    'If you control a creature, draw two cards.',
    'You may draw a card.',
    'You may pay {1}. If you do, draw a card.',
    'Draw two cards and you gain 2 life.',
    'Draw X cards.', 'Draw -1 cards.', 'Draw 1.5 cards.',
    'Target player draws two cards.',
    'You gains 2 life and draw two cards.',
])
def test_unknown_complete_body_never_compiles_a_partial_reward(body):
    assert oracle_effects.compile_draw_life_instruction(body) is None


def custom(name, seat):
    state, unused, _ = position('Cloudblazer', seat)
    state.players[seat].hand.remove(unused)
    state.cards[unused].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(unused)
    source = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 3, 'U': 1} if name == 'Riverwise Augur' else {'C': 11}
    return state, source.id, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}}


@pytest.mark.parametrize('seat', [1, 2])
def test_genuine_augur_unknown_suffix_retains_diagnostic_without_partial_draw(seat, tmp_path):
    state, cid, action = custom('Riverwise Augur', seat)
    life, library = state.players[seat].life, list(state.players[seat].library)
    state = pending(state, seat, action, 'Riverwise Augur')
    item = item_for(state, cid)
    assert item.effect_key == 'noop'
    assert item.payload['__unsupported_trigger_instruction'] == ROWS['Riverwise Augur']['oracle_text'].split(', ', 1)[1].lower()
    assert 'draw three cards' in item.payload['__trigger_full_clause']
    assert any('Unsupported self trigger instruction' in line for line in state.log)
    result = passes(restart(state, tmp_path, 'unknown-body-pending'))
    assert not result.players[seat].hand and result.players[seat].library == library
    assert result.players[seat].life == life and result.pending_mechanic_choice is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_trigger_draw_deckout_and_compound_life_order(seat, name, tmp_path):
    state, _, action = position(name, seat)
    removed = state.players[seat].library[:-1]
    state.players[seat].library = state.players[seat].library[-1:]
    for cid in removed:
        state.cards[cid].move_to_zone(Zone.EXILE)
        state.players[seat].exile.append(cid)
    life = state.players[seat].life
    state = pending(state, seat, action, name)
    result = passes(restart(state, tmp_path, 'deckout-pending'))
    assert result.winner == 3-seat and seat in result.failed_draw_players
    assert len(result.players[seat].hand) == 1 and not result.players[seat].library
    assert result.players[seat].life == life + (2 if name == 'Cloudblazer' else 0)


def dredge_position(name, seat):
    state, cid, action = position(name, seat)
    imp = raw_card(state, ROWS['Stinkweed Imp'], seat, Zone.GRAVEYARD)
    return state, cid, imp.id, action


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_real_dredge_pause_deliberate_choice_private_restart_remaining_draws(seat, name, tmp_path):
    state, cid, imp, action = dredge_position(name, seat)
    library, life = list(state.players[seat].library), state.players[seat].life
    state = passes(pending(state, seat, action, name))
    choice = state.pending_mechanic_choice
    assert choice['kind'] == 'draw' and choice['player_id'] == seat and imp in choice['options']
    assert state.players[seat].life == life + (2 if name == 'Cloudblazer' else 0)
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'choose_mechanic', 'choice_id': imp})
    assert snap(state) == before
    view, _ = decision_view(state, 3-seat, RulesEngine().legal_moves(state, 3-seat))
    assert all(is_unknown(view.cards[card]) for card in library)
    state = act(restart(state, tmp_path, 'dredge-pending'), seat,
                {'type': 'choose_mechanic', 'choice_id': imp})
    remaining = 3 if name == KOZILEK else 1
    assert state.players[seat].hand == [imp] + list(reversed(library[-5-remaining:-5]))
    assert set(state.players[seat].graveyard) == set(library[-5:])
    assert state.players[seat].life == life + (2 if name == 'Cloudblazer' else 0), 'Do not replay the first sequence effect'
    assert state.pending_mechanic_choice is None
    assert all(item.source_card_id != cid or item.effect_key == 'noop' for item in state.stack)
    restart(state, tmp_path, 'dredge-completed')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_invalid_actor_cannot_reach_instruction_compiler(seat, name, monkeypatch):
    calls = []
    original = oracle_effects.compile_draw_life_instruction
    def observe(body):
        calls.append(body)
        return original(body)
    monkeypatch.setattr(oracle_effects, 'compile_draw_life_instruction', observe)
    state, _, action = position(name, seat)
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, action)
    assert not calls and snap(state) == before


def counter_source(state, seat, cid):
    counter = raw_card(state, ROWS['Counterspell'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 2}
    spell = next(item for item in state.stack if item.source_card_id == cid and item.effect_key == 'noop')
    if state.priority_player != 3-seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter.id,
                              'targets': {'target_stack_id': spell.id}})
    return passes(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_countered_kozilek_spell_graveyard_shuffle_then_cast_draw_survives(seat, tmp_path):
    state, cid, action = position(KOZILEK, seat)
    state = pending(state, seat, action, KOZILEK)
    state = counter_source(state, seat, cid)
    assert [item.effect_key for item in state.stack] == ['draw_cards', 'shuffle_graveyard_into_library']
    state = passes(restart(state, tmp_path, 'countered-kozilek'))
    assert state.stack[-1].effect_key == 'draw_cards'
    state = passes(state)
    assert len(state.players[seat].hand) == 4 and not state.stack
    restart(state, tmp_path, 'retained-cast-draw')


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_countered_ulamog_shuffle_then_retained_cast_destruction(seat, tmp_path):
    state, cid, action = custom('Ulamog, the Infinite Gyre', seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1, 2}
    target = raw_card(state, ROWS["Smuggler's Copter"], 3-seat, Zone.BATTLEFIELD)
    state = act(state, seat, action)
    choice = next(move for move in RulesEngine().legal_moves(state, seat) if move.get('target_card_id') == target.id)
    state = act(state, seat, {'type': 'choose_trigger_target', 'stack_id': choice['stack_id'],
                              'target_card_id': target.id})
    state = counter_source(state, seat, cid)
    assert [item.effect_key for item in state.stack] == ['destroy_permanent', 'shuffle_graveyard_into_library']
    state = passes(restart(state, tmp_path, 'ulamog-shuffle-first'))
    assert state.stack[-1].effect_key == 'destroy_permanent' and state.cards[target.id].zone == Zone.BATTLEFIELD
    state = passes(state)
    assert state.cards[target.id].zone == Zone.GRAVEYARD and not state.stack
    restart(state, tmp_path, 'retained-cast-destroyed')
