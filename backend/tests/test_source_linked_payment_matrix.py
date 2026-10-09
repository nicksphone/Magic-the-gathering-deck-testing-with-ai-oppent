"""Actual canonical exile casts on explicitly declared physical resource boards."""
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_source_linked_exile import (
    ROOT, position, activate, raw_card, FACTS, ROWS, action, cast,
    snap, Zone, exile_permission, deserialize_match_snapshot, resolve_top_of_stack,
)
from rules_engine.action_validation import ActionRejected

DIRECTORY = Path(__file__).resolve().parent/'fixtures/source_linked_exile'
EXTRA = {r['name']: r for r in json.loads((DIRECTORY/'payment-facts.json').read_bytes())}
assert hashlib.sha256((DIRECTORY/'payment-facts.json').read_bytes()).hexdigest() == '9363fcad6ae30163aec89d88a1f4b7f81995b9ab65fe2a13af0207022f84bab4'
data = (ROOT/'backend/tests/fixtures/cast_resources/canonical.json').read_bytes()
assert hashlib.sha256(data).hexdigest() == json.loads((ROOT/'backend/tests/fixtures/cast_resources/provenance.json').read_bytes())['sha256']
RESOURCE = {r['name']: r for r in json.loads(data)['data']}
SNOW = next(r for r in json.loads((ROOT/'backend/tests/fixtures/additive_mana.json').read_bytes()) if r['name'] == 'Snow-Covered Forest')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['true_c', 'missing_c', 'snow', 'missing_snow',
                                 'convoke', 'wrong_convoke_color', 'improvise', 'delve'])
def test_actual_exile_cast_payment_matrix(case, seat):
    state, source = position(seat)
    choices = None
    resources = []
    target = None
    if case in {'true_c', 'missing_c'}:
        raw = EXTRA['Spatial Contortion']
        target = raw_card(state, FACTS['Elvish Mystic'], seat, Zone.HAND)
        state = cast(state, seat, target.id)
    elif case in {'snow', 'missing_snow'}:
        raw = EXTRA['Icehide Golem']
    elif case in {'convoke', 'wrong_convoke_color'}:
        raw = RESOURCE['Siege Wurm']
        for _ in range(2):
            payer = raw_card(state, FACTS['Elvish Mystic'], seat, Zone.HAND)
            state = cast(state, seat, payer.id)
            resources.append(payer.id)
        choices = {'convoke': [{'card_id': cid, 'pay_as': 'U' if case == 'wrong_convoke_color' else 'G'} for cid in resources]}
    elif case == 'improvise':
        raw = RESOURCE['Reverse Engineer']
        payer = raw_card(state, FACTS['Shuko'], seat, Zone.HAND)
        state = cast(state, seat, payer.id)
        resources = [payer.id]
        choices = {'improvise': resources}
    else:
        raw = RESOURCE['Hooting Mandrills']
        payer = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.HAND)
        state = cast(state, seat, payer.id, {'target_player': 3-seat})
        resources = [payer.id]
        choices = {'delve': resources}
    spell = raw_card(state, raw, 3-seat, Zone.LIBRARY)
    state = activate(state, seat, source, 0)
    assert exile_permission(state, seat, spell.id)
    # Explicit physical resource counterfactuals; canonical spell/entry/cost facts unchanged.
    for cid in state.players[seat].battlefield:
        if 'Land' in state.cards[cid].types:
            state.cards[cid].tapped = True
    state.players[seat].mana_pool = ({'W': 1, 'C': 1} if case == 'true_c' else
                                   {'W': 2} if case == 'missing_c' else
                                   {'C': 4} if case == 'improvise' else
                                   {'C': 1} if case == 'missing_snow' else
                                   {} if case == 'snow' else {'C': 5})
    if case == 'snow':
        land = raw_card(state, SNOW, seat, Zone.HAND)
        state = action(state, seat, {'type': 'play_land', 'card_id': land.id})
    fields = {'type': 'cast_spell', 'card_id': spell.id, 'from_exile': True,
              'targets': {'target_card_id': target.id} if target else {}}
    if choices is not None:
        fields['resource_payment'] = choices
    before = snap(state)
    if case in {'missing_c', 'missing_snow', 'wrong_convoke_color'}:
        with pytest.raises(ActionRejected):
            action(state, seat, fields)
        assert snap(state) == before
        assert all(not state.cards[cid].tapped for cid in resources)
        return
    state = action(state, seat, fields)
    assert state.cards[spell.id].zone == Zone.STACK
    assert state.stack[-1].payload['mana_spent'] == {'true_c': 2, 'snow': 1, 'convoke': 5, 'improvise': 4, 'delve': 5}[case]
    if case in {'convoke', 'improvise'}:
        assert all(state.cards[cid].tapped for cid in resources)
    if case == 'delve':
        assert state.cards[payer.id].zone == Zone.EXILE
        assert not exile_permission(state, seat, payer.id)
    state = deserialize_match_snapshot(snap(state))
    assert resolve_top_of_stack(state)
    assert state.cards[spell.id].zone == (Zone.GRAVEYARD if case in {'true_c', 'improvise'} else Zone.BATTLEFIELD)
    if case in {'snow', 'convoke', 'delve'}:
        assert state.cards[spell.id].owner == 3-seat and state.cards[spell.id].controller == seat
