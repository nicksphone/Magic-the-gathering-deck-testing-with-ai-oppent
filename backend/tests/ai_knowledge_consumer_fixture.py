"""Explicit canonical board fixtures, NOT naturally replayed opening hands."""
from copy import deepcopy
import json
import os
from pathlib import Path

from ai.agent import AIAgent, _card_for_move
from ai.information import decision_view, is_unknown
from ai.pending_effects import decision_projection_scope
from card_data.hydration import hydrate_deck_cards
from decks.builtin_decks import BUILTIN_DECKS
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine

SEED = 701


def deck(style):
    entries = [{'quantity': int(q), 'card_name': name} for q, name in
               (line.split(' ', 1) for line in BUILTIN_DECKS[style].strip().splitlines())]
    result = hydrate_deck_cards(None, entries)
    assert all(row.get('scryfall_id') and row.get('type_line') for row in result)
    return result


def position(style, opponent, seat):
    own, enemy = deck(style), deck(opponent)
    state = MatchFactory.from_decks(own if seat == 1 else enemy, enemy if seat == 1 else own, seed=SEED)
    state.id = f'knowledge-audit-{style}-{opponent}-{seat}-{SEED}'
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.turn = 5
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            player.library.append(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.mana_pool.clear()
    return state


def take(state, name, seat, zone):
    card = next(card for card in state.cards.values()
                if card.owner == seat and card.name == name and card.zone == Zone.LIBRARY)
    state.players[seat].library.remove(card.id)
    card.move_to_zone(zone)
    getattr(state.players[seat], zone.value).append(card.id)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, card.id)
        card.summoning_sick = False
    return card


def reservation_case(seat, style='Tempo'):
    control = style == 'Control'
    state = position('Dimir Control' if control else 'Tempo', 'Ramp', seat)
    draw = take(state, 'Memory Deluge' if control else 'Consider', seat, Zone.HAND)
    answer = take(state, 'Counterspell' if control else 'Brazen Borrower', seat, Zone.HAND)
    # Four lands fund Deluge; one blue land funds Consider, leaving zero blue after.
    for _ in range(4 if control else 1):
        take(state, 'Island', seat, Zone.BATTLEFIELD)
    if not control:
        take(state, 'Mountain', seat, Zone.BATTLEFIELD)
    target = take(state, 'Topiary Stomper', 3-seat, Zone.BATTLEFIELD)
    take(state, 'Forest', 3-seat, Zone.BATTLEFIELD)
    take(state, 'Forest', 3-seat, Zone.BATTLEFIELD)
    take(state, 'Ugin, the Spirit Dragon', 3-seat, Zone.HAND)
    state.active_player = 3-seat
    return state, draw, answer, target


def modal_case(seat, role):
    state = position('Midrange', 'Tempo', seat)
    source = take(state, 'Bonecrusher Giant', seat, Zone.HAND)
    take(state, 'Llanowar Elves', seat, Zone.BATTLEFIELD)
    if role == 'convert':
        take(state, 'Bonecrusher Giant', seat, Zone.BATTLEFIELD)
    else:
        state.players[3-seat].life = 5
    take(state, 'Delver of Secrets', 3-seat, Zone.BATTLEFIELD)
    take(state, 'Mountain', seat, Zone.BATTLEFIELD)
    take(state, 'Forest', seat, Zone.BATTLEFIELD)
    return state, source


def view_and_moves(state, seat):
    before = serialize_match_snapshot(state)
    legal = RulesEngine().legal_moves(state, seat)
    view, offered = decision_view(state, seat, legal)
    assert serialize_match_snapshot(state) == before
    assert all(is_unknown(view.cards[cid]) for p in view.players.values() for cid in p.library)
    assert all(is_unknown(view.cards[cid]) for cid in view.players[3-seat].hand)
    assert 3-seat not in view.starting_decks
    return view, offered


def actor(style, opponent='Ramp'):
    return AIAgent(difficulty='master', archetype=style, opponent_archetype=opponent)


def receipt(state, seat, ai):
    view, legal = view_and_moves(state, seat)
    before = serialize_match_snapshot(state)
    with decision_projection_scope(view, seat):
        ranked = ai._rank_moves(view, legal, seat, shallow=True)
        rows = []
        for move in legal:
            if move['type'] != 'cast_spell':
                continue
            surface = _card_for_move(view, move)
            action = ai._materialize_action(view, move, seat)
            rows.append({'legal_move': move, 'effective_name': surface.name,
                         'effective_tags': sorted(ai._spell_tags(surface)),
                         'stored_tags': sorted(ai._spell_tags(view.cards[move['card_id']])),
                         'cast_bias': ai._cast_bias(view, move, seat),
                         'matchup_adjustment': ai._matchup_move_adjustment(view, move, seat),
                         'reservation': ai._instant_value_reservation(view, move, seat),
                         'materialized': action})
    assert serialize_match_snapshot(state) == before
    return {'snapshot': before, 'legal_moves': legal, 'profile': ai.matchup_profile,
            'board_role': ai._board_role(view, seat), 'ranked': ranked, 'cast_rows': rows}


def emit(name, value):
    target = os.environ.get('MTG_AI_KNOWLEDGE_AUDIT_EVIDENCE')
    if target:
        root = Path(target).resolve()
        assert str(root).startswith('/home/nick/.hermes/cache/scratch/mtg-ai-knowledge-audit-evidence-')
        (root / (name + '.json')).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
