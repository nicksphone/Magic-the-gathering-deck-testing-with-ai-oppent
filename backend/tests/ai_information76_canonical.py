"""Full verified official inputs for the six AI-fixture modules only."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from tests.library_canonical_fixtures import PRINTED

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES_SHA = '13d4e2a89efbaf1f43d048222aa7c1681b78ca3cb9e42d35267cd990f3b32c1c'


def raw_card(name):
    data = (FIXTURES / 'ai_information76/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCES_SHA
    record = json.loads(data)[name]
    data = (FIXTURES / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['sha256']
    proof = (FIXTURES / record['provenance']).read_bytes()
    assert hashlib.sha256(proof).hexdigest() == record['provenance_sha256']
    if 'line' in record:
        data = data.splitlines()[record['line'] - 1]
        assert hashlib.sha256(data).hexdigest() == record['row_sha256']
    raw = json.loads(data)
    if 'key' in record:
        raw = raw[record['key']]
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    return raw


def deck_entry(name, quantity):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    return {**raw, **normalized, 'card_name': name, 'quantity': quantity,
            'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}


def canonical_card(name, **pose):
    if PRINTED.intersection(pose):
        raise ValueError('Printed fields are not runtime poses')
    sample = MatchFactory.from_decks([deck_entry(name, 8)], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **pose})


def symmetric_deck(name, seed):
    # The original first dealt ID is p1-060. Put its real printed card in the
    # corresponding unshuffled slot, before stock capture and the actual shuffle.
    order = list(range(60))
    random.Random(seed).shuffle(order)
    spell_slot = order[-1]
    return [deck_entry(name if index == spell_slot else 'Island', 1)
            for index in range(60)]


def add_restriction(state, name, player=1):
    card = canonical_card(name, id=state.allocate_object_id(), owner=player,
                          controller=player, zone=Zone.BATTLEFIELD)
    state.cards[card.id] = card
    state.players[player].battlefield.append(card.id)
    assign_static_order_on_battlefield_entry(state, card.id)
    return card


def foretell_setup(seat=1):
    # Same pure position as variable_mana.clean -> foretell.setup, without
    # importing that test module's unrelated HTTP fixtures.
    deck = [deck_entry('Swamp', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=941)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool.clear()
        player.snow_mana_pool.clear()
    card = canonical_card('Behold the Multiverse', id=state.allocate_object_id(),
                          owner=seat, controller=seat, zone=Zone.HAND)
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool = {'C': 2}
    return state, card.id
