"""Additional pinned RAW; the frozen 55-case support stays byte-identical."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from game_state.state import MatchFactory, Step, Zone
from tests.graveyard_batch_native_support_bf62 import raw_card as original_raw_card


BACKEND = Path(__file__).resolve().parents[1]
SOURCES = json.loads((BACKEND / 'tests/fixtures/graveyard_batch_boundary_bf62/SOURCES.json').read_text())


def raw_card(name):
    if name not in SOURCES:
        return original_raw_card(name)
    row = SOURCES[name]
    data = (BACKEND / row['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['sha256']
    value = json.loads(data)
    assert value['object'] == 'card' and value['name'] == name
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == row['raw_row_sha256']
    return value


def position(first=(), second=(), *, active=1):
    def deck(names):
        counts = Counter(names)
        counts['Island'] += 60 - sum(counts.values())
        return [{**raw_card(name), 'card_name': name, 'quantity': count}
                for name, count in counts.items() if count]
    state = MatchFactory.from_decks(deck(first), deck(second), seed=719)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = active
    state.step = Step.PRECOMBAT_MAIN
    return state


def place_all(state, name, owner=1):
    ids = [card.id for card in state.cards.values() if card.name == name and card.owner == owner]
    for cid in ids:
        for player in state.players.values():
            for field in ('hand', 'library', 'graveyard', 'exile', 'battlefield'):
                values = getattr(player, field)
                if cid in values:
                    values.remove(cid)
        card = state.cards[cid]
        card.move_to_zone(Zone.BATTLEFIELD)
        card.controller = owner
        state.players[owner].battlefield.append(cid)
    return ids
