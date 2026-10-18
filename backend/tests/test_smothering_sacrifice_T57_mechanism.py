"""Sacrifice-draw only: genuine handlers and native stack resolution, both seats."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from effects.handlers import destroy_permanent, sacrifice
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.stack_engine import resolve_top_of_stack
from tests.rules_printed_facts_e4 import canonical_card, canonical_deck_entry
from tests.smothering_sacrifice_T57 import smothering_card


DIRECTORY = Path(__file__).parent / 'fixtures/smothering_sacrifice_T57'
FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
          'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')


def _official():
    # Independent complete response reader, not the materializer's admission helper.
    body = (DIRECTORY / 'response.json').read_bytes()
    proof = (DIRECTORY / 'PROVENANCE.json').read_bytes()
    assert len(body) == 5102
    assert hashlib.sha256(body).hexdigest() == 'ff0cec752805b3545a3399925b3fc3189163a0940c2fed1d280e3b9909d80786'
    assert hashlib.sha256(proof).hexdigest() == 'c4f4d6a2426481c733c0b370dff3a84a7d3e6856a0634259874e45f9502e46be'
    raw, origin = json.loads(body), json.loads(proof)
    assert raw['object'] == 'card' and raw['name'] == 'Smothering Abomination'
    assert raw['id'] == origin['id'] == 'aac33238-e4bd-4c72-aecc-9905232c3ab4'
    assert raw['oracle_id'] == origin['oracle_id'] == 'c3db28e5-6162-4642-a1c9-a7ace0737950'
    assert origin['http_status'] == 200 and origin['curl_exit'] == 0
    assert origin['body_sha256'] == hashlib.sha256(body).hexdigest()
    assert {'legalities', 'rulings_uri', 'uri', 'image_uris'} <= raw.keys()
    assert raw['keywords'] == ['Flying', 'Devoid'] and raw['colors'] == []
    assert raw['layout'] == 'normal' and not raw.get('card_faces')
    return raw


def _facts(card, raw):
    expected = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors', 'layout')}
    expected.update(types=[word for word in raw['type_line'].split('\u2014')[0].split() if word == 'Creature'],
                    power=int(raw['power']), toughness=int(raw['toughness']),
                    printed_power=raw['power'], printed_toughness=raw['toughness'],
                    loyalty=None, keywords=['flying'], card_faces=[], selected_face_index=None,
                    image_uri=raw['image_uris']['normal'])
    for key, value in expected.items():
        assert type(getattr(card, key)) is type(value) and getattr(card, key) == value, key
    return expected


def _position(seat, monkeypatch, *, victim_owner=None, victim='Grizzly Bears'):
    raw = _official()
    births, native_init = [], CardInstance.__post_init__

    def observe(card):
        if card.name == raw['name']:
            _facts(card, raw)  # BEFORE native capture, never repaired afterward.
        native_init(card)
        if card.name == raw['name']:
            expected = _facts(card, raw)
            assert card.characteristic_record == {
                'version': 1, 'physical': expected,
                'values': {key: expected[key] for key in FIELDS},
            }
            births.append(card)

    monkeypatch.setattr(CardInstance, '__post_init__', observe)
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=731)
    decks, stock, rng = deepcopy(state.starting_decks), deepcopy(state.sideboard_facts), state.rng.getstate()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = seat
    state.step = Step.PRECOMBAT_MAIN
    source = smothering_card(id='p1', owner=seat, controller=seat, zone=Zone.BATTLEFIELD)
    owner = seat if victim_owner is None else victim_owner
    target = canonical_card(victim, id='c1', owner=owner, controller=owner, zone=Zone.BATTLEFIELD)
    state.cards.update({source.id: source, target.id: target})
    state.players[seat].battlefield.append(source.id)
    state.players[owner].battlefield.append(target.id)
    assert any(card is source for card in births)
    assert state.starting_decks == decks and state.sideboard_facts == stock
    assert state.rng.getstate() == rng
    assert (source.id, source.owner, source.controller, source.zone) == ('p1', seat, seat, Zone.BATTLEFIELD)
    assert (target.id, target.owner, target.controller, target.zone) == ('c1', owner, owner, Zone.BATTLEFIELD)
    assert not state.stack
    return state


def _held(state):
    return {seat: (list(state.players[seat].hand), list(state.players[seat].library)) for seat in (1, 2)}


def _assert_departed(state, owner):
    assert state.cards['c1'].zone == Zone.GRAVEYARD
    assert 'c1' in state.players[owner].graveyard
    assert 'c1' not in state.players[owner].battlefield
    assert state.cards['p1'].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', (1, 2), ids=('seat1', 'seat2'))
def test_own_creature_sacrifice_publishes_real_draw_and_resolves_actual_top_card(seat, monkeypatch):
    state = _position(seat, monkeypatch)
    held = _held(state)
    hand, library = held[seat]
    top = library[-1]
    sacrifice(state, seat, {'target_card_id': 'c1'})
    _assert_departed(state, seat)
    assert len(state.stack) == 1
    item = state.stack[0]
    assert item.source_card_id == 'p1' and item.controller == seat
    assert item.effect_key == 'draw_cards' and item.payload['amount'] == 1
    assert item.payload['__trigger_event'] == 'sacrifice'
    assert _held(state) == held
    resolve_top_of_stack(state)
    assert not state.stack
    assert state.players[seat].hand == hand + [top]
    assert state.players[seat].library == library[:-1]
    assert state.cards[top].zone == Zone.HAND and state.cards[top].owner == seat
    assert (state.players[3-seat].hand, state.players[3-seat].library) == held[3-seat]


@pytest.mark.parametrize('seat', (1, 2), ids=('seat1', 'seat2'))
def test_nonsacrifice_creature_death_does_not_publish_sacrifice_draw(seat, monkeypatch):
    state = _position(seat, monkeypatch)
    held = _held(state)
    destroy_permanent(state, 3-seat, {'target_card_id': 'c1'})
    _assert_departed(state, seat)
    assert not state.stack
    assert _held(state) == held


@pytest.mark.parametrize('seat', (1, 2), ids=('seat1', 'seat2'))
def test_opponent_creature_sacrifice_is_not_your_sacrifice_trigger(seat, monkeypatch):
    state = _position(seat, monkeypatch, victim_owner=3-seat)
    held = _held(state)
    sacrifice(state, 3-seat, {'target_card_id': 'c1'})
    _assert_departed(state, 3-seat)
    assert not state.stack
    assert _held(state) == held


@pytest.mark.parametrize('seat', (1, 2), ids=('seat1', 'seat2'))
def test_own_noncreature_sacrifice_does_not_publish_creature_sacrifice_draw(seat, monkeypatch):
    state = _position(seat, monkeypatch, victim='Sol Ring')
    held = _held(state)
    sacrifice(state, seat, {'target_card_id': 'c1'})
    _assert_departed(state, seat)
    assert not state.stack
    assert _held(state) == held
