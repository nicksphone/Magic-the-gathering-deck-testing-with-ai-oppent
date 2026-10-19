"""Native paid damage frames; controlled corruptions are not legal episodes."""
from copy import deepcopy

import pytest

from game_state.state import object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack, _validate_damage_activation_source
from tests import test_damage_source_controller_audit as audit
from tests import test_noncombat_clause_source_boundaries as boundary
from tests import test_soulscar_affected_order_goldens as prior


def live(seat):
    state, target, _, mage = audit.setup(seat)
    source = audit.add(state, 'Prodigal Sorcerer', seat)
    state = audit.priority(state, seat)
    state = audit.send(state, seat, {'type': 'activate_ability', 'card_id': source,
        'ability_index': 0, 'targets': {'target_card_id': target}})
    return state, target, mage, source


def reject_pure(state):
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected):
        resolve_top_of_stack(state)
    assert prior.snapshot(state) == before
    assert prior.snapshot(prior.reload_exact(state)) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reference', [None, [], {}, {'incarnation': 0},
    {'incarnation': True, 'zone_change_sequence': 0},
    {'incarnation': 0, 'zone_change_sequence': False},
    {'incarnation': -1, 'zone_change_sequence': 0},
    {'incarnation': 0, 'zone_change_sequence': -1},
    {'incarnation': '0', 'zone_change_sequence': 0},
    {'incarnation': 0, 'zone_change_sequence': 0, 'extra': 1}])
def test_paid_live_frame_malformed_reference_rejects_root_pure(seat, reference):
    state, _, _, _ = live(seat)
    state.stack[-1].payload['__activation_source_reference'] = reference
    reject_pure(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [None, [], {'controller': True},
    {'controller': None}, {'controller': 3}, {'controller': 1.0},
    {'controller': 1, 'battlefield_incarnation': True},
    {'controller': 1, 'battlefield_incarnation': -1}])
