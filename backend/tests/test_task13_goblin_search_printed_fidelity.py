"""Full RAW and native birth, not a rules replacement or a synthetic-card waiver."""
import hashlib
import json
from pathlib import Path
import random

import pytest

from game_state.state import CardInstance, MatchFactory, Zone
from tests import test_interactions_expanded as subject


FIXTURES = Path(__file__).parent / 'fixtures'
RECORDS = {
    'Goblin Guide': ('knowledge_profiles/seed155-scryfall.jsonl',
                    '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
                    66, '3c0f5411-1940-410f-96ce-6f92513f753a'),
    'Goblin Piledriver': ('goblin_search/goblin-piledriver.json',
                         'b9e415ae9f2c999062caa727f18fc5ea1279976c85b43b2360794e620c5c8a6d',
                         67, '4b332e3d-dcf4-4f62-8130-124ec5d23b90'),
    'Mogg War Marshal': ('goblin_search/mogg-war-marshal.json',
                        '10e8bb7a4609be90bc3ecd511e771a308891d4919d610aee42005bc9594ae593',
                        64, '4ebce261-3a53-48f2-a173-0d98c68aff2c'),
    'Lightning Bolt': ('knowledge_profiles/seed155-scryfall.jsonl',
                       '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732',
                       66, '7673784e-db4b-43a1-8d55-1bb9fc1e284f'),
}
SLOTS = ('card-goblin-guide', 'card-goblin-piledriver',
         'card-goblin-war-marshal', 'card-lightning-bolt')
NATIVE_KEYWORDS = {'Goblin Guide': ['haste'], 'Goblin Piledriver': ['protection from blue'],
                   'Mogg War Marshal': [], 'Lightning Bolt': []}
RAW_KEYWORDS = {'Goblin Guide': ['Haste'], 'Goblin Piledriver': ['Protection'],
                'Mogg War Marshal': ['Echo'], 'Lightning Bolt': []}
COPY_FIELDS = ('name', 'mana_cost', 'type_line', 'types', 'power', 'toughness',
               'printed_power', 'printed_toughness', 'loyalty', 'oracle_text', 'keywords', 'colors')


def official(name):
    filename, digest, fields, identity = RECORDS[name]
    data = (FIXTURES / filename).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    rows = list(map(json.loads, data.splitlines())) if filename.endswith('.jsonl') else [json.loads(data)]
    matches = [row for row in rows if row.get('name') == name]
    assert len(matches) == 1
    raw = matches[0]
    assert raw['object'] == 'card' and raw['id'] == identity and len(raw) == fields
    assert raw['keywords'] == RAW_KEYWORDS[name] and raw.get('card_faces', []) == []
    return raw


class BeforeSearch(Exception):
    pass


@pytest.mark.parametrize('name', list(RECORDS), ids=['guide', 'piledriver', 'mogg', 'bolt'])
def test_search_slot_has_complete_raw_before_real_factory_and_scene(monkeypatch, name):
    raw = official(name)
    cid = SLOTS[list(RECORDS).index(name)]
    creature = name != 'Lightning Bolt'
    expected = dict(name=name, mana_cost=raw['mana_cost'], type_line=raw['type_line'],
                    types=['Creature'] if creature else ['Instant'],
                    power=int(raw['power']) if creature else None,
                    toughness=int(raw['toughness']) if creature else None,
                    printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                    loyalty=None, oracle_text=raw['oracle_text'], keywords=NATIVE_KEYWORDS[name],
                    colors=raw['colors'], card_faces=[], layout=raw['layout'],
                    selected_face_index=None, image_uri=None)
    previous_factory, previous_birth = MatchFactory.from_decks, CardInstance.__post_init__
    admitted, private_births, scene_births, worlds = [], [], [], []
    inside_private = False

    def record(card):
        assert card.characteristic_record == {
            'version': 1, 'physical': expected,
            'values': {key: expected[key] for key in COPY_FIELDS}}

    def factory(first, second, *args, **kwargs):
        nonlocal inside_private
        selected = bool(first and first[0].get('object') == 'card'
                        and first[0].get('name') == name)
        if selected:
            assert len(first) == 1 and first[0]['quantity'] == 8 and second == []
            assert args == () and kwargs == {'seed': 0}
            assert all(first[0].get(key) == value for key, value in raw.items())
            admitted.append(name)
            before = random.getstate()
            inside_private = True
            try:
                state = previous_factory(first, second, *args, **kwargs)
            finally:
                inside_private = False
            assert random.getstate() == before
            return state
        state = previous_factory(first, second, *args, **kwargs)
        if not worlds:
            worlds.append((state, state.rng.getstate(), random.getstate(),
                           state.next_object_id, set(state.cards)))
        return state

    def birth(card):
        selected = (inside_private and card.name == name) or card.id == cid
        if selected:
            assert admitted == [name], 'Full RAW must reach the real Factory before birth'
            assert {key: getattr(card, key) for key in expected} == expected
            assert card.zone == Zone.LIBRARY and card.owner == card.controller == 1
        previous_birth(card)
        if selected:
            record(card)
            (private_births if inside_private else scene_births).append(card.id)

    def consume(state, player, effect, payload):
        assert player == 1 and effect == 'search_library' and payload == {'contains': 'Goblin'}
        assert state.players[1].library == list(SLOTS)
        assert admitted == [name] and len(private_births) == 8 and scene_births == [cid]
        card = state.cards[cid]
        assert {key: getattr(card, key) for key in expected} == expected
        assert card.id == cid and card.instance_order == 0 and card.summoning_sick is True
        record(card)
        original, rng, global_rng, next_id, cards = worlds[0]
        assert state is original and state.rng.getstate() == rng and random.getstate() == global_rng
        assert state.next_object_id == next_id and set(state.cards) == cards | set(SLOTS)
        raise BeforeSearch

    monkeypatch.setattr(MatchFactory, 'from_decks', staticmethod(factory))
    monkeypatch.setattr(CardInstance, '__post_init__', birth)
    monkeypatch.setattr(subject, 'resolve_effect', consume)
    with pytest.raises(BeforeSearch):
        subject.test_search_library_returns_all_matching_cards()
