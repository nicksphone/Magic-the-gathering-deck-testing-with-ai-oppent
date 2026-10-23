"""Native input witnesses only; original tests retain rules/HTTP outcome coverage."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, MatchState, Zone
from rules_engine.copiable_values import FIELDS, PHYSICAL
from tests import test_api_input_contracts as api_inputs
from tests import test_loyalty_destruction_scope_diagnostic as vraska
from tests import test_meathook_etb as meathook
from tests import test_shield_counters as shield
from tests.test_api_input_contracts import game
from tests.test_self_removal import canonical_cards


TESTS = Path(__file__).parent
RAW_SOURCES = {
    'Vraska the Unseen': (
        'vraska_full/fixtures/vraska-scryfall-raw.json', None, 66,
        'd05bc8f4d639536deb46eabb9f1ee807373418591be1deb1af7d57548d79423f',
        '53bb2bb2183d467d53842a588c074dedc118f62fc8a0ad70e33e2311f69fc7e6',
        'a6ab9d2b-6cb3-4477-8d0e-712c530383bd', '0d2bbce0-8c27-4b82-ab62-51a0c3cfc9b0'),
    'The Meathook Massacre': (
        'fixtures/knowledge_profiles/seed155-scryfall.jsonl', 103, 64,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '74a8c5d89cbd341783af3334f22fd563fa85c1afa10cda141051134bb1ac7b85',
        '70d0540f-93c6-4af5-ab2d-65e6c03001c7', '127de52b-df75-4342-95a0-20d84c5bf916'),
    'Lightning Bolt': (
        'fixtures/knowledge_profiles/seed155-scryfall.jsonl', 57, 66,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '69f44086d0a62778e6284b4d4926cd1d22d80d1330c1192e1c61a28d8f3b732b',
        '7673784e-db4b-43a1-8d55-1bb9fc1e284f', '4457ed35-7c10-48c8-9776-456485fdf070'),
}


def official(name):
    path, line, fields, file_sha, object_sha, identifier, oracle_id = RAW_SOURCES[name]
    encoded = (TESTS / path).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == file_sha
    raw = json.loads(encoded.splitlines()[line - 1] if line else encoded)
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id'], len(raw)) == (
        'card', name, identifier, oracle_id, fields)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == object_sha
    return raw


@pytest.mark.parametrize('case,player', [('vraska', None), ('meathook', None), ('bolt', 1), ('bolt', 2)])
def test_original_full_print_before_birth_and_first_consumer(monkeypatch, request, case, player):
    module, name, helper_name = {
        'vraska': (vraska, 'Vraska the Unseen', '_canonical_vraska'),
        'meathook': (meathook, 'The Meathook Massacre', '_canonical_meathook'),
        'bolt': (shield, 'Lightning Bolt', 'canonical_card'),
    }[case]
    raw = official(name)
    raw_path = (TESTS / RAW_SOURCES[name][0]).resolve()
    expected = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors')}
    expected.update(types={'vraska': ['Planeswalker'], 'meathook': ['Enchantment'], 'bolt': ['Instant']}[case],
                    power=None, toughness=None, printed_power=None, printed_toughness=None,
                    loyalty=int(raw['loyalty']) if 'loyalty' in raw else None, keywords=[])
    physical = {**expected, 'card_faces': raw.get('card_faces', []), 'layout': raw['layout'],
                'selected_face_index': None, 'image_uri': None}
    assert set(expected) == set(FIELDS) and set(physical) == set(PHYSICAL)
    actor = 3 - player if case == 'bolt' else 1
    zone = Zone.BATTLEFIELD if case == 'vraska' else Zone.HAND
    identifier = {'vraska': 'canonical-vraska', 'meathook': 'meathook', 'bolt': None}[case]
    # Fixture setup stays real and precedes all observation patches.
    game_data = request.getfixturevalue('game') if case == 'bolt' else None
    roots = [game_data[1].state] if game_data else []
    provider = Path.read_bytes
    normalizer = ScryfallSyncService._normalize_payload
    factory, birth = MatchFactory.from_decks, CardInstance.__post_init__
    allocate, materialize = MatchState.allocate_object_id, getattr(module, helper_name)
    settled, snapshot = vraska.settled_state, vraska.serialize_match_snapshot
    checked, persist = meathook.checked_action, api_inputs.persist
    providers, normalized, samples, template_births, pose_births = [], [], [], [], []
    allocated, preserved, events = [], [], []
    in_sample = False

    class BeforeConsumer(BaseException):
        pass

    def retained(card):
        assert {key: getattr(card, key) for key in expected} == expected
        assert card.layout == raw['layout'] and card.card_faces == raw.get('card_faces', [])
        assert card.selected_face_index is None and card.image_uri is None
        assert card.characteristic_record == {'version': 1, 'physical': physical, 'values': expected}

    def observe_provider(path):
        encoded = provider(path)
        if path.resolve() == raw_path:
            assert hashlib.sha256(encoded).hexdigest() == RAW_SOURCES[name][3]
            providers.append(RAW_SOURCES[name][3])
            events.append('provider')
        return encoded

    def observe_normalizer(cls, incoming, image_uri, rulings=None):
        target = incoming.get('name') == name
        if target:
            assert incoming == raw and providers == [RAW_SOURCES[name][3]]
            assert image_uri == ('unused:browser-fixture-display' if case == 'bolt'
                                 else 'unused:task13-fixture-display')
        result = normalizer(incoming, image_uri, rulings)
        if target:
            assert result['scryfall_id'] == raw['id'] and result['name'] == name
            for key in ('mana_cost', 'oracle_text', 'type_line', 'layout'):
                assert result[key] == raw[key]
            normalized.append(deepcopy(result))
            events.append('normalizer')
        return result

    def observe_factory(*args, **kwargs):
        nonlocal in_sample
        target = bool(args and args[0] and args[0][0].get('card_name') == name)
        if not target:
            state = factory(*args, **kwargs)
            if case == 'meathook':
                assert not roots and args == ([{'quantity': 60, 'card_name': 'Swamp'}],) * 2
                assert kwargs == {'seed': 209}
                roots.append(state)
            return state
        assert len(normalized) == 1 and not samples and not in_sample
        entry = {**raw, **normalized[0], 'card_name': name, 'quantity': 8,
                 'image_uri': None, 'colors': raw['colors'], 'card_faces': raw.get('card_faces', [])}
        assert args == ([entry], []) and kwargs == {'seed': 0}
        events.append('factory')
        in_sample = True
        try:
            state = factory(*args, **kwargs)
        finally:
            in_sample = False
        assert len(state.cards) == 8 and len(template_births) == 8
        assert len(state.players[1].library) == 1
        for card in state.cards.values():
            retained(card)
        samples.append(state)
        return state

    def observe_birth(card):
        template = card.name == name and in_sample
        posed = card.name == name and card.id == identifier and not in_sample
        if template or posed:
            assert {key: getattr(card, key) for key in physical} == physical
            if template:
                assert card.characteristic_record is None and card.zone == Zone.LIBRARY
                assert card.owner == card.controller == 1 and not card.summoning_sick
            else:
                retained(card)
                assert len(template_births) == 8 and len(samples) == 1
                assert card.zone == zone and card.owner == card.controller == actor
                assert card.summoning_sick and not card.tapped and card.instance_order == 0
        birth(card)
        if template or posed:
            retained(card)
            (template_births if template else pose_births).append(card.id)
            events.append('template_birth' if template else 'pose_birth')

    def observe_settled(*args, **kwargs):
        result = settled(*args, **kwargs)
        assert not roots
        roots.append(result[0])
        return result

    def observe_allocate(state):
        result = allocate(state)
        if roots and state is roots[0]:
            allocated.append(result)
        return result

    def preserve_root(*args, **pose):
        nonlocal identifier
        assert len(roots) == 1
        if case == 'bolt':
            identifier = pose['id']
            assert args == (name,) and pose == dict(id=identifier, owner=actor, controller=actor, zone=zone)
            assert allocated[-1] == identifier and allocated.count(identifier) == 1
        else:
            assert args == () and pose == {}
        # Bolt's original allocation has ALREADY happened while evaluating id=.
        before = pickle.dumps(roots[0], protocol=5)
        allocations_before = list(allocated)
        card = materialize(*args, **pose)
        assert pickle.dumps(roots[0], protocol=5) == before and allocated == allocations_before
        retained(card)
        preserved.append(card)
        return card

    def before_consumer(state):
        assert len(roots) == 1 and state is roots[0]
        card = state.cards[identifier]
        assert len(preserved) == 1 and card is preserved[0]
        retained(card)
        assert card.id == identifier and card.owner == card.controller == actor and card.zone == zone
        assert getattr(state.players[actor], zone.value).count(identifier) == 1
        assert card.summoning_sick and not card.tapped and not card.is_token
        assert card.counters == card.counter_timestamps == card.printed_characteristics == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.entered_turn == card.zone_change_sequence == 0
        assert card.battlefield_incarnation is None
        assert providers == [RAW_SOURCES[name][3]] and len(normalized) == len(samples) == 1
        assert len(template_births) == 8 and pose_births == [identifier]
        assert events == ['provider', 'normalizer', 'factory'] + ['template_birth'] * 8 + ['pose_birth']
        raise BeforeConsumer()

    def observe_snapshot(state, *args, **kwargs):
        if roots and state is roots[0] and identifier in state.cards:
            before_consumer(state)
        return snapshot(state, *args, **kwargs)

    def observe_checked(state, rules, player_id, action, *args, **kwargs):
        if roots and state is roots[0] and action.get('card_id') == identifier:
            assert player_id == 1 and action == {
                'type': 'cast_spell', 'card_id': identifier, 'targets': {'x_value': 2}}
            before_consumer(state)
        return checked(state, rules, player_id, action, *args, **kwargs)

    def observe_persist(controller):
        if game_data and controller is game_data[1]:
            assert controller.state.priority_player == actor
            assert controller.state.players[actor].mana_pool['R'] == 1
            before_consumer(controller.state)
        return persist(controller)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_bytes', observe_provider)
        patch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalizer))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(MatchState, 'allocate_object_id', observe_allocate)
        patch.setattr(module, helper_name, preserve_root)
        if case == 'vraska':
            patch.setattr(vraska, 'settled_state', observe_settled)
            patch.setattr(vraska, 'serialize_match_snapshot', observe_snapshot)
        elif case == 'meathook':
            patch.setattr(meathook, 'checked_action', observe_checked)
        else:
            # The original function imports this name LOCALLY on invocation.
            patch.setattr(api_inputs, 'persist', observe_persist)
        with pytest.raises(BeforeConsumer):
            if case == 'vraska':
                vraska.test_full_canonical_vraska_complete_admission_and_checked_root_are_atomic()
            elif case == 'meathook':
                meathook.test_printed_meathook_etb_uses_announced_x_not_other_abilities()
            else:
                shield.test_http_virtual_shield_choice_survives_sqlite_restore_and_rejects_wrong_owner(game_data, player)
    assert official(name) == raw
