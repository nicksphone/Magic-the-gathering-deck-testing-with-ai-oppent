"""Unmodified locally pinned canonical fixtures for scheduler acceptance."""
from copy import deepcopy
import json
from pathlib import Path

from game_state.state import MatchFactory, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.extra_sequence_support import position, facts, resume
from tests.readiness_rules_seam_support import normalize

FIXTURE = Path(__file__).parent / 'fixtures/queued_sequence'
RAW = json.loads((FIXTURE / 'canonical.json').read_text())


def add(state, name, seat, zone=Zone.HAND):
    row = deepcopy(RAW[name])
    if row.get('card_faces'):
        row.update(row['card_faces'][0])
    sample = MatchFactory.from_decks([{**row, 'card_name': name, 'quantity': 1}], [], seed=7214)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    card.entered_turn = state.turn
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def act(state, seat, action):
    return checked_action(state, RulesEngine(), seat, action)


def cast(state, name, seat, targets=None):
    card = add(state, name, seat)
    return act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
                             'targets': targets or {}}), card.id


def seed_cache(repo):
    for row in RAW.values():
        repo.upsert_card(normalize(row))
