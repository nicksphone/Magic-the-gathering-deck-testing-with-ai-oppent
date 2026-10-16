"""Pure first-consumer and snapshot witnesses; original HTTP body is not run."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from card_data.sync import ScryfallSyncService
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, Zone
from rules_engine.card_faces import apply_transform_face
from rules_engine.copiable_values import PHYSICAL
from tests import test_end_step_attack_reward as original
from tests.wedding_attack_canonical_db4e import WEDDING, canonical_card, deck_entry, raw_card

PURE_NAMES = (
    'test_no_attack_creates_token_then_transforms_only_on_third_resolution',
    'test_two_declared_attackers_draw_even_after_they_leave_and_source_enters_later',
    'test_token_put_onto_battlefield_attacking_does_not_count_as_declared_attacker',
    'test_extra_counters_do_not_transform_until_end_step_trigger_resolves',
    'test_departed_source_trigger_still_makes_token_but_cannot_buff_new_incarnation',
    'test_declared_attacker_history_resets_at_new_turn',
)
HTTP_NAME = 'test_live_cached_card_draws_after_http_attack_and_match_restore'
BOUNDARIES = ('emit_event', 'declare_attackers', 'declare_attackers',
              'add_counters', 'emit_event', 'declare_attackers')
SUBJECTS = [(name, boundary, WEDDING) for name, boundary in zip(PURE_NAMES, BOUNDARIES)]
SUBJECTS += [(PURE_NAMES[index], BOUNDARIES[index], 'Grizzly Bears') for index in (1, 2, 5)]
SUBJECTS += [(PURE_NAMES[0], BOUNDARIES[0], 'Plains')]


@pytest.fixture(autouse=True)
def no_new_main_binding():
    present, before = 'main' in sys.modules, sys.modules.get('main')
    yield
    assert ('main' in sys.modules) == present
    if present: assert sys.modules['main'] is before


def reference(name, face=0):
    # Independent construction from full RAW, not the new materializer's output.
    raw = raw_card(name)
    entry = {**deepcopy(raw), 'quantity': 8, 'card_name': raw['name'],
             'image_uri': ScryfallSyncService._normalize_payload(raw, None)['image_uri']}
    if name == WEDDING: entry['selected_face_index'] = 0
    state = MatchFactory.from_decks([entry], [], seed=0)
    card = next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)
    if name == WEDDING and face: apply_transform_face(card, face)
    return card


def assert_complete(card, name, face=0):
    raw = raw_card(name)
    expected = reference(name, face)
    assert card.card_faces == raw.get('card_faces', []), 'complete ordered official faces required'
    assert {key: getattr(card, key) for key in PHYSICAL} == {key: getattr(expected, key) for key in PHYSICAL}
    assert card.printed_characteristics == expected.printed_characteristics
    assert card.characteristic_record == expected.characteristic_record
    active = raw['card_faces'][face] if name == WEDDING else raw
    assert card.name == active['name'] and card.oracle_text == active['oracle_text']
    assert card.mana_cost == active['mana_cost'] and card.type_line == active['type_line']


@pytest.mark.parametrize('test_name,boundary,name', SUBJECTS,
    ids=[test_name + ':' + name for test_name, boundary, name in SUBJECTS])
def test_actual_first_consumer_gets_complete_printed_facts(monkeypatch, test_name, boundary, name):
    present, main_before = 'main' in sys.modules, sys.modules.get('main')
    real = getattr(original, boundary)
    captured = []
    def observe(state, *args, **kwargs):
        if not captured:
            matches = [card for card in state.cards.values()
                       if (card.id == 'wedding' if name == WEDDING else card.name == name)]
            assert matches
            for card in matches: assert_complete(card, name)
            assert ('main' in sys.modules) == present
            if present: assert sys.modules['main'] is main_before
            captured.append(len(matches))
        return real(state, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(original, boundary, observe)
        getattr(original, test_name)()
    assert captured


@pytest.mark.parametrize('name', (WEDDING, 'Grizzly Bears', 'Plains', 'Island'))
def test_materializer_complete_facts_physical_identity_and_independence(name):
    before = raw_card(name)
    one = canonical_card(name, id='one', owner=1, controller=2, zone=Zone.BATTLEFIELD)
    two = canonical_card(name, id='two', owner=2, controller=1, zone=Zone.HAND)
    assert_complete(one, name); assert_complete(two, name)
    assert (one.id, one.owner, one.controller, one.zone) == ('one', 1, 2, Zone.BATTLEFIELD)
    assert (two.id, two.owner, two.controller, two.zone) == ('two', 2, 1, Zone.HAND)
    one.card_faces.append({'test_only_mutation': True})
    one.characteristic_record['physical']['oracle_text'] = 'test-only mutation'
    one.printed_characteristics['test_only_mutation'] = True
    assert_complete(two, name)
    assert raw_card(name) == before


def test_factory_selects_front_before_every_printed_capture(monkeypatch):
    from rules_engine import copiable_values
    real = copiable_values.initialize
    captured = []
    def observe(card):
        if card.layout == 'transform':
            assert card.selected_face_index == 0
            assert card.card_faces == raw_card(WEDDING)['card_faces']
            captured.append(card.selected_face_index)
        return real(card)
    with monkeypatch.context() as patch:
        patch.setattr(copiable_values, 'initialize', observe)
        card = canonical_card(WEDDING, id='wedding', owner=1, controller=1, zone=Zone.BATTLEFIELD)
    assert captured and len(captured) >= 16
    assert_complete(card, WEDDING)


@pytest.mark.parametrize('face', (0, 1))
def test_original_state_snapshot_retains_full_faces_and_selected_form(face):
    state, cid = original._state()
    assert_complete(state.cards[cid], WEDDING)
    if face: apply_transform_face(state.cards[cid], face)
    before_rng = state.rng.getstate()
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert_complete(restored.cards[cid], WEDDING, face)
    assert restored.rng.getstate() == before_rng
    assert (restored.cards[cid].id, restored.cards[cid].owner, restored.cards[cid].controller) == (cid, 1, 1)


def test_actual_three_resolutions_transform_with_full_facts_and_snapshot():
    state, cid = original._state()
    assert_complete(state.cards[cid], WEDDING)
    for count in (1, 2, 3):
        original._end_step(state)
        assert state.cards[cid].counters['invitation'] == count
    assert_complete(state.cards[cid], WEDDING, 1)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert_complete(restored.cards[cid], WEDDING, 1)


def test_state_and_bear_keep_seed_resources_and_physical_poses():
    state, cid = original._state()
    baseline = MatchFactory.from_decks([deck_entry('Plains', 60)], [deck_entry('Plains', 60)], seed=73)
    assert state.rng.getstate() == baseline.rng.getstate()
    rng = state.rng.getstate()
    original._bear(state, 'physical-bear')
    assert state.rng.getstate() == rng
    assert (state.cards[cid].id, state.cards[cid].owner, state.cards[cid].controller,
            state.cards[cid].zone, state.cards[cid].summoning_sick) == ('wedding', 1, 1, Zone.BATTLEFIELD, True)
    bear = state.cards['physical-bear']
    assert (bear.owner, bear.controller, bear.zone, bear.summoning_sick) == (1, 1, Zone.BATTLEFIELD, False)
    assert_complete(bear, 'Grizzly Bears')
    assert all(player.life == 20 and len(player.hand) == 7 for player in state.players.values())


def test_original_seven_bodies_decorators_and_28_assertions_unchanged():
    tree = ast.parse(Path(original.__file__).read_bytes())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    assert [n.name for n in functions] == [*PURE_NAMES, HTTP_NAME]
    bodies = [ast.dump(n, include_attributes=False) for n in functions]
    assertions = [ast.dump(n, include_attributes=False) for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    digest = lambda values: hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()
    assert digest(bodies) == 'de6bc1830c6d6a6b1f38f2f44d193c6b94efa947147b0a59a3b0ca9fbb5451a1'
    assert len(assertions) == 28 and digest(assertions) == '312d7a99cb1cb847e971e3777c06e24c0d497476b52a1a1a242d6cfc979f9968'
