from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from card_data.seed_cards import seed_card_payload
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.continuous import effective_toughness
from rules_engine.engine import RulesEngine


def _canonical_meathook():
    encoded = (Path(__file__).parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    if hashlib.sha256(encoded).hexdigest() != '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732':
        raise ValueError('Full Meathook source changed')
    raw = json.loads(encoded.splitlines()[102])
    if (raw.get('object'), raw.get('name'), raw.get('id'), raw.get('oracle_id'), len(raw)) != (
            'card', 'The Meathook Massacre', '70d0540f-93c6-4af5-ab2d-65e6c03001c7',
            '127de52b-df75-4342-95a0-20d84c5bf916', 64):
        raise ValueError('Full Meathook identity changed')
    if hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                 ensure_ascii=False).encode()).hexdigest() != '74a8c5d89cbd341783af3334f22fd563fa85c1afa10cda141051134bb1ac7b85':
        raise ValueError('Full Meathook object changed')
    from card_data.sync import ScryfallSyncService
    normalized = ScryfallSyncService._normalize_payload(raw, 'unused:task13-fixture-display')
    entry = {**raw, **normalized, 'card_name': raw['name'], 'quantity': 8,
             'image_uri': None, 'colors': deepcopy(raw.get('colors', [])),
             'card_faces': deepcopy(raw.get('card_faces', []))}
    sample = MatchFactory.from_decks([entry], [], seed=0)
    template = next(card for card in sample.cards.values() if card.zone == Zone.LIBRARY)
    return replace(template, id='meathook', owner=1, controller=1, zone=Zone.HAND,
                   instance_order=0, summoning_sick=True)


def test_printed_meathook_etb_uses_announced_x_not_other_abilities() -> None:
    deck = [{"quantity": 60, "card_name": "Swamp"}]
    state = MatchFactory.from_decks(deck, deck, seed=209)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    state.players[1].mana_pool["B"] = 4
    oracle = seed_card_payload("The Meathook Massacre")
    assert oracle is not None
    hook = _canonical_meathook()
    state.cards[hook.id] = hook
    state.players[1].hand.append(hook.id)
    for cid, owner, toughness in (("own-small", 1, 1), ("small", 2, 1), ("large", 2, 3)):
        creature = CardInstance(cid, cid, owner, owner, Zone.BATTLEFIELD, ["Creature"], power=toughness, toughness=toughness)
        state.cards[cid] = creature
        state.players[owner].battlefield.append(cid)

    rules = RulesEngine()
    state = checked_action(state, rules, 1, {"type": "cast_spell", "card_id": hook.id, "targets": {"x_value": 2}})
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert hook.id in state.players[1].battlefield
    assert state.stack[-1].effect_key == "temporary_pt_buff_all"
    assert state.stack[-1].payload["toughness"] == -2

    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    rules.take_action(state, 1, {"type": "pass_priority"})
    rules.take_action(state, 2, {"type": "pass_priority"})
    assert state.cards["small"].zone == Zone.GRAVEYARD
    assert state.cards["own-small"].zone == Zone.GRAVEYARD
    assert state.cards["large"].zone == Zone.BATTLEFIELD
    assert effective_toughness(state, "large") == 1
    assert {item.effect_key for item in state.stack} == {"gain_life", "lose_life"}
    while state.stack:
        rules.take_action(state, state.priority_player, {"type": "pass_priority"})
    assert state.players[1].life == 21
    assert state.players[2].life == 19
    assert any("All creatures get -2/-2" in line for line in state.log)
