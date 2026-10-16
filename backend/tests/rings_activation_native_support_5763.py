"""Full pinned local official inputs; no invented activated-ability bodies."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.rules_printed_facts_e4 import canonical_deck_entry


HERE = Path(__file__).parent
SOURCES = json.loads((HERE / 'fixtures/rings_activation_native_5763/SOURCES.json').read_bytes())


def raw_card(name):
    pin = SOURCES[name]
    data = (HERE / pin['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == pin['file_sha256']
    raw = json.loads(data.splitlines()[pin['line']-1] if pin['line'] else data)
    for step in pin['steps']:
        raw = raw[step]
    assert raw['name'] == name and raw['object'] == 'card'
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == pin['row_sha256']
    return raw


def position(seat):
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=937)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = seat
    state.mechanic_choice_players = {1, 2}
    return state


def add(state, name, cid, seat, zone=Zone.BATTLEFIELD, *, owner=None):
    raw = raw_card(name)
    sample = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 8}], [], seed=100)
    template = next(c for c in sample.cards.values() if c.zone == Zone.LIBRARY)
    card = replace(template, id=cid, owner=seat if owner is None else owner,
                   controller=seat, zone=zone, instance_order=0, summoning_sick=False)
    state.cards[cid] = card
    getattr(state.players[seat], zone.value).append(cid)
    if zone == Zone.BATTLEFIELD:
        assign_static_order_on_battlefield_entry(state, cid)
    return card


def act(state, seat, kind, **fields):
    return checked_action(state, RulesEngine(), seat, {'type': kind, **fields})


def board(seat, *, foreign_owner=False):
    state = position(seat)
    add(state, 'Rings of Brighthearth', 'rings', seat, owner=3-seat if foreign_owner else seat)
    add(state, 'Prodigal Pyromancer', 'pyromancer', seat, owner=3-seat if foreign_owner else seat)
    state.players[seat].mana_pool = {'C': 2}
    return state


def activate(state, seat, target=None):
    return act(state, seat, 'activate_ability', card_id='pyromancer', ability_index=0,
               targets={'target_player': 3-seat if target is None else target})


def optional(state, seat, *, accept=True):
    assert state.stack[-1].source_card_id == 'rings'
    assert not resolve_top_of_stack(state)
    assert state.pending_trigger_order['phase'] == 'optional'
    return act(state, seat, 'choose_optional_effect', stack_id=state.stack[-1].id, accept=accept)
