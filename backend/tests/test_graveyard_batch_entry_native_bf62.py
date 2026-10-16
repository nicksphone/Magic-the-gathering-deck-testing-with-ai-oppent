"""Genuine paid spells and retained owner choices, without injected stack items/events."""
from copy import deepcopy

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.graveyard_batch_native_support_bf62 import (
    SOURCES, cast_vaults, choose, locate, place, position, raw_card, snapshot,
)


KEY = 'return_graveyard_permanents_batch'


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_complete_raw_facts_reach_real_factory_and_are_independent(name):
    raw = raw_card(name)
    state = position((name,))
    card = state.cards[locate(state, name)]
    assert card.oracle_text == raw.get('oracle_text', '')
    assert card.mana_cost == raw.get('mana_cost', '')
    assert card.type_line == raw['type_line']
    assert card.owner == card.controller == 1
    assert len([card for card in state.cards.values() if card.owner == 1]) == 60
    changed = raw_card(name)
    changed['legalities']['modern'] = 'test-only-local-mutation'
    assert raw_card(name) == raw
    assert changed is not raw and changed['legalities'] is not raw['legalities']


@pytest.mark.parametrize('caster', [1, 2])
def test_paid_targetless_spell_returns_both_owners_without_old_controller_theft(caster):
    state = position(('Open the Vaults', 'Sol Ring'), ('Open the Vaults', 'Oath of Nissa'), active=caster)
    own = place(state, 'Sol Ring', Zone.GRAVEYARD, controller=2)
    other = place(state, 'Oath of Nissa', Zone.GRAVEYARD, 2, controller=1)
    state, source = cast_vaults(state, caster)
    frame = state.stack[-1]
    assert frame.source_card_id == source and frame.controller == caster and frame.effect_key == KEY
    assert sum(state.players[caster].mana_pool.values()) == 0
    assert frame.targets == []
    assert resolve_top_of_stack(state)
    assert own in state.players[1].battlefield and state.cards[own].controller == 1
    assert other in state.players[2].battlefield and state.cards[other].controller == 2
    assert state.cards[source].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('caster', [1, 2])
def test_noneligible_cards_and_aura_without_preexisting_recipient_stay_in_graveyard(caster):
    state = position(('Open the Vaults', 'Sol Ring', 'Grizzly Bears', 'Rancor', 'Forest'), ('Open the Vaults', 'Ornithopter'), active=caster)
    ids = {name: place(state, name, Zone.GRAVEYARD) for name in ['Sol Ring', 'Grizzly Bears', 'Rancor', 'Forest']}
    coentering = place(state, 'Ornithopter', Zone.GRAVEYARD, 2)
    state, _ = cast_vaults(state, caster)
    assert resolve_top_of_stack(state)
    assert ids['Sol Ring'] in state.players[1].battlefield
    assert coentering in state.players[2].battlefield
    for name in ['Grizzly Bears', 'Rancor', 'Forest']:
        assert ids[name] in state.players[1].graveyard
    assert state.pending_mechanic_choice is None


@pytest.mark.parametrize('caster', [1, 2])
def test_existing_permanent_entry_prohibition_is_not_bypassed(caster):
    state = position(('Open the Vaults', 'Sol Ring', 'Soulless Jailer'), ('Open the Vaults', 'Oath of Nissa'), active=caster)
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    enchantment = place(state, 'Oath of Nissa', Zone.GRAVEYARD, 2)
    place(state, 'Soulless Jailer', Zone.BATTLEFIELD)
    state, _ = cast_vaults(state, caster)
    assert resolve_top_of_stack(state)
    assert artifact in state.players[1].graveyard and enchantment in state.players[2].graveyard


@pytest.mark.parametrize('caster', [1, 2])
def test_owner_aura_choices_are_mandatory_apnap_precommit_and_snapshot_safe(caster):
    state = position(('Open the Vaults', 'Rancor', 'Ornithopter', 'Sol Ring'), ('Open the Vaults', 'Rancor', 'Slippery Bogle'), active=caster)
    recipient = place(state, 'Ornithopter', Zone.BATTLEFIELD)
    foreign_hexproof = place(state, 'Slippery Bogle', Zone.BATTLEFIELD, 2)
    auras = {owner: place(state, 'Rancor', Zone.GRAVEYARD, owner) for owner in (1, 2)}
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    state, source = cast_vaults(state, caster)
    assert not resolve_top_of_stack(state)
    frame_id = state.pending_mechanic_choice['resolving_item']['id']
    for owner in (caster, 3-caster):
        pending = state.pending_mechanic_choice
        assert pending['player_id'] == owner and pending['kind'] == 'loyalty_attachment'
        assert pending['entry_card_id'] == auras[owner]
        assert set(pending['options']) == {recipient, foreign_hexproof}
        assert '__none__' not in pending['options']
        assert pending['resolving_item']['id'] == frame_id
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in [artifact, *auras.values()])
        state = snapshot(state)
        with pytest.raises(ActionRejected):
            choose(state, 3-owner, recipient)
        with pytest.raises(ActionRejected):
            choose(state, owner, '__none__')
        state = choose(state, owner, foreign_hexproof)
    assert state.pending_mechanic_choice is None
    for owner, cid in auras.items():
        assert cid in state.players[owner].battlefield and state.cards[cid].controller == owner
        assert state.cards[cid].attached_to == foreign_hexproof
    assert state.cards[artifact].zone == Zone.BATTLEFIELD and state.cards[source].zone == Zone.GRAVEYARD
    assert snapshot(state).cards[auras[1]].attached_to == foreign_hexproof


