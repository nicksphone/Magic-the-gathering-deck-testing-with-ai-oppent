"""Paid canonical shields; component malformed/cleanup boundaries are explicit."""
from copy import deepcopy
import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests import test_soulscar_protection_boundaries as boundary

base, prior = boundary.base, boundary.prior


def cast_salve(state, seat, target):
    from rules_engine.oracle_effects import inspect_target_hints
    source = base.add(state, 'Healing Salve', 3-seat, Zone.HAND)
    mode = next(mode for mode in inspect_target_hints(state, state.cards[source], 3-seat)['modes']
                if mode.startswith('Prevent'))
    state = prior.act(state, seat, {'type': 'pass_priority'})
    state = prior.act(state, 3-seat, {'type': 'cast_spell', 'card_id': source,
                                   'targets': {'mode_text': mode, 'target_card_id': target}})
    state = base.finish(prior.reload_exact(state))
    return state


def shielded(seat):
    state, _, target = boundary.setup(seat, target_name='Torrential Gearhulk', mage=False)
    return cast_salve(state, seat, target), target


@pytest.mark.parametrize('seat', [1, 2])
def test_two_real_salve_frames_independent_partial_consume_and_snapshot(seat):
    state, target = shielded(seat)
    state = cast_salve(state, seat, target)
    receipts = state.numeric_prevention_shields
    assert len(receipts) == 2
    assert len({r.receipt_id for r in receipts}) == len({r.resolving_stack_id for r in receipts}) == 2
    assert all(r.remaining == 3 and r.target_reference['card_id'] == target for r in receipts)
    assert all(r.source_reference['zone_change_sequence'] < state.cards[r.source_card_id].zone_change_sequence
               for r in receipts)
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state, _ = base.cast(state, 'Lightning Bolt', seat, target)
    state = base.finish(prior.reload_exact(state))
    assert {row['source_id'] for row in state.pending_replacement_choice['options']} == {
        'numeric-prevention:' + r.receipt_id for r in receipts}
    chosen = receipts[1].receipt_id
    state = prior.choose(state, 3-seat, 'numeric-prevention:' + chosen)
    assert [r.remaining for r in state.numeric_prevention_shields] == [3, 0]
    assert state.cards[target].counters['__prevent_damage_shield'] == 3
    assert not state.cards[target].counters.get('__damage_marked')
    state, _ = boundary.announce(state, seat, 'Hornet Sting', {'target_card_id': target})
    state = base.finish(prior.reload_exact(state))
    assert [r.remaining for r in state.numeric_prevention_shields] == [2, 0]
    assert state.cards[target].counters['__prevent_damage_shield'] == 2
    assert state.players[1].life == state.players[2].life == 20
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['negative', 'bool', 'duplicate', 'aggregate', 'expiry', 'extra', 'frame-alias'])
def test_receipt_snapshot_rejects_malformed_without_input_mutation(seat, bad):
    state, target = shielded(seat)
    payload = prior.snapshot(state)
    assert payload['numeric_prevention_shields']
    row = payload['numeric_prevention_shields'][0]
    if bad == 'negative':
        row['remaining'] = -1
    elif bad == 'bool':
        row['source_reference']['incarnation'] = True
    elif bad == 'duplicate':
        payload['numeric_prevention_shields'].append(deepcopy(row))
    elif bad == 'aggregate':
        payload['cards'][target]['counters']['__prevent_damage_shield'] = 0
    elif bad == 'expiry':
        row['expires_at_cleanup'] = False
    elif bad == 'extra':
        row['invented'] = 1
    else:
        duplicate = deepcopy(row)
        duplicate['receipt_id'] = 'not-the-same-receipt'
        payload['numeric_prevention_shields'].append(duplicate)
    before = deepcopy(payload)
    with pytest.raises(ActionRejected):
        deserialize_match_snapshot(payload)
    assert payload == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_announced_prevention_malformed_source_rejects_before_pop(seat):
    state, _, target = boundary.setup(seat, mage=False)
    source = base.add(state, 'Mending Hands', seat, Zone.HAND)
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': source,
                                  'targets': {'target_card_id': target}})
    state.stack[-1].payload['__prevention_source_reference'] = {'incarnation': True, 'zone_change_sequence': 1}
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected):
        resolve_top_of_stack(state)
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_component_cleanup_and_legacy_competition_boundary(seat):
    state, target = shielded(seat)
    snapshot = prior.snapshot(state)
    snapshot.pop('numeric_prevention_shields')
    legacy = deserialize_match_snapshot(snapshot)
    assert legacy.numeric_prevention_shields == []
    legacy, _ = base.cast(legacy, 'Lightning Bolt', seat, target)
    legacy = base.finish(legacy)
    assert not legacy.cards[target].counters.get('__damage_marked')
    unknown = deserialize_match_snapshot(snapshot)
    base.add(unknown, 'Soul-Scar Mage', seat)
    unknown, bolt = base.cast(unknown, 'Lightning Bolt', seat, target)
    while unknown.stack[-1].source_card_id != bolt:
        unknown = prior.act(unknown, unknown.priority_player, {'type': 'pass_priority'})
    before = prior.snapshot(unknown)
    with pytest.raises(ActionRejected, match='Legacy numeric prevention'):
        resolve_top_of_stack(unknown)
    assert prior.snapshot(unknown) == before
    # Component lifecycle hook, not a fabricated cleanup episode.
    RulesEngine()._clear_prevention_shields(state)
    assert not state.numeric_prevention_shields
    assert not state.cards[target].counters.get('__prevent_damage_shield')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opposing', [False, True])
