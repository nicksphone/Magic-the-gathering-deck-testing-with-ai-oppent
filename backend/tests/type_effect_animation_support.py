"""Pure animation fixtures shared without importing API test modules."""
import json
from copy import copy
from pathlib import Path

from effects.registry import resolve_effect
from game_state.state import Zone, assign_static_order_on_battlefield_entry, MatchFactory
from rules_engine.oracle_effects import infer_effect_from_oracle

ROWS = {row['name']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/type_effect_lifecycle.json').read_text())}


def permanent(state, name, seat=1):
    sample = MatchFactory.from_decks([{**ROWS[name], 'card_name': name, 'quantity': 1}], [], seed=7)
    card = next(iter(sample.cards.values()))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(Zone.BATTLEFIELD)
    state.cards[card.id] = card
    state.players[seat].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def animate(state, land, seat):
    source = permanent(state, 'Nissa, Who Shakes the World', seat)
    surface = copy(source)
    surface.oracle_text = next(line.split(':', 1)[1].strip() for line in source.oracle_text.splitlines()
                              if line.startswith('+1:'))
    surface.types = []
    key, payload = infer_effect_from_oracle(state, surface, seat, {'target_card_id': land.id})
    assert key == 'add_counters' and payload['animate_land']
    resolve_effect(state, seat, key, {**payload, '__source_card_id': source.id})
    return source
