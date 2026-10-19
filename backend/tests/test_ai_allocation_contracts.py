from dataclasses import replace
import hashlib
import json
from pathlib import Path

from ai.agent import AIAgent
from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from tests.library_canonical_fixtures import PRINTED


def _canonical_card(name, **runtime):
    """Full official printed values at the original uncast, no-entry pose."""
    if PRINTED.intersection(runtime):
        raise ValueError('Printed fields are not runtime fixture overrides')
    root = Path(__file__).parent / 'fixtures'
    data = (root / 'allocation_canonical7f/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == '016f2483ed3eca00d259914b81bfa8668a636bf56d0c3d1fa355dd950d1e9b4d'
    record = json.loads(data)[name]
    data = (root / record['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == record['file_sha256']
    raw = json.loads(data)
    if 'index' in record:
        raw = raw[record['index']]
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == record['id'] and raw['oracle_id'] == record['oracle_id']
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, **{'instance_order': 0, 'summoning_sick': True, **runtime})


def _initialize_entry_counter_pose(state, card):
    """Derive and commit the existing entry counters for a trusted ready pose."""
    from rules_engine.graveyard_batch_entry import _entry_seeds
    from rules_engine.entry_counters import prepare_entry_counters, commit_entry_counters
    seed = _entry_seeds(state, [card], controllers={card.id: card.controller})[card.id]
    data = {'entry_payload': seed, 'entry_prepared': {}, 'entry_index': 0}
    if not prepare_entry_counters(state, card.controller, data, card, 'permanent_entry_counters'):
        raise AssertionError('Controlled counter pose requires a completed native entry preparation')
    commit_entry_counters(state, card, {
        '__entry_counters_by_id': {card.id: data['entry_payload']['__entry_counters_ready']}})


def state_with_targets():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=3)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    # Historical numbers are not printed overrides: Nishoba is genuinely 0/0.
    for cid, name, power, owner in (("friendly", "Phantom Nishoba", 7, 1), ("enemy", "Grizzly Bears", 2, 2)):
        state.cards[cid] = _canonical_card(name, id=cid, owner=owner, controller=owner, zone=Zone.BATTLEFIELD, summoning_sick=False)
        state.players[owner].battlefield.append(cid)
        _initialize_entry_counter_pose(state, state.cards[cid])
    return state


def test_ai_uses_the_fixed_damage_budget_and_an_enemy_recipient():
    state = state_with_targets()
    card = _canonical_card("Pyrotechnics", id="spell", owner=1, controller=1, zone=Zone.HAND)
    state.cards[card.id] = card
    state.players[1].hand.append(card.id)
    state.players[1].mana_pool["R"] = 5
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move.get("card_id") == card.id and move["type"] == "cast_spell")
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"]["target_distribution"] == {"enemy": 4}
    engine.take_action(state, 1, action, reject_invalid=True)
    assert state.stack[-1].payload["target_distribution"] == {"enemy": 4}


def test_generic_targeted_activation_gets_a_materialized_enemy_target():
    state = state_with_targets()
    state.cards["enemy"].counters["__damage_marked"] = 1
    source = _canonical_card("Prodigal Pyromancer", id="pyro", owner=1, controller=1, zone=Zone.BATTLEFIELD, summoning_sick=False)
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move.get("card_id") == source.id and move["type"] == "activate_ability")
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"]["target_card_id"] == "enemy"
    engine.take_action(state, 1, action, reject_invalid=True)
    assert source.tapped
    assert state.stack[-1].payload["target_card_id"] == "enemy"


def test_generic_targeted_activation_avoids_nonlethal_creature_damage():
    state = state_with_targets()
    source = _canonical_card("Prodigal Pyromancer", id="pyro", owner=1, controller=1, zone=Zone.BATTLEFIELD, summoning_sick=False)
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    engine = RulesEngine()
    move = next(move for move in engine.legal_moves(state, 1) if move.get("card_id") == source.id and move["type"] == "activate_ability")
    action = AIAgent()._materialize_action(state, move, 1)
    assert action["targets"] == {"target_player": 2}
    engine.take_action(state, 1, action, reject_invalid=True)
    assert state.stack[-1].payload["target_player"] == 2