@pytest.mark.parametrize('tamper', ['attachment', 'graveyard-reentry'])
def test_stale_retained_reference_rejects_choice_without_partial_batch_commit(tamper):
    state = position(('Open the Vaults', 'Rancor', 'Ornithopter', 'Sol Ring'))
    target = place(state, 'Ornithopter', Zone.BATTLEFIELD)
    aura = place(state, 'Rancor', Zone.GRAVEYARD)
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    state, _ = cast_vaults(state, 1)
    assert not resolve_top_of_stack(state)
    # Deliberate retained-protocol negative: same ID, genuinely different zone visit.
    cid = target if tamper == 'attachment' else artifact
    zone = state.cards[cid].zone
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.cards[cid].move_to_zone(zone)
    before = deepcopy(state)
    with pytest.raises(ActionRejected):
        choose(state, 1, target)
    assert state.rng.getstate() == before.rng.getstate()
    assert all(getattr(state, name) == getattr(before, name)
               for name in state.__dataclass_fields__ if name != 'rng')
    assert state.cards[aura].zone == state.cards[artifact].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('caster', [1, 2])
def test_coentering_observers_see_every_committed_entry_and_native_apnap_order(caster):
    state = position(('Open the Vaults', 'Altar of the Brood', 'Sol Ring'), ('Open the Vaults', 'Eidolon of Blossoms', 'Oath of Nissa'), active=caster)
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    altar = place(state, 'Altar of the Brood', Zone.GRAVEYARD)
    eidolon = place(state, 'Eidolon of Blossoms', Zone.GRAVEYARD, 2)
    oath = place(state, 'Oath of Nissa', Zone.GRAVEYARD, 2)
    state, _ = cast_vaults(state, caster)
    assert resolve_top_of_stack(state)
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in (artifact, altar, eidolon, oath))
    assert len([item for item in state.stack if item.source_card_id == altar]) == 1
    assert len([item for item in state.stack if item.source_card_id == eidolon]) == 2
    controllers = [item.controller for item in state.stack]
    assert controllers == sorted(controllers, key=lambda owner: owner != caster)


@pytest.mark.parametrize('caster', [1, 2])
def test_graveyard_departures_use_preexisting_observers_not_coentering_ones(caster):
    state = position(('Open the Vaults', 'Quintorius, Field Historian', 'Sol Ring', 'Desecrated Tomb'), ('Open the Vaults', 'Ornithopter'), active=caster)
    observer = place(state, 'Quintorius, Field Historian', Zone.BATTLEFIELD)
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    tomb = place(state, 'Desecrated Tomb', Zone.GRAVEYARD)
    creature = place(state, 'Ornithopter', Zone.GRAVEYARD, 2)
    state, _ = cast_vaults(state, caster)
    assert resolve_top_of_stack(state)
    assert all(state.cards[cid].zone == Zone.BATTLEFIELD for cid in (artifact, tomb, creature))
    assert len([item for item in state.stack if item.source_card_id == observer]) == 1
    assert not any(item.source_card_id == tomb for item in state.stack)


@pytest.mark.parametrize('caster', [1, 2])
def test_intrinsic_entry_counters_are_prepared_for_each_owner(caster):
    state = position(('Open the Vaults', 'Triskelion', 'Hardened Scales'), ('Open the Vaults', 'Triskelion'), active=caster)
    first = place(state, 'Triskelion', Zone.GRAVEYARD)
    second = place(state, 'Triskelion', Zone.GRAVEYARD, 2)
    place(state, 'Hardened Scales', Zone.BATTLEFIELD)
    state, _ = cast_vaults(state, caster)
    assert resolve_top_of_stack(state)
    assert state.cards[first].counters['+1/+1'] == 4
    assert state.cards[second].counters['+1/+1'] == 3


@pytest.mark.parametrize('owner', [1, 2])
def test_read_ahead_owner_pause_retains_whole_plan_through_snapshot(owner):
    state = position(('Open the Vaults', 'The Weatherseed Treaty', 'Sol Ring'), ('The Weatherseed Treaty',))
    saga = place(state, 'The Weatherseed Treaty', Zone.GRAVEYARD, owner)
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    state, _ = cast_vaults(state, 1)
    assert not resolve_top_of_stack(state)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'saga_entry' and pending['player_id'] == owner
    assert state.cards[saga].zone == state.cards[artifact].zone == Zone.GRAVEYARD
    state = snapshot(state)
    state = choose(state, owner, '2')
    assert state.cards[saga].zone == state.cards[artifact].zone == Zone.BATTLEFIELD
    assert state.cards[saga].controller == owner and state.cards[saga].counters['__lore'] == 2


