"""Canonical two-family audit support; no invented effect or scheduler."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import pickle

from card_data.hydration import ready_for_match
from game_state.state import MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.ability_model import build_ability_spec, build_spell_spec
from rules_engine.action_validation import checked_action
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.engine import RulesEngine
from rules_engine.oracle_effects import extract_activated_abilities
from tests.readiness_rules_seam_support import normalize

FIXTURE = Path(__file__).parent / 'fixtures/extra_sequence'
RAW = json.loads((FIXTURE / 'canonical.json').read_text())
FAMILIES = ('Time Warp', 'Aggravated Assault')


def canonical(name):
    return {**deepcopy(RAW[name]), 'card_name': name, 'quantity': 1}


def seed_cache(repo):
    for raw in RAW.values():
        repo.upsert_card(normalize(raw))


def position(seat, step=Step.PRECOMBAT_MAIN):
    deck = [{**canonical('Island'), 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=7214)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 5
    state.active_player = state.priority_player = seat
    state.step = step
    for player in state.players.values():
        for cid in player.hand:
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
        player.hand.clear()
        player.mana_pool = {'W': 0, 'U': 10, 'B': 0, 'R': 10, 'G': 0, 'C': 10}
    return state


def add(state, name, seat, zone=Zone.BATTLEFIELD):
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


def action(source, target=None):
    if source.name == 'Time Warp':
        return {'type': 'cast_spell', 'card_id': source.id,
                'targets': {'target_player': target if target is not None else source.controller}}
    return {'type': 'activate_ability', 'card_id': source.id, 'ability_index': 0, 'targets': {}}


def submit(state, source, target=None):
    return checked_action(state, RulesEngine(), source.controller, action(source, target))


def resume(state):
    return deserialize_match_snapshot(serialize_match_snapshot(state))


def facts(state):
    data = deepcopy(vars(state))
    data['cards'] = {cid: deepcopy(vars(card)) for cid, card in state.cards.items()}
    data['players'] = {pid: deepcopy(vars(player)) for pid, player in state.players.items()}
    data['stack'] = [deepcopy(vars(item)) for item in state.stack]
    data['rng'] = state.rng.getstate()
    return data


def observe(state, source):
    before = pickle.dumps(state)
    candidate = deepcopy(state)
    candidate_source = candidate.cards[source.id]
    spec = build_spell_spec(candidate, candidate_source, source.controller)
    activated = extract_activated_abilities(candidate_source)
    ability = None
    if activated:
        text = activated[0]['text']
        proxy = type('ActivatedOracleProxy', (), {
            'id': source.id, 'oracle_text': text, 'mana_cost': '', 'name': source.name})()
        ability = asdict(build_ability_spec(candidate, proxy, source.controller, report_unsupported=False))
    assert pickle.dumps(state) == before
    return {'name': source.name, 'seat': source.controller,
            'metadata_ready': ready_for_match(canonical(source.name)),
            'known_gaps': known_unsupported_mechanics(source.oracle_text, card_name=source.name),
            'spell': asdict(spec), 'activated': activated, 'ability': ability,
            'diagnostic_log': candidate.log, 'execution_certified': False}
