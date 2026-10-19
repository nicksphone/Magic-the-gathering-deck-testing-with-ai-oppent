"""Original six formerly-red assertions, copied byte-for-byte without weakening."""
from copy import deepcopy
import json
import os
import pytest
import inventory as inv
from domain_paid_support import position, add, act, cast, restore, resolve, respond, receipt
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from rules_engine.domain import basic_land_type_count
from rules_engine.mana import mana_value
from rules_engine.stack_engine import resolve_top_of_stack
FAMILIES = ['Searing Blaze', 'Herd Migration', 'Leyline Binding', 'Sunfall', 'Chrome Host Seedshark']
PHASE = os.environ.get('ADMISSION_PHASE', 'before')
OUT = inv.ROOT.parent / 'evidence'

@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raws = {name: selected[card['scryfall_id']] for name, card in seed.items()}
    for name in FAMILIES:
        assert raws[name]['oracle_text'] == seed[name]['oracle_text']
    with (OUT / ('facts-' + PHASE + '.json')).open('x') as stream:
        json.dump({'source': proof, 'cards': {name: raws[name] for name in FAMILIES}}, stream, indent=2)
    return raws


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('find', [False, True])
def test_paid_domain_hand_ability_search_reveal_shuffle_and_life(facts, seat, find):
    state = position(facts, seat)
    source = add(state, facts, 'Herd Migration', seat, Zone.HAND)
    basic = add(state, facts, 'Forest', seat, Zone.LIBRARY)
    nonbasic = add(state, facts, 'Hallowed Fountain', seat, Zone.LIBRARY)
    state.players[seat].mana_pool = {'C': 1, 'G': 1}
    life = state.players[seat].life
    state = act(state, seat, 'activate_ability', card_id=source, ability_index=0)
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert sum(state.players[seat].mana_pool.values()) == 0
    receipt(f'herd-hand-compiled-{seat}-{find}', facts, ['Herd Migration'], state,
            paid_C=1, paid_G=1, stack=serialize_match_snapshot(state)['stack'])
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'search_library'
    assert nonbasic not in state.pending_mechanic_choice['options']
    state = restore(state)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        act(state, seat, 'choose_mechanic', card_ids=[nonbasic])
    assert serialize_match_snapshot(state) == before
    state = act(state, seat, 'choose_mechanic', card_ids=[basic] if find else [])
    assert state.cards[basic].zone == (Zone.HAND if find else Zone.LIBRARY)
    receipt(f'herd-hand-observed-{seat}-{find}', facts, ['Herd Migration'], state,
            life_before=life, life_after=state.players[seat].life,
            stack=serialize_match_snapshot(state)['stack'])
    assert state.players[seat].life == life + 3
    assert not state.stack and state.pending_mechanic_choice is None
    receipt(f'herd-hand-{seat}-{find}', facts, ['Herd Migration'], state, life_gain=3, selected_basic=find)


@pytest.mark.parametrize('seat', [1, 2])
def test_paid_domain_discount_and_linked_nonland_trigger(facts, seat):
    state = position(facts, seat)
    source = add(state, facts, 'Leyline Binding', seat, Zone.HAND)
    target = add(state, facts, 'Torrential Gearhulk', 3-seat)
    own = add(state, facts, 'Torrential Gearhulk', seat)
    land = add(state, facts, 'Mountain', 3-seat)
    add(state, facts, 'Hallowed Fountain', seat)
    add(state, facts, 'Mountain', seat)
    yavi = add(state, facts, 'Yavimaya, Cradle of Growth', seat, Zone.HAND)
    state = act(state, seat, 'play_land', card_id=yavi)
    assert basic_land_type_count(state, seat) == 4
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    state = cast(state, seat, source)
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert mana_value(state.cards[source].mana_cost) == 6
    resolve(state)
    assert state.pending_trigger_order['phase'] == 'targets'
    sid = state.pending_trigger_order['current_stack_id']
    for invalid in (land, own):
        before = serialize_match_snapshot(state)
        with pytest.raises(ActionRejected):
            act(state, seat, 'choose_trigger_target', stack_id=sid, target_card_id=invalid)
        assert serialize_match_snapshot(state) == before
    state = act(restore(state), seat, 'choose_trigger_target', stack_id=sid, target_card_id=target)
    receipt(f'leyline-trigger-{seat}', facts, ['Leyline Binding'], state,
            stack=serialize_match_snapshot(state)['stack'])
    resolve(state)
    assert state.cards[target].zone == Zone.EXILE
    assert state.cards[source].zone == Zone.BATTLEFIELD
    linked_before = deepcopy(state.linked_exiles)
    removal = add(state, facts, 'Boseiju, Who Endures', 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'C': 1, 'G': 1}
    state = act(respond(state, 3-seat), 3-seat, 'activate_ability', card_id=removal,
                ability_index=1, targets={'target_card_id': source})
    assert sum(state.players[3-seat].mana_pool.values()) == 0
    resolve_top_of_stack(state)
    if state.pending_mechanic_choice:
        assert state.pending_mechanic_choice['kind'] == 'optional_search'
        state = act(state, seat, 'choose_mechanic', card_ids=['decline'])
    assert state.cards[source].zone == Zone.GRAVEYARD
    receipt(f'leyline-return-observed-{seat}', facts, ['Leyline Binding'], state,
            linked_before=linked_before, source_zone=state.cards[source].zone.value,
            target_zone=state.cards[target].zone.value, removal_paid_C=1, removal_paid_G=1)
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert not state.linked_exiles
    receipt(f'leyline-{seat}', facts, ['Leyline Binding'], state, domain=4, paid_C=1, paid_W=1, target_returned=True)

