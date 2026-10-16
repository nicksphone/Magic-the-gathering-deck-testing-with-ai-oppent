"""Pinned full RAW and genuine factory births for graveyard-batch goldens."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine


BACKEND = Path(__file__).resolve().parents[1]
SOURCES = json.loads((BACKEND / 'tests/fixtures/graveyard_batch_native_bf62/SOURCES.json').read_text())


def raw_card(name):
    source = SOURCES[name]
    data = (BACKEND / source['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == source['sha256']
    value = json.loads(data.splitlines()[source['line'] - 1]) if source['line'] else json.loads(data)
    for key in source['steps']:
        value = value[key]
    assert value['object'] == 'card' and value['name'] == name
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == source['raw_row_sha256']
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


def locate(state, name, owner=1):
    return next(card.id for card in state.cards.values() if card.owner == owner and card.name == name)


def place(state, name, zone, owner=1, *, controller=None):
    cid = locate(state, name, owner)
    card = state.cards[cid]
    for player in state.players.values():
        for field in ('hand', 'library', 'graveyard', 'exile', 'battlefield'):
            values = getattr(player, field)
            if cid in values:
                values.remove(cid)
    card.move_to_zone(zone)
    card.controller = owner if controller is None else controller
    recipient = card.controller if zone == Zone.BATTLEFIELD else owner
    getattr(state.players[recipient], zone.value).append(cid)
    return cid


def cast_vaults(state, caster):
    cid = place(state, 'Open the Vaults', Zone.HAND, caster)
    state.priority_player = caster
    state.players[caster].mana_pool.update(C=4, W=2)
    state = checked_action(state, RulesEngine(), caster, {'type': 'cast_spell', 'card_id': cid})
    return state, cid


def snapshot(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def choose(state, actor, choice):
    return checked_action(state, RulesEngine(), actor,
                          {'type': 'choose_mechanic', 'choice_id': choice})
