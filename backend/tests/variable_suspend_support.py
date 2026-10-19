"""Full canonical intake and diagnostic positions, never synthetic Oracle."""
from copy import deepcopy
import json
from pathlib import Path
import re

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone
from rules_engine.oracle_text import without_reminder_text

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).parent / 'fixtures/variable_suspend_canonical'
PROVENANCE = json.loads((DIRECTORY / 'provenance.json').read_text())
RAW = {row['name']: json.loads((ROOT / row['path']).read_bytes()) for row in PROVENANCE['canonical_cards']}
NAMES = list(RAW)
RIFT = json.loads((Path(__file__).parent / 'fixtures/suspend_canonical/rift-bolt.json').read_bytes())
CONTROL_DIRECTORY = Path(__file__).parent / 'fixtures/canonical_land_animation_audit'
NONBASIC = json.loads((CONTROL_DIRECTORY / 'mutavault.json').read_bytes())


def printed_cost(name):
    line = next(line for line in without_reminder_text(RAW[name]['oracle_text']).splitlines()
                if line.startswith('Suspend '))
    return ''.join(re.findall(r'\{[^}]+\}', line))


def position(name, seat=1):
    row = {**deepcopy(RAW[name]), 'card_name': name, 'quantity': 1}
    deck = [row, {**RIFT, 'card_name': RIFT['name'], 'quantity': 4}]
    state = MatchFactory.from_decks(deck if seat == 1 else [], deck if seat == 2 else [], seed=1719)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    state.turn = 5
    state.mechanic_choice_players = {1, 2}
    state.trigger_order_choice_players = {1, 2}
    card = next(card for card in state.cards.values() if card.name == name)
    for cid in list(state.players[seat].hand):
        if cid != card.id:
            state.players[seat].hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            state.players[seat].library.append(cid)
    state.players[seat].mana_pool = {'C': 6, RAW[name]['colors'][0]: 1}
    return state, card.id


def exile_position(name, seat=1, count=2):
    # A diagnostic pre-existing position, NOT a claimed legal Suspend-X workflow.
    state, cid = position(name, seat)
    state.players[seat].hand.remove(cid)
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(cid)
    state.cards[cid].counters['time'] = count
    return state, cid


def resume(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def nonbasic_target(state, seat, zone=Zone.BATTLEFIELD):
    raw = {**NONBASIC, 'card_name': NONBASIC['name'], 'quantity': 1}
    sample = MatchFactory.from_decks([raw], [], seed=1719)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card
