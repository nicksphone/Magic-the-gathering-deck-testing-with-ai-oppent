"""Complete grammar plus genuine paid canonical resolution; no injected triggers."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine import oracle_effects
from tests.test_linked_damage_targets import raw_card
from tests.test_optional_land_from_hand_audit import (
    setup, cast, advance, land_choice, roundtrip,
)

FIXTURE = Path(__file__).parent / 'fixtures/optional_land_compiler'
ROWS = {}
for entry in json.loads((FIXTURE / 'provenance.json').read_text())['cards']:
    raw = (FIXTURE / entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['oracle_id'] == entry['oracle_id']
    ROWS[row['name']] = row


@pytest.mark.parametrize('tapped', [False, True])
@pytest.mark.parametrize('draw', [None, 'a', 'two', '0', '12'])
def test_complete_optional_land_grammar_has_exact_order_and_no_inferred_choice(tapped, draw):
    body = 'You may put a land card from your hand onto the battlefield'
    body += ' tapped.' if tapped else '.'
    land = {'effect_key': 'put_land_from_hand', 'payload': {'optional': True, 'tapped': tapped}}
    if draw is None:
        expected = (land['effect_key'], land['payload'])
    else:
        body = f'Draw {draw} cards. ' + body
        amount = {'a': 1, 'two': 2, '0': 0, '12': 12}[draw]
        expected = ('effect_sequence', {'effects': [
            {'effect_key': 'draw_cards', 'payload': {'amount': amount}}, land,
        ]})
    assert oracle_effects.compile_optional_land_instruction(body) == expected


@pytest.mark.parametrize('tail', [
    ' Then draw a card.', ' If you control a creature.', ' and scry 1.',
    ' unless an opponent pays {1}.', ' until end of turn.',
    ' Then discard a card.',
])
@pytest.mark.parametrize('draw_first', [False, True])
def test_new_prefix_unknown_tail_never_compiles_partial_reward(tail, draw_first):
    body = ('Draw a card. ' if draw_first else '')
    body += 'You may put a land card from your hand onto the battlefield.' + tail
    assert oracle_effects.optional_land_instruction_candidate(body)
    assert oracle_effects.compile_optional_land_instruction(body) is None


@pytest.mark.parametrize('body', [
    'Put a land card from your hand onto the battlefield tapped.',
    'Target player draws a card.', 'You may draw a card.',
    'Search your library for a basic land card.',
    'You gain half X life and draw half X cards. Round down each time.',
])
def test_other_families_do_not_enter_optional_land_admission(body):
    assert not oracle_effects.optional_land_instruction_candidate(body)
    assert oracle_effects.compile_optional_land_instruction(body) is None


def raw_position(name, seat, **options):
    state, original, land, drawn = setup(name, seat, **options)
    # Replace the normalized seed fixture with the complete official raw row.
    assert original.oracle_text == ROWS[name]['oracle_text']
    state.players[seat].hand.remove(original.id)
    original.move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(original.id)
    source = raw_card(state, ROWS[name], seat, Zone.HAND)
    return state, source, land, drawn


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Growth Spiral', 'Arboreal Grazer'])
@pytest.mark.parametrize('select', [False, True])
def test_full_raw_paid_optional_choice_private_restart_and_exact_entry(seat, name, select, tmp_path):
    state, source, land, drawn = raw_position(name, seat)
    ledger = []
    state = advance(cast(state, source, seat, ledger), ledger)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'land_from_hand' and pending['player_id'] == seat
    assert pending['min_count'] == 0 and pending['count'] == 1
    assert pending['effect_payload']['optional'] is True
    assert pending['effect_payload']['tapped'] is (name == 'Arboreal Grazer')
    assert land.id in state.players[seat].hand
    if name == 'Growth Spiral':
        assert drawn in state.players[seat].hand and state.draws_this_turn[seat] == 1
    else:
        assert source.id in state.players[seat].battlefield and drawn in state.players[seat].library
    public = serialize_match(state, look_players=(3-seat,))
    assert set(public['pending_mechanic_choice']) == {'kind', 'player_id', 'label', 'count', 'min_count'}
    assert not RulesEngine().legal_moves(state, 3-seat)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'choose_mechanic', 'card_ids': [land.id]})
    assert serialize_match_snapshot(state) == before
    state = roundtrip(state, tmp_path / 'raw-pending.sqlite')
    state = land_choice(state, seat, ledger, selected=land.id if select else None)
    state = advance(state, ledger)
    assert land.id in (state.players[seat].battlefield if select else state.players[seat].hand)
    if select:
        assert state.cards[land.id].tapped is (name == 'Arboreal Grazer')
    assert state.players[seat].lands_played_this_turn == 1
    assert state.pending_mechanic_choice is None
    roundtrip(state, tmp_path / 'raw-complete.sqlite')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Growth Spiral', 'Arboreal Grazer'])
def test_wrong_actor_paid_action_never_reaches_compiler(seat, name, monkeypatch):
    state, source, _, _ = raw_position(name, seat)
    calls = []
    original = oracle_effects.compile_optional_land_instruction
    def observe(body):
        calls.append(body)
        return original(body)
    monkeypatch.setattr(oracle_effects, 'compile_optional_land_instruction', observe)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat, {'type': 'cast_spell', 'card_id': source.id})
    assert not calls and serialize_match_snapshot(state) == before
