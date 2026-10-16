from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Step, Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.library_canonical_fixtures import PRINTED


def _canonical_source(name, **runtime):
    """Complete printed input at the original trusted, uncast runtime pose."""
    if PRINTED.intersection(runtime):
        raise ValueError('Printed fields are not runtime fixture overrides')
    root = Path(__file__).parent / 'fixtures'
    data = (root / 'human_activation_canonical7f/SOURCES.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == '8b4dcb302d0a2f65b2d44e274205179b08f8759520cbc852ef18c91127ea0a5a'
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


def test_activated_target_validation_happens_before_paying_tap_cost():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=2)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    source = _canonical_source("Prodigal Pyromancer", id="source", owner=1, controller=1, zone=Zone.BATTLEFIELD, summoning_sick=False)
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "activate_ability", "card_id": source.id, "ability_index": 0, "targets": {"target_player": 99}})
    assert not source.tapped
    assert not state.stack
    engine.take_action(state, 1, {"type": "activate_ability", "card_id": source.id, "ability_index": 0, "targets": {"target_player": 2}})
    assert source.tapped
    assert len(state.stack) == 1


def test_legal_move_card_metadata_is_exposed_only_at_http_boundary():
    import main
    from ai.agent import AIAgent
    deck = [{"quantity": 60, "card_name": "Island", "type_line": "Basic Land - Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=3)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    rules = RulesEngine()
    controller = main.MatchController(state=state, rules=rules, controllers={1: "human", 2: "human"}, ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human", deck_ids=(None, None), mainboards={1: deck, 2: deck}, sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False, match_complete=False, best_of=3)
    main.ACTIVE_MATCHES[state.id] = controller
    try:
        assert all("card_view" not in move for move in rules.legal_moves(state, 1))
        move = next(move for move in main.get_legal_moves(state.id, 1)["moves"] if move["type"] == "play_land")
        assert move["card_view"]["name"] == "Island"
    finally:
        main.ACTIVE_MATCHES.pop(state.id, None)


def test_empty_graveyard_target_surface_rejects_stale_card():
    from rules_engine.targeting import validate_cast_targets
    valid, _ = validate_cast_targets({"graveyard_permanent_targets": []}, {"target_card_id": "stale"})
    assert not valid


def test_unsupported_activation_is_rejected_without_paying_costs():
    state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}], [{"quantity": 60, "card_name": "Island"}], seed=2)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    source = _canonical_source("Oona, Queen of the Fae", id="source", owner=1, controller=1, zone=Zone.BATTLEFIELD, summoning_sick=False)
    state.cards[source.id] = source
    state.players[1].battlefield.append(source.id)
    state.players[1].mana_pool["U"] = 4
    before = serialize_match_snapshot(state)
    assert not any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))
    assert serialize_match_snapshot(state) == before
    RulesEngine().take_action(state, 1, {"type": "activate_ability", "card_id": source.id, "ability_index": 0, "targets": {"target_player": 2, "x_value": 3}})
    assert state.players[1].mana_pool["U"] == 4
    assert not state.stack
    assert "Unsupported activated ability effect" in state.log[-1]
    assert not any(move["type"] == "activate_ability" for move in RulesEngine().legal_moves(state, 1))


def test_activated_extractor_preserves_adjacent_mana_symbols():
    from rules_engine.oracle_effects import extract_activated_abilities
    card = _canonical_source("Azure Mage", id="mage", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    ability = extract_activated_abilities(card)[0]
    assert ability["mana_cost"] == "{3}{U}"
