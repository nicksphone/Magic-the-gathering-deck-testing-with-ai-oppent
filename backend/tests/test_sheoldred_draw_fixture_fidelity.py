"""Observe canonical positive inputs consumed by the original draw-event tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import tests.test_draw_triggers_no_recursive_draw as original
from tests.canonical_positive_fixtures import raw_card


NAME = 'Sheoldred, the Apocalypse'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
RAW_SHA = 'a6e9b1b3748becaaed1316a4ac7ea8c2ae340de41dada04189816990d2901b5f'
SUBJECTS = (
    original.test_sheoldred_you_draw_trigger_gains_life_not_draw,
    original.test_sheoldred_opponent_draw_trigger_loses_life,
)


def capture(body, monkeypatch):
    real_put = original._put_static_permanent_with_oracle
    real_emit = original.emit_event
    records = []

    def put(state, player_id, *args):
        card = state.cards[state.players[player_id].hand[0]]
        before = deepcopy(vars(card))
        rng = state.rng.getstate()
        facts = deepcopy(state.sideboard_facts)
        decks = deepcopy(state.starting_decks)
        card_id = real_put(state, player_id, *args)
        assert card_id == before['id']
        assert state.rng.getstate() == rng
        assert state.sideboard_facts == facts and state.starting_decks == decks
        records.append({'before': before, 'card': state.cards[card_id]})
        return card_id

    def emit(state, event, payload):
        assert event == 'draw_card' and len(records) == 1
        records[0]['source'] = deepcopy(vars(records[0]['card']))
        records[0]['event'] = deepcopy(payload)
        return real_emit(state, event, payload)

    with monkeypatch.context() as patch:
        patch.setattr(original, '_put_static_permanent_with_oracle', put)
        patch.setattr(original, 'emit_event', emit)
        body()
    assert len(records) == 1 and 'source' in records[0]
    return records[0]


@pytest.mark.parametrize('body', SUBJECTS, ids=['own-draw', 'opponent-draw'])
def test_actual_watcher_before_draw_event_has_full_official_rules(body, monkeypatch):
    source = capture(body, monkeypatch)['source']
    raw = raw_card(NAME)
    keys = ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout')
    assert {key: source[key] for key in keys} == {key: raw[key] for key in keys}
    assert source['types'] == ['Creature'] and source['card_faces'] == []
    assert (source['power'], source['toughness']) == (int(raw['power']), int(raw['toughness']))
    assert (source['printed_power'], source['printed_toughness']) == (raw['power'], raw['toughness'])
    assert 'deathtouch' in source['keywords']


def test_original_runtime_identity_and_direct_event_operands_are_preserved(monkeypatch):
    for body, player, event_card in zip(SUBJECTS, (1, 2), ('x', 'y')):
        record = capture(body, monkeypatch)
        before, source = record['before'], record['source']
        for key in ('id', 'owner', 'controller', 'instance_order', 'zone_change_sequence',
                    'summoning_sick', 'tapped', 'entered_turn', 'static_order',
                    'effect_timestamp', 'battlefield_incarnation', 'counters'):
            assert source[key] == before[key]
        assert before['zone'] == original.Zone.HAND and source['zone'] == original.Zone.BATTLEFIELD
        assert record['event'] == {'player_id': player, 'card_id': event_card}


def test_actual_source_and_official_mutables_are_independent(monkeypatch):
    first = capture(SUBJECTS[0], monkeypatch)['card']
    second = capture(SUBJECTS[0], monkeypatch)['card']
    assert first is not second
    first.types.append('Declared noncanonical independence sentinel')
    first.counters['independence-sentinel'] = 1
    assert second.types == ['Creature'] and second.counters == {}
    raw = raw_card(NAME)
    raw['colors'].clear()
    raw['legalities'].clear()
    assert raw_card(NAME)['colors'] == ['B'] and raw_card(NAME)['legalities']


def test_full_official_seed_and_provenance_are_pinned():
    root = Path(__file__).parent / 'fixtures/knowledge_profiles'
    data = (root / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    provenance = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == SEED_SHA and provenance['oracle_modified'] is False
    assert provenance['response_statuses'] == [200, 200, 200]
    raw = raw_card(NAME)
    assert [json.loads(line) for line in data.splitlines() if json.loads(line)['name'] == NAME] == [raw]
    assert raw['object'] == 'card' and raw['id'] and raw['oracle_id'] and raw['legalities']
    assert raw['rulings_uri'].startswith('https://api.scryfall.com/cards/')
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == RAW_SHA
