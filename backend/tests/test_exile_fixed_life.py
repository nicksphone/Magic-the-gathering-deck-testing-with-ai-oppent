"""Complete canonical exile/life instructions; paid native outcomes, not AI scores."""
from copy import copy

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_ai_recurring_engines import add
from tests.test_aura_linked_exile_paid import facts, pose, cast, settle, act, reload
from tests.test_exile_power_life_edges import RAW


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('foreign_owner', [False, True])
def test_paid_exile_rewards_actual_predeparture_controller(facts, seat, foreign_owner):
    state, source, _, target, _ = pose(
        facts, seat, source_name='Lay Down Arms', foreign_owner=foreign_owner)
    owner = state.cards[target].owner
    state = settle(cast(state, seat, source, target))
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.cards[target].zone == Zone.EXILE
    assert target in state.players[owner].exile
    assert state.players[3 - seat].life == 23
    assert state.players[seat].life == 20
    assert not state.linked_exiles


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_bounce_response_fizzles_exile_and_its_life_reward(facts, seat):
    state, source, _, target, _ = pose(facts, seat, source_name='Lay Down Arms')
    reply = add(state, 'Unsummon', 3 - seat, Zone.HAND, cards=RAW)
    state.players[3 - seat].mana_pool['U'] = 1
    state = cast(state, seat, source, target)
    state = act(state, seat, {'type': 'pass_priority'})
    state = settle(cast(state, 3 - seat, reply.id, target))
    assert state.cards[target].zone == Zone.HAND
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert state.players[seat].life == state.players[3 - seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('conversion', ['Tainted Remedy', "Alhammarret's Archive"])
def test_fixed_life_uses_existing_replacement_aware_gain_resolver(facts, seat, conversion):
    state, source, _, target, _ = pose(facts, seat, source_name='Lay Down Arms')
    recipient = 3 - seat
    add(state, conversion, seat if conversion == 'Tainted Remedy' else recipient,
        Zone.BATTLEFIELD, cards=RAW)
    state = settle(cast(state, seat, source, target))
    assert state.cards[target].zone == Zone.EXILE
    assert state.players[recipient].life == (17 if conversion == 'Tainted Remedy' else 26)
    assert state.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('double_first', [False, True])
def test_pending_replacement_retains_recipient_and_real_spell_context(facts, seat, double_first):
    state, source, _, target, _ = pose(facts, seat, source_name='Lay Down Arms')
    recipient = 3 - seat
    converter = add(state, 'Tainted Remedy', seat, Zone.BATTLEFIELD, cards=RAW)
    doubler = add(state, "Alhammarret's Archive", recipient, Zone.BATTLEFIELD, cards=RAW)
    state.replacement_choice_required = True
    state.replacement_choice_players = {recipient}
    state = cast(state, seat, source, target)
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    pending = state.pending_replacement_choice
    assert state.cards[target].zone == Zone.EXILE
    assert pending['player_id'] == recipient and pending['controller'] == seat
    assert pending['gain_payload']['target_player'] == recipient
    assert pending['gain_payload']['amount'] == 3
    assert pending['gain_payload']['__source_card_id'] == source
    assert state.players[recipient].life == 20
    state = reload(state)
    state = act(state, recipient, {'type': 'choose_replacement',
                'replacement_source_id': doubler.id if double_first else converter.id})
    assert not state.pending_replacement_choice
    assert state.players[recipient].life == (14 if double_first else 17)
    assert state.players[seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_control_change_seam_uses_resolution_not_announcement_controller(facts, seat):
    state, source, _, target, _ = pose(facts, seat, source_name='Lay Down Arms')
    state = cast(state, seat, source, target)
    # Trusted control seam while a real paid spell is pending, not a played
    # control-changing response or a copied-spell qualification claim.
    state.players[3 - seat].battlefield.remove(target)
    state.players[seat].battlefield.append(target)
    state.cards[target].controller = seat
    state = settle(state)
    assert state.cards[target].zone == Zone.EXILE
    assert target in state.players[3 - seat].exile
    assert state.players[seat].life == 23 and state.players[3 - seat].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [
    ' Draw a card.', ' If you gained life this way, draw a card.', '\nUnknown instruction.',
])
def test_unknown_exile_life_suffix_has_no_partial_reward_or_exile(facts, seat, tail):
    state, source, _, target, _ = pose(facts, seat, source_name='Lay Down Arms')
    negative = copy(state.cards[source])
    negative.oracle_text += tail  # Deliberate noncanonical parser-negative specimen.
    before = serialize_match_snapshot(state)
    key, payload = infer_effect_from_oracle(state, negative, seat, {'target_card_id': target})
    assert key == 'noop' and payload.get('__unsupported_instruction')
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_mana_value_target_restriction_is_not_lost_by_complete_body_compiler(facts, seat):
    state, source, _, target, _ = pose(
        facts, seat, source_name='Lay Down Arms', target_name='Nissa, Who Shakes the World')
    before = serialize_match_snapshot(state)
    # Nissa is neither a creature nor below this board's four-Plains bound.
    with pytest.raises(ActionRejected):
        cast(state, seat, source, target)
    assert serialize_match_snapshot(state) == before
