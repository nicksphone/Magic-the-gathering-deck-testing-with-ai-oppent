"""Funded canonical setup; every post-setup departure is a checked paid spell."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.state import Step, Zone
from rules_engine.oracle_effects import infer_effect_from_oracle, inspect_target_hints
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_selected_graveyard_reference import (
    COPY, UNSUMMON, ROWS, act, position, raw_card, ref, restart, snap,
)

FIXTURES = Path(__file__).parent / 'fixtures/causal_graveyard_return'
HASHES = {
    'cremate.json': 'ee297088c46cb15196fa27c4b6aa16599300ac8621fdd3cdd0ca37879f54405b',
    'pull-from-eternity.json': '80667247e72c531637fd69411716fa905fc3085627511033dde3e5fc3ef21a07',
}
RAW = {}
for filename, digest in HASHES.items():
    data = (FIXTURES / filename).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    row = json.loads(data)
    RAW[row['name']] = row


def record(label, state, **extra):
    path = Path(os.environ['MTG_CAUSAL_GY_EVIDENCE']) / (label + '.json')
    with path.open('x') as stream:
        json.dump({'state': snap(state), **extra}, stream, indent=2, default=str)


def setup(seat):
    state, source = position(seat, 'Torrential Gearhulk')
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].battlefield.remove(source)
    state.cards[source].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source)
    target = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    second = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    spells = {name: raw_card(state, raw, 3-seat, Zone.HAND).id
              for name, raw in {**RAW, 'Unsummon': UNSUMMON}.items()}
    copier = raw_card(state, COPY, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'U': 2, 'C': 6}
    state.players[3-seat].mana_pool = {'B': 1, 'W': 1, 'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source})
    assert resolve_top_of_stack(state)
    trigger = state.stack[-1]
    assert trigger.effect_key == 'cast_from_graveyard'
    selected = trigger.payload['target_card_id']
    assert selected in {target.id, second.id}
    if selected == second.id:
        target, second = second, target
    assert trigger.payload['__trigger_target_reference'] == ref(state.cards[target.id])
    return state, source, target.id, second.id, spells, copier.id


def respond(state, seat, spell, target):
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == seat
    action = {'type': 'cast_spell', 'card_id': spell,
              'targets': {'target_card_id': target}}
    before = snap(state)
    try:
        return act(state, seat, action)
    except ActionRejected as error:
        assert snap(state) == before, 'Rejected checked response mutated caller root'
        label = hashlib.sha256(os.environ['PYTEST_CURRENT_TEST'].encode()).hexdigest()[:12]
        record('rejection-' + label, state, action=action, reason=str(error),
               root_unchanged=True, legal_moves=RulesEngine().legal_moves(state, seat))
        raise


def exile_selected(seat):
    state, source, target, second, spells, copier = setup(seat)
    trigger_id = state.stack[-1].id
    seal = deepcopy(state.stack[-1].payload['__trigger_target_reference'])
    before_hand = len(state.players[3-seat].hand)
    state = respond(state, 3-seat, spells['Cremate'], target)
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.EXILE
    assert target in state.players[seat].exile
    assert len(state.players[3-seat].hand) == before_hand
    assert state.players[3-seat].mana_pool.get('B', 0) == 0
    trigger = next(item for item in state.stack if item.id == trigger_id)
    assert trigger.payload['__trigger_target_reference'] == seal
    return state, source, target, second, spells, copier, seal


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Cremate', 'Pull from Eternity'])
def test_complete_official_body_compilation(seat, name):
    if name == 'Pull from Eternity':
        state, _, target, _, spells, _, _ = exile_selected(seat)
    else:
        state, _, target, _, spells, _ = setup(seat)
    before = snap(state)
    key, payload = infer_effect_from_oracle(state, state.cards[spells[name]], 3-seat,
                                          {'target_card_id': target})
    record(f'compile-{name}-{seat}', state, effect_key=key, payload=payload,
           oracle=RAW[name]['oracle_text'])
    if name == 'Cremate':
        assert key == 'effect_sequence'
        assert [effect['effect_key'] for effect in payload['effects']] == [
            'exile_from_graveyard', 'draw_cards']
        assert payload['effects'][1]['payload']['amount'] == 1
    else:
        assert key != 'noop', 'Full canonical exile-to-owner-graveyard body unsupported'
    # Unsupported diagnostic recording may be intentional; supported compilation is pure.
    if name == 'Cremate':
        assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_pull_target_domain_is_face_up_exile_not_graveyard(seat):
    state, _, target, _, spells, _, _ = exile_selected(seat)
    hints = inspect_target_hints(state, state.cards[spells['Pull from Eternity']], 3-seat)
    options = {str(row['id']) for key, rows in hints.items()
               if key.endswith('_targets') and isinstance(rows, list)
               for row in rows if isinstance(row, dict) and 'id' in row}
    record(f'pull-domain-{seat}', state, hints=hints, offered_ids=sorted(options), target=target)
    assert target in options, 'Actual face-up Cremate-exiled target absent from Pull target domain'
    assert all(state.cards[cid].zone == Zone.EXILE for cid in options if cid in state.cards)


@pytest.mark.parametrize('seat', [1, 2])
def test_checked_paid_pull_returns_actual_exiled_object(seat):
    state, _, target, _, spells, _, seal = exile_selected(seat)
    record(f'pull-before-admission-{seat}', state, original_seal=seal,
           current_reference=ref(state.cards[target]))
    state = respond(state, 3-seat, spells['Pull from Eternity'], target)
    assert state.players[3-seat].mana_pool.get('W', 0) == 0
    state = restart(state)
    assert resolve_top_of_stack(state)
    record(f'pull-after-resolution-{seat}', state, original_seal=seal)
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert target in state.players[seat].graveyard
    assert ref(state.cards[target]) != seal


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_causal_aba_old_trigger_cannot_cast_reentered_target(seat):
    state, _, target, _, spells, _, seal = exile_selected(seat)
    record(f'aba-before-return-{seat}', state, original_seal=seal)
    state = respond(state, 3-seat, spells['Pull from Eternity'], target)
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert ref(state.cards[target]) != seal
    state = restart(state)
    assert state.stack[-1].payload['__trigger_target_reference'] == seal
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert not state.stack
    record(f'aba-complete-{seat}', state, original_seal=seal)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_cremate_draw_exile_and_original_trigger_control(seat):
    state, _, target, _, _, _, seal = exile_selected(seat)
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.EXILE
    assert not state.stack
    record(f'cremate-control-{seat}', state, original_seal=seal)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_source_unsummon_does_not_cancel_selected_permission(seat):
    state, source, target, _, spells, _ = setup(seat)
    seal = deepcopy(state.stack[-1].payload['__trigger_target_reference'])
    state = respond(state, 3-seat, spells['Unsummon'], source)
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.HAND
    assert state.players[3-seat].mana_pool.get('U', 0) == 0
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.STACK
    assert state.stack[-1].payload['__exile_instead_of_graveyard'] is True
    record(f'source-bounce-{seat}', state, original_seal=seal)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['keep', 'new'])
def test_real_paid_copy_keep_or_retarget_without_trusted_aba(seat, choice):
    state, _, first, second, _, copier = setup(seat)
    seal = deepcopy(state.stack[-1].payload['__trigger_target_reference'])
    state = act(state, seat, {'type': 'activate_ability', 'card_id': copier,
        'ability_index': 0, 'targets': {'target_stack_id': state.stack[-1].id}})
    assert state.cards[copier].tapped
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    copy_id = state.pending_mechanic_choice['stack_id']
    state = restart(state)
    selected = first if choice == 'keep' else second
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [
        'keep' if choice == 'keep' else 'target_card_id:' + second]})
    copied = next(item for item in state.stack if item.id == copy_id)
    assert copied.payload['target_card_id'] == selected
    assert copied.payload['__trigger_target_reference'] == ref(state.cards[selected])
    if choice == 'keep':
        assert copied.payload['__trigger_target_reference'] == seal
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[selected].zone == Zone.STACK
    record(f'copy-{choice}-{seat}', state, selected=selected, original_seal=seal)