@pytest.mark.parametrize('caster', [1, 2])
def test_real_twincast_copy_uses_its_native_controller_frame_and_retains_owner_entry(caster):
    copier = 3-caster
    state = position(('Open the Vaults', 'Twincast', 'Sol Ring'), ('Open the Vaults', 'Twincast', 'Oath of Nissa'), active=caster)
    artifact = place(state, 'Sol Ring', Zone.GRAVEYARD)
    enchantment = place(state, 'Oath of Nissa', Zone.GRAVEYARD, 2)
    state, source = cast_vaults(state, caster)
    original = state.stack[-1].id
    copy_spell = place(state, 'Twincast', Zone.HAND, copier)
    state = checked_action(state, RulesEngine(), caster, {'type': 'pass_priority'})
    state.players[copier].mana_pool.update(U=2)
    state = checked_action(state, RulesEngine(), copier, {'type': 'cast_spell', 'card_id': copy_spell, 'targets': {'target_stack_id': original}})
    assert resolve_top_of_stack(state)
    # Native copy-target machinery may publish a genuine keep/change decision.
    if state.pending_mechanic_choice:
        pending = state.pending_mechanic_choice
        assert pending['player_id'] == copier
        state = choose(state, copier, 'keep')
    copied = state.stack[-1]
    assert copied.id != original and copied.source_card_id == source and copied.controller == copier
    assert resolve_top_of_stack(state)
    assert artifact in state.players[1].battlefield and enchantment in state.players[2].battlefield
    assert state.cards[artifact].controller == 1 and state.cards[enchantment].controller == 2
    state = snapshot(state)
    assert resolve_top_of_stack(state)
    assert state.players[1].battlefield.count(artifact) == state.players[2].battlefield.count(enchantment) == 1


@pytest.mark.parametrize('tamper', ['active-bool', 'incarnation-bool', 'duplicate-id', 'frame-source', 'extra-field'])
def test_retained_plan_strict_types_and_native_frame_reject_tampering(tamper):
    state = position(('Open the Vaults', 'Rancor', 'Ornithopter'))
    target = place(state, 'Ornithopter', Zone.BATTLEFIELD)
    aura = place(state, 'Rancor', Zone.GRAVEYARD)
    state, _ = cast_vaults(state, 1)
    assert not resolve_top_of_stack(state)
    plan = state.pending_mechanic_choice['effect_payload']['__graveyard_batch_plan']
    if tamper == 'active-bool':
        plan['active_player'] = True
    elif tamper == 'incarnation-bool':
        assert plan['entries'][0]['reference']['incarnation'] == 0
        plan['entries'][0]['reference']['incarnation'] = False
    elif tamper == 'duplicate-id':
        plan['entries'].append(deepcopy(plan['entries'][0]))
    elif tamper == 'frame-source':
        plan['frame']['source_card_id'] = 'not-the-native-source'
    else:
        plan['extra'] = True
    before = deepcopy(state)
    with pytest.raises(ActionRejected):
        choose(state, 1, target)
    assert state.rng.getstate() == before.rng.getstate()
    assert all(getattr(state, name) == getattr(before, name)
               for name in state.__dataclass_fields__ if name != 'rng')
    assert state.cards[aura].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('caster', [1, 2])
def test_mixed_aura_and_read_ahead_choices_finish_each_owner_in_apnap_order(caster):
    names = ('Open the Vaults', 'Rancor', 'The Weatherseed Treaty', 'Ornithopter')
    state = position(names, names, active=caster)
    target = place(state, 'Ornithopter', Zone.BATTLEFIELD)
    auras = {owner: place(state, 'Rancor', Zone.GRAVEYARD, owner) for owner in (1, 2)}
    sagas = {owner: place(state, 'The Weatherseed Treaty', Zone.GRAVEYARD, owner) for owner in (1, 2)}
    state, _ = cast_vaults(state, caster)
    assert not resolve_top_of_stack(state)
    for owner in (caster, 3-caster):
        assert state.pending_mechanic_choice['kind'] == 'loyalty_attachment'
        assert state.pending_mechanic_choice['player_id'] == owner
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in [*auras.values(), *sagas.values()])
        state = choose(snapshot(state), owner, target)
        assert state.pending_mechanic_choice['kind'] == 'saga_entry'
        assert state.pending_mechanic_choice['player_id'] == owner
        assert all(state.cards[cid].zone == Zone.GRAVEYARD for cid in [*auras.values(), *sagas.values()])
        state = choose(snapshot(state), owner, '2')
    for owner in (1, 2):
        assert state.cards[auras[owner]].controller == state.cards[sagas[owner]].controller == owner
        assert state.cards[auras[owner]].attached_to == target
        assert state.cards[sagas[owner]].counters['__lore'] == 2
