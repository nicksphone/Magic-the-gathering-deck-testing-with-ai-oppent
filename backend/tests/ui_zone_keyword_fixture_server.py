"""Registration helper for trusted positions, not played-game checkpoints.

Complete RAW files are hash-checked before normalization and physical card birth.
No routes are installed merely by importing this module.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from fastapi import HTTPException
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match
from game_state.state import MatchFactory, Step, Zone
from rules_engine.foretell import can_look
from tests.browser_fixture_server import app, publish, ACTIVE_MATCHES
from tests.browser_positive83_canonical import entry

NINJA_SHA = 'd5c28c0171ed64bf41b2435a9edcf4ebcef7cc5d121e27996c74b9a1a8f41b0f'
NAMES = {'foretell': 'Doomskar', 'cycle_card': 'Hollow One',
         'ninjutsu': 'Ninja of the Deep Hours'}


def register_zone_keyword_fixtures():
    """Register once from ui_v2; use only the fixed, complete offline objects."""
    raw = {}
    for name, relative, expected in (
        ('Doomskar', 'ui_zone_keyword/doomskar.json',
         '49ee32b3f03ee7fed84de52f41d74a0c61b3b0f2ffa35b9646644234bdec0f69'),
        ('Hollow One', 'ui_zone_keyword/hollow-one.json',
         '3df32a84d1c5bf470c1d517905017cf0e450fbbe94545b35f8be4921c9e8c456'),
        ('Ninja of the Deep Hours', 'ninjutsu_canonical/ninja-of-the-deep-hours.json', NINJA_SHA),
    ):
        encoded = (Path(__file__).parent / 'fixtures' / relative).read_bytes()
        if hashlib.sha256(encoded).hexdigest() != expected:
            raise ValueError('Complete RAW pin changed: ' + name)
        raw[name] = json.loads(encoded)
    for name, card in raw.items():
        if (card.get('object') != 'card' or card.get('name') != name
                or not all(card.get(key) for key in ('id', 'oracle_id', 'oracle_text', 'type_line'))):
            raise ValueError('Not a supported canonical RAW object: ' + name)
    scenes = {}

    def target_entry(name):
        value = deepcopy(raw[name])
        normalized = ScryfallSyncService._normalize_payload(value, 'unused:browser-fixture-display')
        return {**value, **normalized, 'card_name': name, 'quantity': 1,
                'image_uri': None, 'colors': deepcopy(value.get('colors', [])),
                'card_faces': deepcopy(value.get('card_faces', []))}

    @app.post('/fixture/zone-keyword')
    def setup(seat: int = 1, kind: str = 'foretell'):
        if seat not in (1, 2) or kind not in NAMES:
            raise HTTPException(422, 'Expected one of three fixed actions and seat 1 or 2')
        name = NAMES[kind]
        deck = [entry('Island', 57 if kind == 'ninjutsu' else 59), target_entry(name)]
        if kind == 'ninjutsu':
            deck.append(entry('Grizzly Bears', 2))
        opponent = [entry('Island', 60)]
        decks = {seat: deck, 3 - seat: opponent}
        state = MatchFactory.from_decks(decks[1], decks[2], seed=45)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.turn = 5
        state.active_player = state.priority_player = seat
        state.step = Step.DECLARE_ATTACKERS if kind == 'ninjutsu' else Step.PRECOMBAT_MAIN
        # Trusted pose ONLY, after genuine complete-RAW normalization/native birth.
        for player in state.players.values():
            for cid in list(player.hand):
                player.hand.remove(cid)
                player.library.append(cid)
                state.cards[cid].move_to_zone(Zone.LIBRARY)
        player = state.players[seat]

        def move(name, zone):
            cid = next(cid for cid in player.library if state.cards[cid].name == name)
            player.library.remove(cid)
            getattr(player, zone.value).append(cid)
            state.cards[cid].move_to_zone(zone)
            state.cards[cid].summoning_sick = False
            return cid

        card_id = move(name, Zone.HAND)
        land_ids = [move('Island', Zone.BATTLEFIELD) for _ in range(2)]
        attacker_ids = [move('Grizzly Bears', Zone.BATTLEFIELD) for _ in range(2)] if kind == 'ninjutsu' else []
        state.log.append('Trusted zone-keyword browser position; not a played-game checkpoint.')
        publish(state, deck, capture_original_stock=False, mainboards=decks)
        scenes.clear()
        scenes[state.id] = (seat, card_id, attacker_ids, land_ids)
        return {'id': state.id, 'card_id': card_id, 'attacker_ids': attacker_ids,
                'attacker_id': attacker_ids[1] if attacker_ids else None}

    @app.get('/fixture/zone-keyword/{match_id}/facts')
    def facts(match_id: str):
        if match_id not in scenes or match_id not in ACTIVE_MATCHES:
            raise HTTPException(404, 'Unknown zone-keyword fixture')
        seat, cid, attacker_ids, lands = scenes[match_id]
        state = ACTIVE_MATCHES[match_id].state
        player, card = state.players[seat], state.cards[cid]
        # Exercise real serializer look permissions, not an invented privacy filter.
        views = [serialize_match(state, look_players=look)['players'][seat]['exile']
                 for look in ([], [3 - seat], [seat])]
        return {
            'zone': card.zone.value, 'face_down': card.exile_face_down,
            'hand_count': len(player.hand), 'library_count': len(player.library),
            'graveyard_count': len(player.graveyard), 'exile_count': len(player.exile),
            'stack_size': len(state.stack), 'priority_player': state.priority_player,
            'step': state.step.value, 'blockers_declared': state.blockers_declared,
            'blocks': state.blocks, 'attackers': state.attackers,
            'attacker_zone': state.cards[attacker_ids[1]].zone.value if attacker_ids else None,
            'first_attacker_zone': state.cards[attacker_ids[0]].zone.value if attacker_ids else None,
            'attack_target': state.attack_targets.get(cid), 'tapped': card.tapped,
            'lands_tapped': sum(state.cards[land].tapped for land in lands),
            'mana_remaining': sum(player.mana_pool.values()),
            'owner_can_look': can_look(card, seat),
            'opponent_can_look': can_look(card, 3 - seat),
            'public_exile_hidden': not any(item['id'] == cid for item in views[0]),
            'opponent_exile_hidden': not any(item['id'] == cid for item in views[1]),
            'owner_exile_visible': any(item['id'] == cid for item in views[2]),
            'name_in_log': any(card.name in line for line in state.log),
            'foretells': state.foretells_this_turn.get(seat, 0),
            'spells_cast': state.spells_cast_this_turn.get(seat, 0),
        }
