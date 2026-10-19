"""Native frame provenance only; upstream delayed-cast semantics remain RED."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry, object_incarnation
from tests.test_graveyard_self_activation_product import position, FAMILIES, raw_card, act, snapshot
from test_mixed_entry_origin_audit import ROWS, finish_priority

HERE = Path(__file__).resolve().parents[1]
UNSUMMON = json.loads((HERE / 'fixtures/unsummon.json').read_text())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('depart', [False, True])
def test_real_published_frame_retains_source_pre_after_paid_bounce(request, seat, depart):
    state, _ = position(seat, FAMILIES[0])
    for cid in list(state.players[seat].library[:4]):
        state.players[seat].library.remove(cid)
        state.players[seat].battlefield.append(cid)
        state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
        assign_static_order_on_battlefield_entry(state, cid)
        state.cards[cid].summoning_sick = False
    source = raw_card(state, ROWS['Summon: Fenrir'], seat, Zone.HAND)
    response = raw_card(state, UNSUMMON, seat, Zone.HAND)
    state.players[seat].mana_pool = {'G': 1, 'C': 2}
    state = finish_priority(act(state, seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}}))
    for _ in range(96):
        item = next((item for item in state.stack if item.source_card_id == source.id
                     and item.payload.get('__chapter_number') == 2), None)
        if item:
            break
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert item is not None
    publication = deepcopy(item.payload['__one_shot_publication'])
    assert publication['reference'] == {
        'incarnation': object_incarnation(state.cards[source.id]),
        'zone_change_sequence': state.cards[source.id].zone_change_sequence, 'zone': 'battlefield'}
    assert publication['oracle_text'] == ROWS['Summon: Fenrir']['oracle_text']
    if depart:
        state = act(state, seat, {'type': 'cast_spell', 'card_id': response.id,
                                 'targets': {'target_card_id': source.id}})
        state = act(state, state.priority_player, {'type': 'pass_priority'})
        state = act(state, state.priority_player, {'type': 'pass_priority'})
        assert state.cards[source.id].zone == Zone.HAND
    state = finish_priority(state)
    packet = state.pending_entry_counters[0]
    origin = packet['__entry_origin']
    assert origin['publication'] == publication
    assert origin['controller'] == seat and origin['frame']['controller'] == seat
    assert origin['frame']['source_card_id'] == source.id
    assert origin['child_position'] is None
    assert origin['semantic_qualification'] == 'upstream_not_certified'
    assert origin['frame']['payload']['__chapter_clause'] == publication['clause']
    if depart:
        assert publication['reference']['zone_change_sequence'] < state.cards[source.id].zone_change_sequence
    target = Path(os.environ['MTG_ONE_SHOT_EVIDENCE']) / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    with target.open('x') as f:
        json.dump({'scope': 'actual origin provenance, NOT correct delayed next-cast episode',
                   'publication': publication, 'origin': origin, 'after': snapshot(state)}, f,indent=2,sort_keys=True)
