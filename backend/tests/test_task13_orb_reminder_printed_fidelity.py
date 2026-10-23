"""Native caller-bound input witnesses; not full parser or adventure outcomes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import CardInstance, MatchFactory, Zone, _infer_keywords
from rules_engine.card_types import printed_card_types
from rules_engine.copiable_values import FIELDS, PHYSICAL
from tests import test_multi_target_adventure as adventure
from tests import test_oracle_reminder_boundaries as reminder


TESTS = Path(__file__).parent
SOURCES = {
    'Bloodtithe Harvester': (
        'fixtures/knowledge_profiles/seed155-scryfall.jsonl', 9, 66,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        'a086eb1eeb92eda6ad51aa1c551cc3739ac5207456fdc5b7ccb8e2b1c7e198e8',
        'ae4aec0d-c853-44e6-9f51-cbecf413ea14', '419a8ab2-cff6-4811-a559-8791c9bb3d8e'),
    "Witch's Oven": (
        'fixtures/knowledge_profiles/seed155-scryfall.jsonl', 117, 66,
        '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
        '28665f48c3fcea64e1b0e48b30ce69ceee4aa3e4a4d33f2982220248699c0cd2',
        '04ef8493-d986-45f8-a718-617b028f7ad4', '8fa0fe02-2452-4386-8e0c-165757b0f0a3'),
    'Witchbane Orb': (
        'fixtures/task13_witchbane_orb/witchbane-orb.raw.json', None, 63,
        '98335dd475e759b14a8ed40c911c2e7cdec21787f47947c2d25d1cb88f811750',
        'db55b23bf0042af045162ef1495bea8730f3905b13e5e35d8410925812656746',
        '53e0bf16-62f5-4b62-96e8-bc7e049bcf89', '7411a8f4-b736-482f-886e-5fa671e94e0d'),
}


def official(name):
    path, line, fields, file_sha, object_sha, identifier, oracle_id = SOURCES[name]
    encoded = (TESTS / path).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == file_sha
    raw = json.loads(encoded.splitlines()[line - 1] if line else encoded)
    assert (raw['object'], raw['name'], len(raw), raw['id'], raw['oracle_id']) == (
        'card', name, fields, identifier, oracle_id)
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest() == object_sha
    return raw


@pytest.mark.parametrize('context,name', [
    ('quoted', 'Bloodtithe Harvester'), ('quoted', "Witch's Oven"),
    ('infer', 'Bloodtithe Harvester'), ('infer', "Witch's Oven"),
    ('all-lost', 'Witchbane Orb'), ('one-player', 'Witchbane Orb'), ('reject', 'Witchbane Orb'),
])
def test_original_full_print_before_birth_and_first_consumer(monkeypatch, context, name):
    raw = official(name)
    orb = name == 'Witchbane Orb'
    module, helper = (adventure, '_witchbane_orb') if orb else (reminder, '_card')
    identifier, owner = ('orb', 2) if orb else (name, 1)
    raw_path = (TESTS / SOURCES[name][0]).resolve()
    expected = {key: raw[key] for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors')}
    # This is the real Factory's keyword projection, not Scryfall's catalog tags.
    expected.update(types=printed_card_types(raw['type_line']),
                    power=int(raw['power']) if 'power' in raw else None,
                    toughness=int(raw['toughness']) if 'toughness' in raw else None,
                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                    loyalty=None, keywords=_infer_keywords(raw['oracle_text']))
    physical = {**expected, 'layout': raw['layout'], 'card_faces': raw.get('card_faces', []),
                'selected_face_index': None, 'image_uri': None}
    assert set(expected) == set(FIELDS) and set(physical) == set(PHYSICAL)
    provider, normalizer = Path.read_bytes, ScryfallSyncService._normalize_payload
    factory, birth, materialize = MatchFactory.from_decks, CardInstance.__post_init__, getattr(module, helper)
    state_builder, grant = reminder._state, adventure.grant_player_hexproof
    extract, infer = reminder.extract_activated_abilities, reminder.infer_effect_from_oracle
    snapshot = adventure.serialize_match_snapshot
    roots, providers, normalized, samples, template_births, posed, preserved = [], [], [], [], [], [], []
    grants, preceding, events = [], [], []
    active = in_sample = False

    class BeforeConsumer(BaseException):
        pass

    def retained(card):
        assert {key: getattr(card, key) for key in physical} == physical
        assert card.characteristic_record == {'version': 1, 'physical': physical, 'values': expected}

    def observe_provider(path):
        encoded = provider(path)
        # The two reminder prints share a file; count only the selected call.
        if active and path.resolve() == raw_path:
            assert hashlib.sha256(encoded).hexdigest() == SOURCES[name][3]
            providers.append(SOURCES[name][3])
            events.append('provider')
        return encoded

    def observe_normalizer(cls, incoming, image_uri, rulings=None):
        target = active and incoming.get('name') == name
        if target:
            assert incoming == raw and providers == [SOURCES[name][3]]
            assert image_uri == 'unused:task13-' + ('orb' if orb else 'reminder') + '-display'
        result = normalizer(incoming, image_uri, rulings)
        if target:
            assert result['scryfall_id'] == raw['id']
            for key in ('name', 'mana_cost', 'type_line', 'oracle_text', 'layout'):
                assert result[key] == raw[key]
            normalized.append(deepcopy(result))
            events.append('normalizer')
        return result

    def observe_factory(*args, **kwargs):
        nonlocal in_sample
        target = active and bool(args and args[0] and args[0][0].get('card_name') == name)
        if not target:
            return factory(*args, **kwargs)
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
        assert len(state.cards) == len(template_births) == 8 and len(state.players[1].library) == 1
        for card in state.cards.values():
            retained(card)
        samples.append(state)
        return state

    def observe_birth(card):
        template = active and in_sample and card.name == name
        pose = active and not in_sample and card.id == identifier and card.name == name
        if template or pose:
            assert {key: getattr(card, key) for key in physical} == physical
            if template:
                assert card.characteristic_record is None and card.zone == Zone.LIBRARY
                assert card.owner == card.controller == 1
                assert card.summoning_sick == ('Creature' in expected['types'])
            else:
                retained(card)
                assert len(samples) == 1 and len(template_births) == 8
                assert card.owner == card.controller == owner and card.zone == Zone.BATTLEFIELD
                assert card.summoning_sick and not card.tapped and card.instance_order == 0
        birth(card)
        if template or pose:
            retained(card)
            (template_births if template else posed).append(card)
            events.append('template_birth' if template else 'pose_birth')

    def preserve_input(*args, **kwargs):
        nonlocal active
        if not orb and args != (name,):
            return materialize(*args, **kwargs)
        assert not kwargs and args == (() if orb else (name,)) and not active
        assert len(roots) == (0 if context == 'quoted' else 1)
        before = pickle.dumps(roots[0], protocol=5) if roots else None
        active = True
        try:
            card = materialize(*args, **kwargs)
        finally:
            active = False
        if roots:
            assert pickle.dumps(roots[0], protocol=5) == before
        retained(card)
        preserved.append(card)
        return card

    def observe_state():
        state = state_builder()
        assert not roots
        roots.append(state)
        return state

    def observe_grant(state):
        assert not roots
        roots.append(state)
        result = grant(state)
        assert result is None
        grants.append(True)
        return result

    def before_consumer(state, card):
        assert len(preserved) == len(posed) == 1 and card is preserved[0] is posed[0]
        retained(card)
        assert card.id == identifier and card.owner == card.controller == owner
        assert card.zone == Zone.BATTLEFIELD and card.summoning_sick and not card.tapped and not card.is_token
        assert card.counters == card.counter_timestamps == card.printed_characteristics == {}
        assert card.knowledge_snapshot == {}
        assert card.instance_order == card.static_order == card.effect_timestamp == 0
        assert card.entered_turn == card.zone_change_sequence == 0 and card.battlefield_incarnation is None
        if state is None:
            assert context == 'quoted' and not roots
        else:
            assert len(roots) == 1 and state is roots[0] and state.cards[identifier] is card
            if orb:
                assert state.players[2].battlefield.count(identifier) == 1 and grants == [True]
            else:
                # Preserve the original parser-only scene: cards mapping, no BF list.
                assert all(identifier not in player.battlefield for player in state.players.values())
        if name == "Witch's Oven":
            assert preceding == ['harvester-' + context]
        else:
            assert preceding == []
        assert providers == [SOURCES[name][3]] and len(normalized) == len(samples) == 1
        assert events == ['provider', 'normalizer', 'factory'] + ['template_birth'] * 8 + ['pose_birth']
        raise BeforeConsumer()

    def observe_extract(card, *args, **kwargs):
        if card.id == identifier and card.name == name:
            before_consumer(None, card)
        result = extract(card, *args, **kwargs)
        if name == "Witch's Oven" and card.name == 'Bloodtithe Harvester':
            preceding.append('harvester-quoted')
        return result

    def observe_infer(state, card, player_id, *args, **kwargs):
        if card.id == identifier and card.name == name:
            assert player_id == 1
            before_consumer(state, card)
        result = infer(state, card, player_id, *args, **kwargs)
        if name == "Witch's Oven" and card.name == 'Bloodtithe Harvester':
            preceding.append('harvester-infer')
        return result

    def observe_snapshot(state, *args, **kwargs):
        if roots and state is roots[0] and identifier in state.cards:
            before_consumer(state, state.cards[identifier])
        return snapshot(state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_bytes', observe_provider)
        patch.setattr(ScryfallSyncService, '_normalize_payload', classmethod(observe_normalizer))
        patch.setattr(MatchFactory, 'from_decks', staticmethod(observe_factory))
        patch.setattr(CardInstance, '__post_init__', observe_birth)
        patch.setattr(module, helper, preserve_input)
        if orb:
            patch.setattr(adventure, 'grant_player_hexproof', observe_grant)
            patch.setattr(adventure, 'serialize_match_snapshot', observe_snapshot)
        else:
            patch.setattr(reminder, '_state', observe_state)
            patch.setattr(reminder, 'extract_activated_abilities', observe_extract)
            patch.setattr(reminder, 'infer_effect_from_oracle', observe_infer)
        with pytest.raises(BeforeConsumer):
            if context == 'quoted':
                reminder.test_quoted_token_ability_is_not_extracted_from_creator()
            elif context == 'infer':
                reminder.test_reminder_text_cannot_create_false_draw_life_or_target_effects()
            elif context == 'all-lost':
                adventure.test_meager_meal_all_targets_illegal_goes_to_graveyard()
            elif context == 'one-player':
                adventure.test_meager_meal_one_legal_target_resolves_only_that_effect('player')
            else:
                adventure.test_meager_meal_cannot_target_hexproof_player_at_cast()
    assert official(name) == raw
