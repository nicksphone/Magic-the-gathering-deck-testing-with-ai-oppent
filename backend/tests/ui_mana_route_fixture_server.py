"""Canonical trusted mana positions for the real App/API, not played games."""
from copy import deepcopy
import json

from fastapi import HTTPException
from game_state.state import MatchFactory, Step, Zone
from tests.browser_fixture_server import app, publish, ACTIVE_MATCHES
from tests.browser_positive83_canonical import entry


def register_mana_route_fixtures():
    scenes = {}

    @app.middleware('http')
    async def record_mana_actions(request, call_next):
        scene = next((value for match_id, value in scenes.items()
                      if request.url.path == f'/matches/{match_id}/action'), None)
        if request.method != 'POST' or scene is None:
            return await call_next(request)
        receipts = scene['receipts']
        if len(receipts) >= 8:
            raise RuntimeError('Built-App mana receipt limit exceeded')
        # Same cached-body pass-through pattern as the qualified PR38 helper.
        body = await request.body()
        response = await call_next(request)
        try:
            payload = json.loads(body)
        except ValueError:
            payload = None
        receipts.append({'body': payload, 'status': response.status_code})
        return response

    @app.post('/fixture/built-app-mana')
    def setup(seat: int = 1):
        if seat not in (1, 2):
            raise HTTPException(422, 'Expected seat 1 or 2')
        # Existing reader verifies complete RAW/provenance, then normalizes BEFORE birth.
        deck = [entry('Island', 59), entry('Sol Ring')]
        state = MatchFactory.from_decks(deck, deck, seed=46)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.turn = 5
        state.active_player = state.priority_player = seat
        state.step = Step.PRECOMBAT_MAIN
        sources = {}
        for pid, player in state.players.items():
            for cid in list(player.hand):
                player.hand.remove(cid)
                player.library.append(cid)
                state.cards[cid].move_to_zone(Zone.LIBRARY)

            def move(name):
                cid = next(cid for cid in player.library if state.cards[cid].name == name)
                player.library.remove(cid)
                player.battlefield.append(cid)
                state.cards[cid].move_to_zone(Zone.BATTLEFIELD)
                return cid

            # Only the pose changes; printed facts, native IDs and allocator stay genuine.
            lands = [move('Island') for _ in range(3)]
            sources[pid] = {'lands': lands, 'ring': move('Sol Ring')}
        state.log.append('Trusted built-App mana position; not a played-game checkpoint.')
        publish(state, deck, capture_original_stock=False, mainboards={1: deck, 2: deck})
        scenes.clear()
        scenes[state.id] = {'sources': sources, 'receipts': []}
        return {'id': state.id, 'land_ids': sources[seat]['lands'],
                'ring_id': sources[seat]['ring']}

    @app.get('/fixture/built-app-mana/{match_id}/facts')
    def facts(match_id: str):
        if match_id not in scenes or match_id not in ACTIVE_MATCHES:
            raise HTTPException(404, 'Unknown built-App mana fixture')
        scene = scenes[match_id]
        state = ACTIVE_MATCHES[match_id].state
        players = {}
        for pid, player in state.players.items():
            sources = scene['sources'][pid]
            players[pid] = {
                'land_tapped': {cid: state.cards[cid].tapped for cid in sources['lands']},
                'ring_tapped': state.cards[sources['ring']].tapped,
                'pool': deepcopy(player.mana_pool),
                'snow_pool': deepcopy(player.snow_mana_pool),
                'restricted_pool': deepcopy(player.restricted_mana_pool),
                'battlefield_ids': list(player.battlefield),
                'source_zones': {cid: state.cards[cid].zone.value
                                 for cid in [*sources['lands'], sources['ring']]},
                'hand_count': len(player.hand), 'library_count': len(player.library),
                'graveyard_count': len(player.graveyard), 'exile_count': len(player.exile),
                'life': player.life, 'counters': deepcopy(player.counters),
                'spells_cast': state.spells_cast_this_turn[pid],
            }
        return {'action_requests': deepcopy(scene['receipts']), 'players': players,
                'stack_size': len(state.stack),
                'position': {'active_player': state.active_player,
                             'priority_player': state.priority_player,
                             'step': state.step.value, 'turn': state.turn,
                             'winner': state.winner}}
