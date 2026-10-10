"""Real cost queries and retained method offers; not paid/native episodes."""
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.costs import casting_method, check_cost_option_available, collect_cost_options
from test_soulless_jailer_query_contract import add, position, pure_scope, rows
from test_soulless_jailer_typed_query import extra_rows


@pytest.fixture(scope='module')
def permissions_rows():
    directory = Path(__file__).parent / 'fixtures/graveyard_permissions'
    raw = (directory / 'limited-permissions.json').read_bytes()
    provenance = json.loads((directory / 'limited-permissions.json.provenance.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == provenance['sha256']
    return {row['name']: row for row in json.loads(raw)['data']}


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('zone', (Zone.GRAVEYARD, Zone.EXILE))
def test_real_complete_method_offers_and_retained_aura_option_recheck(rows, extra_rows, permissions_rows, seat, zone):
    state = position(seat)
    state.players[seat].mana_pool = {'G': 10}
    if zone == Zone.GRAVEYARD:
        add(state, permissions_rows['Muldrotha, the Gravetide'], seat, Zone.BATTLEFIELD)
    card = add(state, extra_rows['Leafcrown Dryad'], seat, zone)
    with pure_scope(state):
        original = collect_cost_options(state, seat, card)
        assert {casting_method(option.id) for option in original} == {'base', 'bestow'}
        retained_aura = next(option for option in original if casting_method(option.id) == 'bestow')
        retained_creature = next(option for option in original if casting_method(option.id) == 'base')
        assert check_cost_option_available(state, seat, card, retained_aura) is True
    add(state, rows['Soulless Jailer'], 3 - seat, Zone.BATTLEFIELD)
    with pure_scope(state):
        offered = collect_cost_options(state, seat, card)
        assert {casting_method(option.id) for option in offered} == {'base'}
        assert check_cost_option_available(state, seat, card, retained_aura) is False
        assert check_cost_option_available(state, seat, card, retained_creature) is True
    # Cost availability is not an exile permission or proof of an actual cast.
    assert card.zone == zone and state.players[seat].mana_pool == {'G': 10}
