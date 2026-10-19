"""Canonical action goldens and labeled pure complete-grammar negatives."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected
from tests.test_cloudshift_compound_audit import position, ROWS, act, passes, restart, snap, raw_card

FIXTURE = Path(__file__).parent / 'fixtures/immediate_return_product'
for line in (FIXTURE / 'SHA256SUMS').read_text().splitlines():
    digest, filename = line.split()
    assert hashlib.sha256((FIXTURE / Path(filename).name).read_bytes()).hexdigest() == digest
EXTRA = {name: json.loads((FIXTURE / (name + '.json')).read_text()) for name in
         ('doubling-season', 'hardened-scales', 'raise-the-alarm', 'unsummon')}


@pytest.mark.parametrize('suffix', [' Draw a card.', ' Then gain 2 life.',
                                   ' If you do, draw a card.', ' until end of turn.',
                                   '\nRebound'])
@pytest.mark.parametrize('name', ROWS)
def test_unsupported_complete_tail_has_no_partial_exile_admission(name, suffix):
    state, source, spell, _ = position(1, name)
    proxy = deepcopy(state.cards[spell])
    proxy.oracle_text += suffix  # Pure grammar negative, NEVER executed as a card.
    proxy.card_faces = []
    before = snap(state)
    spec = build_ability_spec(state, proxy, 1, {'target_card_id': source}, report_unsupported=False)
    assert spec.effect.key == 'noop' and spec.effect.payload['__unsupported_immediate_return']
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_two_actual_blinks_do_not_retreat_new_incarnation_as_old_target(seat, name, tmp_path):
    state, source, first, _ = position(seat, name)
    second = raw_card(state, ROWS[name], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    sequence = state.cards[source].zone_change_sequence
    for spell in (first, second):
        state = act(state, seat, {'type': 'cast_spell', 'card_id': spell,
                                 'targets': {'target_card_id': source}})
    state = passes(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].zone_change_sequence == sequence + 2
    state = passes(restart(state, tmp_path, 'new-object-original-still-stacked'))
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].zone_change_sequence == sequence + 2
    assert state.cards[source].counters['+1/+1'] == 2
    assert all(state.cards[spell].zone == Zone.GRAVEYARD for spell in (first, second))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_actual_bounce_response_leaves_original_blink_target_in_hand(seat, name, tmp_path):
    state, source, blink, _ = position(seat, name)
    bounce = raw_card(state, EXTRA['unsummon'], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 1, 'U': 1, 'C': 1}
    sequence = state.cards[source].zone_change_sequence
    for spell in (blink, bounce):
        state = act(state, seat, {'type': 'cast_spell', 'card_id': spell,
                                 'targets': {'target_card_id': source}})
    state = passes(state)
    assert state.cards[source].zone == Zone.HAND
    state = passes(restart(state, tmp_path, 'departed-target'))
    assert state.cards[source].zone == Zone.HAND
    assert state.cards[source].zone_change_sequence == sequence + 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_real_paid_created_token_cannot_return_from_exile(seat, name, tmp_path):
    state, _, blink, _ = position(seat, name)
    maker = raw_card(state, EXTRA['raise-the-alarm'], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'W': 2, 'C': 2}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': maker, 'targets': {}})
    state = passes(state)
    token = next(cid for cid in state.players[seat].battlefield if state.cards[cid].is_token)
    sequence = state.cards[token].zone_change_sequence
    state = act(state, seat, {'type': 'cast_spell', 'card_id': blink,
                             'targets': {'target_card_id': token}})
    state = passes(restart(state, tmp_path, 'real-token-target'))
    assert token not in state.players[seat].battlefield
    if token in state.cards:
        assert state.cards[token].zone != Zone.BATTLEFIELD
        assert state.cards[token].zone_change_sequence == sequence + 1
    assert state.cards[blink].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first, expected', [('add', 6), ('double', 5)])
def test_entry_counter_replacement_choice_keeps_exiled_object_and_resumes_once(seat, first, expected, tmp_path):
    state, source, blink, _ = position(seat, 'cloudshift')
    for name in ('doubling-season', 'hardened-scales'):
        raw_card(state, EXTRA[name], seat, Zone.BATTLEFIELD)
    sequence = state.cards[source].zone_change_sequence
    state = act(state, seat, {'type': 'cast_spell', 'card_id': blink,
                             'targets': {'target_card_id': source}})
    state = passes(state)
    assert state.cards[source].zone == Zone.EXILE
    assert state.pending_replacement_choice['player_id'] == seat
    state = restart(state, tmp_path, 'entry-choice-with-retained-exile-reference')
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'choose_replacement', 'replacement_source_id': 'invalid'})
    assert snap(state) == before
    option = next(row for row in state.pending_replacement_choice['options'] if row['operation'] == first)
    state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    for _ in range(3):
        if not state.pending_replacement_choice:
            break
        option = state.pending_replacement_choice['options'][0]
        state = act(state, seat, {'type': 'choose_replacement', 'replacement_source_id': option['source_id']})
    assert state.pending_replacement_choice is None
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].zone_change_sequence == sequence + 2
    assert state.cards[source].counters['+1/+1'] == expected
    assert state.cards[blink].zone == Zone.GRAVEYARD
    restart(state, tmp_path, 'entry-choice-finished')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ROWS)
def test_existing_humility_suppresses_printed_fixed_counters_on_reentry(seat, name, tmp_path):
    from tests.test_self_graveyard_replacement_interactions import ROWS as CANONICAL
    state, source, blink, _ = position(seat, name)
    raw_card(state, CANONICAL['Humility'], 3-seat, Zone.BATTLEFIELD)
    sequence = state.cards[source].zone_change_sequence
    state = act(state, seat, {'type': 'cast_spell', 'card_id': blink,
                             'targets': {'target_card_id': source}})
    state = passes(restart(state, tmp_path, 'humility-on-stack'))
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].zone_change_sequence == sequence + 2
    assert state.cards[source].counters.get('+1/+1', 0) == 0
