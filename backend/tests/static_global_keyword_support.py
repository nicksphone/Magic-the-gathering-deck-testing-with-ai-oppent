"""Canonical static-global audit setup; zone seams are not blink certification."""
import json
from pathlib import Path

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.extra_sequence_support import position
from tests.test_linked_damage_targets import raw_card

FIXTURE = Path(__file__).parent / 'fixtures/static_global_keywords'
RAW = json.loads((FIXTURE / 'canonical.json').read_text())
FAMILIES = (('Absolute Law', 'red'), ('Absolute Grace', 'black'))


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    card = raw_card(state, RAW[name], seat, zone)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
    return card


def cast(state, name, seat, targets=None):
    card = add(state, name, seat, Zone.HAND)
    state.priority_player = seat
    state.players[seat].mana_pool = dict.fromkeys(('W', 'U', 'B', 'R', 'G', 'C'), 10)
    state = checked_action(state, RulesEngine(), seat, {
        'type': 'cast_spell', 'card_id': card.id, 'targets': targets or {}})
    while state.stack:
        assert resolve_top_of_stack(state)
    return state, card.id


def board(seat, name, *, resolve_source=True):
    state = position(seat)
    targets = [add(state, 'Grizzly Bears', owner).id for owner in (1, 2)]
    if resolve_source:
        state, source = cast(state, name, seat)
        assert state.cards[source].zone == Zone.BATTLEFIELD
    else:
        source = add(state, name, seat).id
    return state, source, targets


def zone_seam(state, cid, zone):
    """Controlled incarnation seam, explicitly not a paid blink/reanimation."""
    card = state.cards[cid]
    getattr(state.players[card.controller], card.zone.value).remove(cid)
    card.move_to_zone(zone)
    getattr(state.players[card.controller], zone.value).append(cid)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, cid)
