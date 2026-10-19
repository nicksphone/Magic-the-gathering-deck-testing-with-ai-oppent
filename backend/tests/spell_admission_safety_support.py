"""Full canonical admission facts; no effect or Oracle rewriting."""
from copy import deepcopy
import json
from pathlib import Path
from game_state.state import MatchFactory, Zone
from tests.extra_sequence_support import position, facts, resume
from tests.readiness_rules_seam_support import normalize

FIXTURE = Path(__file__).parent / 'fixtures/spell_admission_safety'
RAW = json.loads((FIXTURE / 'canonical.json').read_text())
UNSUPPORTED = ("Day's Undoing", 'Worst Fears', 'Temporal Mastery', 'Relentless Assault')


def canonical(name):
    row = {**deepcopy(RAW[name]), 'card_name': name, 'quantity': 1}
    if row.get('card_faces'):
        row.update({k: v for k, v in row['card_faces'][0].items()
                    if k in {'mana_cost', 'type_line', 'oracle_text', 'power', 'toughness', 'loyalty'}})
    return row


def add(state, name, seat, zone=Zone.HAND):
    sample = MatchFactory.from_decks([canonical(name)], [], seed=7214)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    card.entered_turn = state.turn
    card.summoning_sick = 'Creature' in card.types
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def seed_cache(repo):
    for raw in RAW.values():
        repo.upsert_card(normalize(raw))