def test_paid_prevention_copy_survives_countered_original_with_actual_frame(seat, opposing):
    import json
    from pathlib import Path
    from tests.test_linked_damage_targets import raw_card
    from tests.test_temporary_control_lifecycle_audit import passes
    from rules_engine.oracle_effects import inspect_target_hints
    state, _, target = boundary.setup(seat, target_name='Torrential Gearhulk', mage=False)
    copier = 3-seat if opposing else seat
    d = Path(__file__).parent / 'fixtures'
    salve = base.add(state, 'Healing Salve', seat, Zone.HAND)
    twin = raw_card(state, json.loads((d / 'coupled_targets/twincast.json').read_text()), copier, Zone.HAND).id
    counter = raw_card(state, json.loads((d / 'trigger_instruction_product/counterspell.json').read_text()), 3-seat, Zone.HAND).id
    mode = next(mode for mode in inspect_target_hints(state, state.cards[salve], seat)['modes'] if mode.startswith('Prevent'))
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': salve,
                                   'targets': {'mode_text': mode, 'target_card_id': target}})
    original = state.stack[-1]
    old_id, pre = original.id, deepcopy(original.payload['__prevention_source_reference'])
    if opposing:
        state = prior.act(state, seat, {'type': 'pass_priority'})
    state = prior.act(state, copier, {'type': 'cast_spell', 'card_id': twin,
                                    'targets': {'target_stack_id': old_id}})
    state = passes(state)
    assert 'keep' in state.pending_mechanic_choice['options']
    state = prior.act(state, copier, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    copy_id = state.stack[-1].id
    assert copy_id != old_id and state.stack[-1].controller == copier
    if state.priority_player != 3-seat:
        state = prior.act(state, state.priority_player, {'type': 'pass_priority'})
    state = prior.act(state, 3-seat, {'type': 'cast_spell', 'card_id': counter,
                                    'targets': {'target_stack_id': old_id}})
    state = passes(state)
    assert state.cards[salve].zone == Zone.GRAVEYARD
    assert state.stack[-1].id == copy_id
    state = base.finish(prior.reload_exact(state))
    assert len(state.numeric_prevention_shields) == 1
    receipt = state.numeric_prevention_shields[0]
    assert receipt.resolving_stack_id == copy_id and receipt.source_controller == copier
    assert receipt.source_card_id == salve and receipt.source_reference == pre
    assert receipt.remaining == 3 and state.cards[target].counters['__prevent_damage_shield'] == 3


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_player_shield_consumes_partial_and_preserves_remaining(seat):
    from rules_engine.oracle_effects import inspect_target_hints
    state = base.position(seat)
    state.players[seat].mana_pool['G'] = 1
    salve = base.add(state, 'Healing Salve', seat, Zone.HAND)
    mode = next(mode for mode in inspect_target_hints(state, state.cards[salve], seat)['modes'] if mode.startswith('Prevent'))
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': salve,
                                   'targets': {'mode_text': mode, 'target_player': 3-seat}})
    state = base.finish(prior.reload_exact(state))
    state, _ = boundary.announce(state, seat, 'Hornet Sting', {'target_player': 3-seat})
    state = base.finish(prior.reload_exact(state))
    assert state.players[3-seat].life == 20
    assert state.players[3-seat].prevent_damage_shield == 2
    assert state.numeric_prevention_shields[0].remaining == 2
    assert state.numeric_prevention_shields[0].target_player == 3-seat


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_multiplier_then_numeric_shield_then_conversion_requeries_amount(seat):
    state, target = shielded(seat)
    mage = base.add(state, 'Soul-Scar Mage', seat)
    state = prior.paid_spell(state, 'Furnace of Rath', seat)
    furnace = next(cid for cid in state.players[seat].battlefield if state.cards[cid].name == 'Furnace of Rath')
    numeric = 'numeric-prevention:' + state.numeric_prevention_shields[0].receipt_id
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state, _ = base.cast(state, 'Lightning Bolt', seat, target)
    state = base.finish(prior.reload_exact(state))
    state = prior.choose(state, 3-seat, furnace)
    assert state.pending_replacement_choice['amount'] == 6
    state = prior.choose(state, 3-seat, numeric)
    assert state.pending_replacement_choice['amount'] == 3
    state = prior.choose(state, 3-seat, mage)
    assert state.cards[target].counters.get('-1/-1') == 3
    assert not state.cards[target].counters.get('__damage_marked')
    assert not state.cards[target].counters.get('__prevent_damage_shield')
    assert state.players[1].life == state.players[2].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_component_combat_bridge_and_locked_prevention_do_not_desynchronize(seat):
    from rules_engine.combat import _mark_creature_damage
    state, target = shielded(seat)
    assert _mark_creature_damage(state, target, 1) == 0
    assert state.numeric_prevention_shields[0].remaining == 2
    assert state.cards[target].counters['__prevent_damage_shield'] == 2
    prior.reload_exact(state)
    # Explicit core lock boundary, not a fabricated canonical lock spell.
    state.turn_damage_cant_be_prevented = True
    state, _ = base.cast(state, 'Lightning Bolt', seat, target)
    state = base.finish(state)
    assert state.cards[target].counters['__damage_marked'] == 3
    assert state.numeric_prevention_shields[0].remaining == 2
    assert state.cards[target].counters['__prevent_damage_shield'] == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_blink_retires_old_target_shield_without_refresh(seat):
    import json
    from pathlib import Path
    from tests.test_linked_damage_targets import raw_card
    from tests.test_generic_protection_damage import CANONICAL
    state = base.position(seat)
    state.players[seat].mana_pool['G'] = 1
    target = raw_card(state, CANONICAL['White Knight'], 3-seat, Zone.BATTLEFIELD).id
    state = cast_salve(state, seat, target)
    old = deepcopy(state.numeric_prevention_shields[0].target_reference)
    blink = raw_card(state, json.loads((Path(__file__).parent /
        'fixtures/temporary_control_audit/cloudshift.json').read_text()), 3-seat, Zone.HAND).id
    state = prior.act(state, seat, {'type': 'pass_priority'})
    state = prior.act(state, 3-seat, {'type': 'cast_spell', 'card_id': blink,
                                   'targets': {'target_card_id': target}})
    state = base.finish(prior.reload_exact(state))
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].zone_change_sequence == old['zone_change_sequence'] + 2
    assert state.numeric_prevention_shields[0].target_reference == old
    assert not state.cards[target].counters.get('__prevent_damage_shield')
    state, _ = boundary.announce(state, seat, 'Hornet Sting', {'target_card_id': target})
    state = base.finish(prior.reload_exact(state))
    assert state.cards[target].counters.get('__damage_marked') == 1
    assert state.numeric_prevention_shields[0].remaining == 3
    prior.reload_exact(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('amount', [0, -1, True, '3'])
def test_corrupted_real_prevention_amount_rejects_before_pop(seat, amount):
    state, _, target = boundary.setup(seat, mage=False)
    source = base.add(state, 'Mending Hands', seat, Zone.HAND)
    state = prior.act(state, seat, {'type': 'cast_spell', 'card_id': source,
                                  'targets': {'target_card_id': target}})
    state.stack[-1].payload['amount'] = amount
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected):
        resolve_top_of_stack(state)
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_broadcast_legacy_competition_rejects_before_pop(seat):
    state, target = shielded(seat)
    payload = prior.snapshot(state)
    payload.pop('numeric_prevention_shields')
    state = deserialize_match_snapshot(payload)
    base.add(state, 'Soul-Scar Mage', seat)
    state, spell = boundary.announce(state, seat, 'Pyroclasm')
    while state.stack[-1].source_card_id != spell:
        state = prior.act(state, state.priority_player, {'type': 'pass_priority'})
    before = prior.snapshot(state)
    with pytest.raises(ActionRejected, match='Legacy numeric prevention'):
        resolve_top_of_stack(state)
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first, expected', [('Doubling Season', 7), ('Winding Constrictor', 8)])
def test_paid_numeric_consume_then_conversion_counter_pause_exactly_once(seat, first, expected):
    from tests.test_counter_replacements import source as counter_source
    from tests.test_batch_graveyard_publication_audit import assert_private
    state, target = shielded(seat)
    mage = base.add(state, 'Soul-Scar Mage', seat)
    sources = {name: counter_source(state, name, 3-seat).id
               for name in ('Doubling Season', 'Winding Constrictor')}
    state = prior.paid_spell(state, 'Furnace of Rath', seat)
    furnace = next(cid for cid in state.players[seat].battlefield
                   if state.cards[cid].name == 'Furnace of Rath')
    numeric = 'numeric-prevention:' + state.numeric_prevention_shields[0].receipt_id
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    state, spell = base.cast(state, 'Lightning Bolt', seat, target)
    item_id = next(item.id for item in state.stack if item.source_card_id == spell)
    state = base.finish(prior.reload_exact(state))
    state = prior.choose(state, 3-seat, furnace)
    state = prior.choose(state, 3-seat, numeric)
    state = prior.choose(state, 3-seat, mage)
    pending = state.pending_replacement_choice
    assert pending['resume_kind'] == 'counter_event'
    assert pending['resolving_item']['id'] == item_id
    assert state.numeric_prevention_shields[0].remaining == 0
    assert not state.cards[target].counters.get('__prevent_damage_shield')
    state = prior.reload_exact(state)
    choice = next(option['source_id'] for option in state.pending_replacement_choice['options']
                  if option['source_card_id'] == sources[first])
    state = prior.choose(state, 3-seat, choice)
    assert not state.pending_replacement_choice
    assert state.cards[target].zone == Zone.GRAVEYARD
    assert state.cards[target].last_known_battlefield['counters']['-1/-1'] == expected
    assert state.numeric_prevention_shields[0].remaining == 0
    assert state.players[1].life == state.players[2].life == 20
    assert_private(prior.reload_exact(state))
