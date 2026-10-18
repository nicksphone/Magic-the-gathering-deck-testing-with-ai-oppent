"""Real checked casts; private protocol mutations are not canonical card facts."""
from copy import deepcopy
import json

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from tests.test_forge_human_replacement_order import (
    act, assert_initial_choice, balances, cast_action, choose, restore, setup,
)


def paused_cast(seat):
    state, forges, spell, _ = setup(seat)
    state.players[seat].mana_pool['C'] = 2
    original = serialize_match_snapshot(state)
    result = act(state, seat, cast_action(state.cards[spell]))
    assert serialize_match_snapshot(state) == original
    assert_initial_choice(result, seat, balances(state))
    return result, forges, spell


@pytest.mark.parametrize('seat', [1, 2])
def test_real_cast_pause_has_typed_payment_and_prepared_owner(seat):
    state, forges, spell = paused_cast(seat)
    value = state.mana_continuation
    assert value['version'] == 1 and value['origin']['action_kind'] == 'cast_spell'
    assert [(f['tag'], f.get('op'), f['phase']) for f in value['frames']] == [
        ('owner', 'cast', 'mana'), ('payment', None, 'produce'),
        ('mana_activation', None, 'linked_damage')]
    owner, payment, activation = value['frames']
    assert owner['payer'] == payment['payer'] == activation['payer'] == seat
    assert owner['data']['source']['card_id'] == spell
    assert activation['source']['card_id'] in forges
    assert payment['data']['cursor'] == 0 and payment['data']['in_flight'] is True
    assert state.cards[spell].zone == Zone.HAND and not state.stack
    assert json.loads(json.dumps(serialize_match_snapshot(state)))['mana_continuation'] == value


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [0, 1])
def test_real_two_choice_cast_publishes_once_after_locked_payment(seat, selected, monkeypatch):
    from rules_engine import engine
    state, forges, spell, _ = setup(seat)
    state.players[seat].mana_pool['C'] = 2
    before = serialize_match_snapshot(state)
    published = []
    real = engine.add_to_stack

    def observe(*args, **kwargs):
        item = real(*args, **kwargs)
        if item.source_card_id == spell:
            published.append(item)
        return item

    monkeypatch.setattr(engine, 'add_to_stack', observe)
    result = act(state, seat, cast_action(state.cards[spell]))
    ids = list(balances(result))
    assert not published and result.cards[spell].zone == Zone.HAND
    result = choose(restore(result), seat, ids[selected])
    assert result.pending_replacement_choice and not published
    assert result.cards[spell].zone == Zone.HAND and not result.stack
    result = choose(restore(result), seat, ids[1-selected])
    assert len(published) == 1 and result.stack[-1] is published[0]
    assert result.cards[spell].zone == Zone.STACK and result.mana_continuation is None
    assert all(result.cards[cid].tapped for cid in forges)
    assert balances(result) == {key: 2 for key in ids}
    assert result.players[seat].life == 20 and result.players[seat].prevent_damage_shield == 4
    assert not any(result.players[seat].mana_pool.values())
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('corruption', [
    'version', 'payer_bool', 'cursor_bool', 'requirement', 'source',
    'staging_prefix', 'unknown_payment_key', 'active_prefix',
])
def test_real_cast_snapshot_rejects_typed_and_binding_corruption(seat, corruption):
    state, _, _ = paused_cast(seat)
    before = serialize_match_snapshot(state)
    payload = deepcopy(before)
    value = payload['mana_continuation']
    owner, payment, activation = value['frames']
    if corruption == 'version':
        value['version'] = 2
    elif corruption == 'payer_bool':
        payment['payer'] = True
    elif corruption == 'cursor_bool':
        payment['data']['cursor'] = False
    elif corruption == 'requirement':
        payment['data']['req']['W'] += 1
    elif corruption == 'source':
        owner['data']['source']['incarnation'] += 1
    elif corruption == 'staging_prefix':
        owner['stage']['queue_start'] += 1
    elif corruption == 'unknown_payment_key':
        payment['data']['unregistered'] = 0
    else:
        payment['data']['in_flight'] = False
    with pytest.raises(ActionRejected):
        deserialize_match_snapshot(payload)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('invalid', ['wrong_actor', 'unaffordable_remaining_source'])
def test_selected_cast_continuation_rejection_keeps_entire_input(seat, invalid):
    state, forges, _ = paused_cast(seat)
    if invalid == 'unaffordable_remaining_source':
        # Explicit protocol staleness, not an invented played-game action.
        unused = next(cid for cid in forges if not state.cards[cid].tapped)
        state.cards[unused].tapped = True
    before = serialize_match_snapshot(state)
    receipt = next(iter(balances(state)))
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if invalid == 'wrong_actor' else seat,
                       {'type': 'choose_replacement',
                        'replacement_source_id': 'numeric-prevention:' + receipt})
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_private_cast_intent_omitted_for_both_public_viewers(seat):
    state, _, _ = paused_cast(seat)
    before = serialize_match_snapshot(state)
    for viewer in (1, 2):
        public = serialize_match(state, look_players=(viewer,))
        assert 'mana_continuation' not in public
        assert 'payment_contract' not in json.dumps(public)
    restored = deserialize_match_snapshot(json.loads(json.dumps(before)))
    assert serialize_match_snapshot(restored) == before
    assert serialize_match_snapshot(state) == before