def test_present_bad_lki_rejected_even_for_live_same_object(seat, bad):
    state, _, _, _ = live(seat)
    state.stack[-1].payload['__source_lki'] = bad
    reject_pure(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_live_control_change_preserves_native_identity_and_current_applicability(seat):
    state, target, mage, source = live(seat)
    reference = deepcopy(state.stack[-1].payload['__activation_source_reference'])
    ability_id = state.stack[-1].id
    state, _, frame = audit.cast(state, 'Ray of Command', 3-seat, {'target_card_id': source})
    state = audit.resolve_announced(state, frame)
    assert state.stack[-1].id == ability_id
    assert state.cards[source].controller == 3-seat
    assert object_incarnation(state.cards[source]) == reference['incarnation']
    assert state.cards[source].zone_change_sequence == reference['zone_change_sequence']
    assert '__source_lki' not in state.stack[-1].payload
    restored = prior.reload_exact(state)
    assert not resolve_top_of_stack(restored)  # Native replacement choice pauses resolution.
    assert not resolve_top_of_stack(state)
    assert prior.snapshot(restored) == prior.snapshot(state)
    boundary.old_source_verdict(state, seat, target, mage, source, 'conversion')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('container', ['direct', 'conditional', 'sequence'])
def test_bad_departed_receipt_rejected_before_target_fizzle_including_containers(seat, container):
    state, target, _, _, _, _ = boundary.departed(seat, 'graveyard')
    item = state.stack[-1]
    item.payload['__source_lki']['controller'] = None
    # Controlled persisted-frame boundary, not a fabricated canonical compound card.
    if container == 'conditional':
        item.effect_key = 'conditional_instruction'
        item.payload.update(condition='graveyard_types', effect_key='deal_damage', normal=1,
                            enhanced=3, __conditional_target_reference=['missing', 0, 0])
    elif container == 'sequence':
        item.effect_key = 'effect_sequence'
        item.payload['effects'] = [{'effect_key': 'deal_damage',
                                  'payload': {'amount': 1, 'target_card_id': target}}]
    else:
        item.payload['__announced_target_references']['targets']['target_card_id']['incarnation'] += 1000
    reject_pure(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_child_lki_cannot_override_valid_root_receipt_with_wrong_incarnation(seat):
    state, target, _, _, _, receipt = boundary.departed(seat, 'graveyard')
    item = state.stack[-1]
    item.effect_key = 'effect_sequence'
    receipt['battlefield_incarnation'] += 1
    item.payload['effects'] = [{'effect_key': 'deal_damage', 'payload': {
        'amount': 1, 'target_card_id': target, '__source_lki': receipt}}]
    reject_pure(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_disappeared_source_card_still_resolves_with_real_retained_lki(seat):
    state, target, mage, source, _, _ = boundary.departed(seat, 'graveyard')
    # Controlled reader boundary: no fabricated LKI; receipt came from actual paid death.
    state.players[seat].graveyard.remove(source)
    del state.cards[source]
    assert not resolve_top_of_stack(state)
    boundary.old_source_verdict(state, seat, target, mage, source, 'prevention')


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_lki_with_disappeared_source_rejects_without_mutation(seat):
    state, _, _, source, _, _ = boundary.departed(seat, 'graveyard')
    state.players[seat].graveyard.remove(source)
    del state.cards[source]
    state.stack[-1].payload.pop('__source_lki')
    reject_pure(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['incarnation', 'zone_change_sequence'])
def test_live_source_reference_identity_mismatch_without_lki_rejects(seat, field):
    state, _, _, _ = live(seat)
    state.stack[-1].payload['__activation_source_reference'][field] += 1
    reject_pure(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('corrupt', [False, True])
def test_actual_paid_target_bounce_valid_fizzle_or_early_bad_lki_rejection(seat, corrupt):
    state, target, _, _ = live(seat)
    frame_id = state.stack[-1].id
    remaining = state.numeric_prevention_shields[0].remaining
    state, _ = boundary.extra_cast(state, 'Unsummon', seat, target)
    assert state.stack[-1].id == frame_id
    if corrupt:
        state.stack[-1].payload['__source_lki'] = {'controller': None,
            'battlefield_incarnation': state.stack[-1].payload['__activation_source_reference']['incarnation']}
        reject_pure(state)
    else:
        state = prior.reload_exact(state)
        assert resolve_top_of_stack(state)
        assert not any(item.id == frame_id for item in state.stack)
        assert not state.pending_replacement_choice
        assert state.numeric_prevention_shields[0].remaining == remaining
        assert not state.cards[target].counters.get('-1/-1', 0)
        assert state.players[1].life == state.players[2].life == 20
        for viewer in (1, 2):
            view, _ = boundary.decision_view(state, viewer, boundary.RulesEngine().legal_moves(state, viewer))
            for cid in state.players[3-viewer].hand + state.players[3-viewer].library:
                if cid == target:
                    remembered = boundary.remembered_hand_card(state, viewer, state.cards[cid])
                    assert remembered is not None and remembered.name == 'Torrential Gearhulk'
                    assert view.cards[cid].__dict__ == remembered.__dict__
                else:
                    assert boundary.is_unknown(view.cards[cid])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('marker', ['__activation_source_reference', '__ability_target_text'])
def test_legacy_without_both_native_markers_stays_outside_guard_root_pure(seat, marker):
    state, _, _, _ = live(seat)
    # Reader-only compatibility: removal of a native marker is not an external valid action.
    state.stack[-1].payload.pop(marker)
    before = prior.snapshot(state)
    _validate_damage_activation_source(state, state.stack[-1])
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_existing_real_paid_hand_discard_damage_channel_remains_supported(seat):
    from tests.test_hand_activations import test_damage_channel_discards_exact_source_and_is_not_a_spell
    # Reuse the unchanged complete canonical Twinshot Sniper admission/payment/restore assertions.
    test_damage_channel_discards_exact_source_and_is_not_a_spell(seat)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_cast_prowess_frame_remains_outside_native_activation_guard(seat):
    state, target, _, _ = audit.setup(seat)
    state, _, _ = audit.cast(state, 'Lightning Bolt', 3-seat, {'target_card_id': target})
    trigger = state.stack[-1]
    assert trigger.payload.get('__trigger_event') == 'spell_cast'
    before = prior.snapshot(state)
    _validate_damage_activation_source(state, trigger)
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('container', ['conditional', 'sequence'])
def test_true_departed_lki_validates_inside_containing_packet_root_pure(seat, container):
    state, target, _, _, _, _ = boundary.departed(seat, 'graveyard')
    item = state.stack[-1]
    # Controlled packet-reader boundary, not a newly supported canonical conditional activation.
    if container == 'conditional':
        item.effect_key = 'conditional_instruction'
        item.payload.update(condition='graveyard_types', effect_key='deal_damage', normal=1, enhanced=3)
    else:
        item.effect_key = 'effect_sequence'
        item.payload['effects'] = [{'effect_key': 'deal_damage',
            'payload': {'amount': 1, 'target_card_id': target, '__source_lki': deepcopy(item.payload['__source_lki'])}}]
    before = prior.snapshot(state)
    _validate_damage_activation_source(state, item)
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_unknown_conditional_packet_not_recursed_or_claimed_as_damage(seat):
    state, _, _, _ = live(seat)
    item = state.stack[-1]
    # Unknown controlled packet, never submitted as a supported canonical instruction.
    item.effect_key = 'conditional_instruction'
    item.payload['effect_key'] = 'conditional_instruction'
    before = prior.snapshot(state)
    _validate_damage_activation_source(state, item)
    assert prior.snapshot(state) == before
