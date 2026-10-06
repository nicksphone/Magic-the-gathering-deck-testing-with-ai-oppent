"""Explicit null/non-list other-card resources must not become automatic choices."""
import pytest

from tests.test_mana_executor_choices import position, add, spec
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.mana_abilities import activate_mana_ability


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['sacrifice', 'discard'])
@pytest.mark.parametrize('selected', [None, 'unselected', (), False])
def test_explicit_nonlist_resource_never_infers_other_card(seat, family, selected):
    state = position(seat)
    if family == 'sacrifice':
        source = add(state, 'Phyrexian Tower', seat)
        add(state, 'Llanowar Elves', seat)
        ability = spec(state, source, 'Sacrifice')
        key = 'sacrifice_card_ids'
    else:
        source = add(state, 'Bog Witch', seat)
        add(state, 'Forest', seat, Zone.HAND)
        state.players[seat].mana_pool['B'] = 1
        ability = spec(state, source, 'Discard')
        key = 'discard_card_ids'
    before = serialize_match_snapshot(state)
    assert not activate_mana_ability(state, seat, source.id, ability[0], 'B',
        payment_choices={key: selected})
    assert serialize_match_snapshot(state) == before
