"""Availability inventory, not paid resolution or complete-card qualification."""
import hashlib
import json
import os
from pathlib import Path

from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.coverage import known_unsupported_mechanics, static_coverage_details
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_loyalty_abilities


def test_all_shipped_printed_planeswalker_availability():
    seed_path = Path(os.environ['LOYALTY_INVENTORY_SOURCE']) / 'backend/card_data/builtin_oracle_seed.json'
    raw = seed_path.read_bytes()
    cards = json.loads(raw)['cards']
    assert len(cards) == 155
    surfaces = []
    for card in cards.values():
        if 'Planeswalker' in card.get('type_line', ''):
            surfaces.append((card['name'], None, card))
        for index, face in enumerate(card.get('card_faces') or []):
            if 'Planeswalker' in face.get('type_line', ''):
                surfaces.append((card['name'], index, face))
    assert len(surfaces) == 6
    rows = []
    for parent, face_index, printed in surfaces:
        for seat in (1, 2):
            deck = [{'quantity': 30, 'card_name': 'Forest'},
                    {**printed, 'quantity': 1, 'card_name': printed['name']}]
            state = MatchFactory.from_decks(deck, deck, seed=2331)
            state.pregame_pending = False
            state.kept_hands = {1, 2}
            state.active_player = state.priority_player = seat
            state.step = Step.PRECOMBAT_MAIN
            walker = next(c for c in state.cards.values() if c.owner == seat and c.name == printed['name'])
            owner = state.players[seat]
            for zone in (owner.library, owner.hand):
                if walker.id in zone:
                    zone.remove(walker.id)
            owner.battlefield.append(walker.id)
            walker.zone = Zone.BATTLEFIELD
            walker.entered_turn = state.turn
            walker.static_order = walker.effect_timestamp = 1
            assert walker.oracle_text == printed['oracle_text']
            assert walker.loyalty == int(printed['loyalty'])
            before = serialize_match_snapshot(state)
            abilities = extract_loyalty_abilities(walker)
            moves = [m for m in RulesEngine().legal_moves(state, seat)
                     if m.get('type') == 'activate_loyalty' and m.get('card_id') == walker.id]
            assert serialize_match_snapshot(state) == before
            rows.append({'parent': parent, 'face_index': face_index, 'seat': seat,
                'printed': printed, 'starting_loyalty': walker.loyalty,
                'abilities': abilities, 'offered_templates': moves,
                'static_warnings': static_coverage_details(walker.oracle_text, card_name=walker.name),
                'warnings': known_unsupported_mechanics(walker.oracle_text, card_name=walker.name),
                'query_input_snapshot': before, 'query_input_unchanged': True})
    out = {'scope': 'seeded main-phase printed-loyalty availability, no paid execution',
           'seed_records': len(cards), 'printed_planeswalker_surfaces': len(surfaces),
           'seed_sha256': hashlib.sha256(raw).hexdigest(), 'rows': rows}
    (Path(os.environ['GAP6_EVIDENCE']) / 'shipped-planeswalker-inventory.json').write_text(
        json.dumps(out, indent=2) + '\n')
