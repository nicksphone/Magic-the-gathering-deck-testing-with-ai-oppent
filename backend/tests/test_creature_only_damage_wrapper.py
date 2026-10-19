"""Real paid compiler episodes plus explicitly controlled wrapper boundaries."""
from copy import deepcopy
import pytest

from effects import handlers
from effects.registry import EFFECT_HANDLERS
from game_state.state import Zone
from tests import test_soulscar_protection_boundaries as boundary

base = boundary.base
prior = boundary.prior


@pytest.mark.parametrize('seat', [1, 2])
def test_component_effective_membership_and_provenance_forwarded_once(seat, monkeypatch):
    from tests import test_basic_land_layer_goldens as layers
    state = base.position(seat)
    creature = base.add(state, 'Torrential Gearhulk', seat)
    changed = base.add(state, 'Torrential Gearhulk', 3-seat)
    base.add(state, 'Island', seat)
    base.add(state, 'Torrential Gearhulk', seat, Zone.GRAVEYARD)
    # Controlled canonical attachment setup, not a legal Song response episode.
    layers.setter(state, 'Song of the Dryads', seat, state.cards[changed])
    source = base.add(state, 'Lightning Bolt', seat, Zone.HAND)
    lki = {'controller': seat, 'color_names': ['red']}
    payload = {'amount': 2, '__source_card_id': source, '__source_lki': lki}
    before = prior.snapshot(state)
    calls = []
    monkeypatch.setattr(handlers, 'deal_damage_batch', lambda *args: calls.append(args))
    assert EFFECT_HANDLERS['damage_each_creature'] is handlers.damage_each_creature
    handlers.damage_each_creature(state, seat, payload)
    assert len(calls) == 1 and calls[0][:2] == (state, seat)
    assert calls[0][2]['recipients'] == [{'target_card_id': creature, 'amount': 2}]
    assert calls[0][2]['__source_card_id'] == source
    assert calls[0][2]['__source_lki'] is lki
    assert prior.snapshot(state) == before
    assert payload == {'amount': 2, '__source_card_id': source, '__source_lki': lki}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('amount', [0, -1])
def test_component_nonpositive_amount_has_no_batch_or_mutation(seat, amount, monkeypatch):
    state = base.position(seat)
    base.add(state, 'Torrential Gearhulk', seat)
    before = prior.snapshot(state)
    def forbidden(*args):
        pytest.fail('Nonpositive damage must not dispatch a batch')
    monkeypatch.setattr(handlers, 'deal_damage_batch', forbidden)
    handlers.damage_each_creature(state, seat, {'amount': amount})
    assert prior.snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_component_empty_creature_cohort_never_adds_players(seat, monkeypatch):
    state = base.position(seat)
    base.add(state, 'Island', seat)
    calls = []
    monkeypatch.setattr(handlers, 'deal_damage_batch', lambda *args: calls.append(args))
    handlers.damage_each_creature(state, seat, {'amount': 2})
    assert len(calls) == 1 and calls[0][2]['recipients'] == []
    assert state.players[1].life == state.players[2].life == 20


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_animation_response_joins_creature_cohort_at_resolution(seat):
    from tests.test_canonical_land_animation_audit import ROWS, action
    from tests.test_linked_damage_targets import raw_card
    state = base.position(seat)
    state.turn = 5
    land = raw_card(state, ROWS['Mutavault'], seat, Zone.BATTLEFIELD)
    land.summoning_sick = False
    state, spell = boundary.announce(state, seat, 'Pyroclasm')
    assert state.cards[land.id].types == ['Land']
    before_pool = sum(state.players[seat].mana_pool.values())
    state = prior.act(state, seat, action(state.cards[land.id]))
    assert sum(state.players[seat].mana_pool.values()) == before_pool - 1
    assert state.stack[-1].source_card_id == land.id
    state = base.finish(prior.reload_exact(state))
    assert state.cards[land.id].zone == Zone.GRAVEYARD
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.players[1].life == state.players[2].life == 20


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('first', ['protection', 'conversion'])
def test_paid_pyroclasm_pause_restores_frozen_cohort_without_wrapper_reentry(seat, first, monkeypatch):
    from tests.test_batch_graveyard_publication_audit import assert_private
    state, mage, protected = boundary.setup(seat)
    remaining = base.add(state, 'Torrential Gearhulk', 3-seat)
    cohort = [cid for player in state.players.values() for cid in player.battlefield]
    expected_remaining = cohort[cohort.index(protected) + 1:]
    state.replacement_choice_required = True
    state.replacement_choice_players = {3-seat}
    calls = []
    original = handlers.damage_each_creature
    def observe(current, controller, payload):
        calls.append(deepcopy(payload))
        return original(current, controller, payload)
    monkeypatch.setitem(EFFECT_HANDLERS, 'damage_each_creature', observe)
    state, spell = boundary.announce(state, seat, 'Pyroclasm')
    frame = next(item for item in state.stack if item.source_card_id == spell)
    frame_id = frame.id
    state = base.finish(prior.reload_exact(state))
    pending = state.pending_replacement_choice
    assert pending['resume_kind'] == 'damage_batch'
    assert pending['target_card_id'] == protected and pending['player_id'] == 3-seat
    assert pending['resolving_item']['id'] == frame_id
    continuation = pending['continuation_effects'][0]
    assert continuation['effect_key'] == 'deal_damage_batch'
    assert continuation['payload']['recipients'] == [
        {'target_card_id': cid, 'amount': 2} for cid in expected_remaining]
    assert continuation['payload']['__source_card_id'] == spell
    assert continuation['payload']['lifelink_total'] == 0
    assert_private(state)
    state = prior.reload_exact(state)
    # Controlled protocol boundary: no legal action is claimed during a choice.
    # A changed board must not cause the already-computed cohort to refresh.
    late = base.add(state, 'Torrential Gearhulk', 3-seat)
    selected = mage if first == 'conversion' else 'protection:' + protected
    state = prior.choose(state, 3-seat, selected)
    assert len(calls) == 1 and calls[0]['__source_card_id'] == spell
    if first == 'conversion':
        assert state.cards[protected].zone == Zone.GRAVEYARD
        assert state.cards[protected].last_known_battlefield['counters']['-1/-1'] == 2
    else:
        assert state.cards[protected].zone == Zone.BATTLEFIELD
        assert not state.cards[protected].counters.get('-1/-1', 0)
    assert state.cards[remaining].counters.get('-1/-1', 0) == 2
    assert not state.cards[late].counters.get('-1/-1', 0)
    assert not state.cards[late].counters.get('__damage_marked', 0)
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert state.players[1].life == state.players[2].life == 20
    assert not state.pending_replacement_choice and not state.pending_mechanic_choice
    assert_private(prior.reload_exact(state))
