"""Exact corpus facts and local diagnostic positions, not a support classifier."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import pickle

from card_data.hydration import hydrate_deck_cards, ready_for_match
from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.ability_model import build_ability_spec, build_spell_spec
from rules_engine.action_validation import checked_action
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack

FIXTURE = Path(__file__).parent/'fixtures/readiness_rules_seam'
RAW = json.loads((FIXTURE/'canonical.json').read_text())
FAMILIES = {'Dimir Control':['Counterspell','Fatal Push','Go for the Throat','Drown in the Loch'],
            'Tokens':['Raise the Alarm','Intangible Virtue','Clarion Spirit','Wedding Announcement // Wedding Festivity']}


def normalize(raw):
    return ScryfallSyncService._normalize_payload(raw, ScryfallSyncService._extract_remote_image_uri(raw))


def seed_cache(repo):
    for raw in RAW.values():
        repo.upsert_card(normalize(raw))


def canonical(name):
    raw = RAW[name]
    row = {**raw, 'card_name':name, 'quantity':1}
    if raw.get('card_faces'):
        row.update({key:value for key,value in raw['card_faces'][0].items() if key in
                    {'mana_cost','type_line','oracle_text','power','toughness','loyalty'}})
    return row


def position(seat):
    deck = [{**canonical('Island'), 'quantity':60}]
    state = MatchFactory.from_decks(deck, deck, seed=6214)
    state.pregame_pending = False
    state.kept_hands = {1,2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {'W':10,'U':10,'B':10,'R':10,'G':10,'C':10}
    return state


def add(state, name, seat, zone=Zone.BATTLEFIELD):
    sample = MatchFactory.from_decks([canonical(name)], [], seed=6214)
    card = deepcopy(next(iter(sample.cards.values())))
    card.id = state.allocate_object_id()
    card.owner = card.controller = seat
    card.move_to_zone(zone)
    card.summoning_sick = False
    state.cards[card.id] = card
    getattr(state.players[seat], zone.value).append(card.id)
    return card


def cast(state, source, **targets):
    return checked_action(state, RulesEngine(), source.controller,
                          {'type':'cast_spell','card_id':source.id,'targets':targets})


def resolve(state):
    for _ in range(20):
        if not state.stack:
            return state
        assert resolve_top_of_stack(state)
    raise AssertionError('Bounded stack failed to settle')


def resume(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def observation(state, source):
    before = pickle.dumps(state)
    ability = asdict(build_ability_spec(state, source, source.controller, report_unsupported=False))
    spell = asdict(build_spell_spec(state, source, source.controller))
    assert pickle.dumps(state) == before
    raw = RAW[source.printed_characteristics.get('name', source.name)] if source.name in RAW else RAW['Wedding Announcement // Wedding Festivity']
    return {'card_name':source.name,'seat':source.controller,
            'raw_sha256':hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'metadata_ready':ready_for_match(canonical(raw['name'])),
            'known_gaps':known_unsupported_mechanics(raw.get('oracle_text',''),raw.get('card_faces'),card_name=raw['name']),
            'ability':ability,'spell':spell,'execution_certified':False}
