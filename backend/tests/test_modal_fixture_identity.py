"""Native fixture birth/serde controls, not paid modal or HTTP acceptance."""
import ast
from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from card_data.hydration import hydrate_deck_cards
from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Step, Zone, assign_static_order_on_battlefield_entry


SUBJECT = Path(__file__).with_name('test_modal_spell_faces.py')
DATA = json.loads((SUBJECT.parent / 'fixtures/modal_spell_faces.json').read_text())
VALKI = 'Valki, God of Lies // Tibalt, Cosmic Impostor'
ARCHAIC = 'Wandering Archaic // Explore the Vastlands'
MYSTIC = next(json.loads(line) for line in
              (SUBJECT.parent / 'fixtures/knowledge_profiles/seed155-scryfall.jsonl').read_text().splitlines()
              if json.loads(line)['name'] == 'Elvish Mystic')


class BirthCaptured(Exception):
    pass


def subjects():
    names = {'fixture', '_valki_entry', '_valki_with_exiled_mystic'}
    nodes = [node for node in ast.parse(SUBJECT.read_text()).body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = dict(DATA=DATA, VALKI=VALKI, json=json, Path=Path, __file__=str(SUBJECT),
                     SimpleNamespace=SimpleNamespace, hydrate_deck_cards=hydrate_deck_cards,
                     ScryfallSyncService=ScryfallSyncService, MatchFactory=MatchFactory,
                     Step=Step, Zone=Zone,
                     assign_static_order_on_battlefield_entry=assign_static_order_on_battlefield_entry)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SUBJECT), 'exec'), namespace)
    return namespace


def opponent_rows():
    return [{**deepcopy(DATA[VALKI]), 'quantity': 59}, {**deepcopy(MYSTIC), 'quantity': 1}]


def assert_bound(state):
    assert len(state.cards) == len(state.sideboard_facts['inventory']) == 120
    assert state.sideboard_facts['game_id'] == state.id
    snapshot = serialize_match_snapshot(state)
    assert serialize_match_snapshot(deserialize_match_snapshot(snapshot)) == snapshot
    return snapshot


def assert_mystic_stock(state):
    assert_bound(state)
    assert Counter({row['card_name']: row['quantity'] for row in state.starting_decks[2]}) == {
        VALKI: 59, 'Elvish Mystic': 1}
    mystics = [card for card in state.cards.values() if card.owner == 2 and card.name == 'Elvish Mystic']
    assert len(mystics) == 1
    card = mystics[0]
    assert card.oracle_text == MYSTIC['oracle_text']
    assert card.mana_cost == MYSTIC['mana_cost']
    assert card.types == ['Creature']
    assert state.sideboard_facts['inventory'][card.id] == {'owner': 2, 'stock_key': 'Elvish Mystic'}
    return card


def test_real_helper_tail_has_native_printed_binding_before_any_resolution():
    namespace = subjects()
    original_entry = namespace['_valki_entry']
    births = []

    def stop_at_entry_event(state, event, payload):
        births.append((state, state.cards[payload['card_id']]))
        raise BirthCaptured

    def birth_only_entry(**kwargs):
        with pytest.raises(BirthCaptured):
            original_entry(**kwargs)
        return births.pop()

    # Real positioning prefix; stop before emission, with no fabricated StackItem.
    namespace['emit_event'] = stop_at_entry_event
    namespace['_valki_entry'] = birth_only_entry
    captured = []

    def stop_before_resolution(state):
        captured.append(assert_mystic_stock(state).id)
        raise BirthCaptured

    namespace['resolve_top_of_stack'] = stop_before_resolution
    with pytest.raises(BirthCaptured):
        namespace['_valki_with_exiled_mystic']()
    assert len(captured) == 1


def test_real_entry_positions_born_mystic_before_event_not_a_donor_id():
    namespace = subjects()
    signature = ast.parse(SUBJECT.read_text())
    node = next(n for n in signature.body if isinstance(n, ast.FunctionDef) and n.name == '_valki_entry')
    assert 'opponent_rows' in {arg.arg for arg in node.args.args + node.args.kwonlyargs}
    captured = []

    def stop_before_event(state, event, payload):
        card = assert_mystic_stock(state)
        assert card.zone == Zone.HAND and card.id in state.players[2].hand
        assert len(state.players[2].hand) == 7
        assert len(state.players[2].library) == 53
        assert payload['card_id'] in state.players[1].battlefield
        captured.append(card.id)
        raise BirthCaptured

    namespace['emit_event'] = stop_before_event
    with pytest.raises(BirthCaptured):
        namespace['_valki_entry'](opponent_rows=opponent_rows())
    assert len(captured) == 1


@pytest.mark.parametrize('name', [VALKI, ARCHAIC])
def test_default_whole_canonical_fixture_still_has_sixty_each(name):
    state, card = subjects()['fixture'](name)
    assert_bound(state)
    for pid in (1, 2):
        assert state.starting_decks[pid][0]['quantity'] == 60
        assert state.starting_decks[pid][0]['card_name'] == name
        assert len([c for c in state.cards.values() if c.owner == pid]) == 60
    assert card.card_faces == state.starting_decks[1][0]['card_faces']


def test_canonical_rows_are_not_mutated_by_birth():
    before = deepcopy(DATA)
    mystic_before = deepcopy(MYSTIC)
    state, _ = subjects()['fixture'](VALKI)
    assert_bound(state)
    assert DATA == before and MYSTIC == mystic_before


@pytest.mark.parametrize('pid', [1, 2])
def test_postbirth_printed_repurpose_still_rejects_snapshot(pid):
    state, _ = subjects()['fixture'](VALKI)
    assert_bound(state)
    target = state.cards[state.players[pid].hand[0]]
    target.printed_characteristics['name'] = 'Elvish Mystic'
    with pytest.raises(ValueError, match='physical printed source'):
        serialize_match_snapshot(state)


def test_native_private_snapshot_retains_full_born_faces_and_stock():
    state, source = subjects()['fixture'](VALKI)
    snapshot = assert_bound(state)
    assert snapshot['sideboard_facts'] == state.sideboard_facts
    assert state.cards[source.id].card_faces == state.starting_decks[1][0]['card_faces']
    assert state.starting_decks[1][0]['card_faces'][1]['oracle_text'] == DATA[VALKI]['card_faces'][1]['oracle_text']
