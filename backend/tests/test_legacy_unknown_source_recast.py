"""Historical-frame finisher safety seam, not a naturally played LIFO history.

The newly cast spell normally resolves before an older ability. We explicitly
select the older finisher to test its provenance contract (e.g. resumed legacy
frames); no claim is made that ordinary priority can reorder these frames.
"""
import json
from pathlib import Path

import pytest

from effects.handlers import return_permanent_to_hand
from game_state.state import StackItem, Zone, object_incarnation
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import finish_stack_resolution
from rules_engine.targeting import stack_object_kind
from tests.test_activation_modifiers import ROWS
from tests.test_linked_damage_targets import raw_card
from tests.test_stack_publication_provenance import position


class LegacySourceCleanupMismatch(AssertionError):
    pass


def old_frame_and_recast(seat, kind):
    state = position(seat)
    raw_card(state, json.loads((Path(__file__).parent/'fixtures/global_flash_timing_audit/vedalken-orrery.json').read_text()), seat, Zone.BATTLEFIELD)
    source = raw_card(state, ROWS['Azure Mage'], seat, Zone.BATTLEFIELD)
    original_reference = (object_incarnation(source), source.zone_change_sequence)
    # Deliberate historical storage input: no kind or retained-source evidence.
    payload = {'amount': 1, 'target_player': seat}
    if kind == 'activated':
        payload['__announced_stack_kind'] = 'activated'
    old = StackItem('historical-ability', source.id, seat, 'Historical draw ability', 'draw_cards', payload)
    state.stack.append(old)
    return_permanent_to_hand(state, seat, {'target_card_id': source.id})
    state.players[seat].mana_pool.update({'U': 1, 'C': 1})
    state = checked_action(state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source.id})
    source = state.cards[source.id]
    assert source.zone == Zone.STACK
    assert (object_incarnation(source), source.zone_change_sequence) != original_reference
    fresh = state.stack[-1]
    assert fresh.id != old.id and fresh.source_card_id == old.source_card_id
    assert stack_object_kind(state, fresh) == 'spell'
    old = next(item for item in state.stack if item.id == old.id)
    assert stack_object_kind(state, old) == ('legacy_unknown' if kind == 'legacy' else kind)
    return state, old, fresh, source


@pytest.mark.parametrize('seat', [1, 2])
def test_typed_ability_finisher_preserves_distinct_recast_spell(seat):
    state, old, fresh, source = old_frame_and_recast(seat, 'activated')
    state.stack.remove(old)  # Explicit finisher seam; not a legal LIFO transition.
    assert finish_stack_resolution(state, old, dict(old.payload))
    assert source.zone == Zone.STACK and state.stack == [fresh]
    assert source.id not in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.xfail(strict=True, raises=LegacySourceCleanupMismatch,
                   reason='finish_stack_resolution legacy_unknown seam lacks proof of the source stack incarnation')
def test_untyped_historical_finisher_must_not_move_distinct_recast_spell(seat):
    state, old, fresh, source = old_frame_and_recast(seat, 'legacy')
    state.stack.remove(old)
    assert finish_stack_resolution(state, old, dict(old.payload))
    assert state.stack == [fresh]  # The separate spell frame remains pending.
    if source.zone == Zone.BATTLEFIELD:
        raise LegacySourceCleanupMismatch('Older untyped frame entered a distinct recast source while its spell remains pending')
    assert source.zone == Zone.STACK
    assert source.id not in state.players[seat].battlefield
