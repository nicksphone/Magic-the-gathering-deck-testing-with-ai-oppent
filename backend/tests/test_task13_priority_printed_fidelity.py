"""Four printed-input sites; native witnesses run only in the semantic gate."""
from importlib import import_module
import hashlib
import json
from pathlib import Path
import pickle

import pytest

from game_state.state import CardInstance, MatchFactory, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
RECORDS = {
    'Boros Swiftblade': ('browser_inline26/canonical.jsonl',
        '3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd',
        'line', 13, '6135a9f2-e86d-4a34-857e-adea3c722fea',
        '377e4dad-866b-4e02-8c10-072bf7f000be',
        '818014cfaae1ae4ab856bec3d70e8d568906a86c4b5a9f26bfe68c0b12bdbe6e'),
    'Monastery Swiftspear': ('knowledge_profiles/seed155-scryfall.jsonl', SEED_SHA,
        'name', 'Monastery Swiftspear', 'd6bfa227-4309-40ed-952c-279595eab17e',
        'dafd2713-d1bc-474b-b390-d2ff20b5375e',
        '258c54a794d0afb52cdfb383dfec82bf6aef9da38e05799cd9931774120f8a54'),
    'Think Twice': ('nth_spell_triggers/canonical.json',
        '3c865aae6e0e85af644d38f3c0f1900fc71fad502b8e335b1085ec8ee2f04d10',
        'key', 'Think Twice', '85835de4-66ea-4ba1-87ca-6bcec2a8660a',
        'fa85c5a2-8e83-4624-a35a-a0bbf17ecbb4',
        '8f35730528f108ce4e4ad0797dbabc210c36365f63a5bf7b4328198c9bbcc636'),
    'Island': ('knowledge_profiles/seed155-scryfall.jsonl', SEED_SHA,
        'line', 50, '1335d293-3dd2-4f13-bd2c-22181f4528ee',
        'b2c6aa39-2d2a-459c-a555-fb48ba993373',
        '932ef67074504645e2ddf2ceefcb9e65aa3b6938c6f6c42cb226dbdbe5b30d6b'),
}
SITES = (
    ('test_autoplay_progression', 'test_autoplay_preserves_first_strike_priority_window',
     'creature', 'Boros Swiftblade'),
    ('test_combat', 'test_priority_passes_apply_unblocked_combat_damage_once',
     'card', 'Monastery Swiftspear'),
    ('test_human_auto_progress', 'test_payable_end_step_instant_preserves_control_window',
     'card', 'Think Twice'),
    ('test_human_auto_progress', 'test_payable_end_step_instant_preserves_control_window',
     'land', 'Island'),
)


def official(name):
    filename, pin, kind, location, identity, oracle, object_pin = RECORDS[name]
    data = (FIXTURES / filename).read_bytes()
    assert hashlib.sha256(data).hexdigest() == pin
    if kind == 'line':
        raw = json.loads(data.splitlines()[location - 1])
    elif kind == 'name':
        rows = [json.loads(line) for line in data.splitlines()]
        matches = [row for row in rows if row['name'] == location]
        assert len(matches) == 1
        raw = matches[0]
    else:
        assert kind == 'key'
        raw = json.loads(data)[location]
    assert (raw['object'], raw['name'], raw['id'], raw['oracle_id']) == (
        'card', name, identity, oracle)
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == object_pin
    return raw


NATIVE_CASES = [('boros', 1, None), ('swiftspear', 1, None)] + [
    ('human', seat, pooled) for seat in (1, 2) for pooled in (True, False)]


@pytest.mark.parametrize('kind,seat,pooled', NATIVE_CASES)
def test_original_priority_inputs_keep_printing_and_pose(monkeypatch, kind, seat, pooled):
    site = SITES[0 if kind == 'boros' else 1 if kind == 'swiftspear' else 2]
    original = import_module('tests.' + site[0])
    target_id = 'swiftblade' if kind == 'boros' else 'swiftspear' if kind == 'swiftspear' else 'think'
    targets = {target_id: (site[3], seat, Zone.HAND if kind == 'human' else Zone.BATTLEFIELD,
                           kind != 'boros')}
    if kind == 'human' and not pooled:
        targets.update({f'island-{index}': ('Island', seat, Zone.BATTLEFIELD, True)
                        for index in range(2)})
    factory, post_init = MatchFactory.from_decks, CardInstance.__post_init__
    raw_seen, poses, states, preservation = [], [], [], []

    class BeforeConsumer(BaseException):
        pass

    def capture_factory(first, second, *args, **kwargs):
        if first and first[0].get('object') == 'card':
            name = first[0]['name']
            assert name in {row[0] for row in targets.values()}
            raw = official(name)
            assert all(first[0].get(key) == value for key, value in raw.items())
            assert len(first) == 1 and first[0]['quantity'] == 8
            assert second == [] and args == () and kwargs == {'seed': 0}
            raw_seen.append(name)
        result = factory(first, second, *args, **kwargs)
        if not states and first and first[0].get('object') != 'card':
            states.append(result)
        return result

    def capture_card(card):
        if card.id in targets:
            name, owner, zone, sick = targets[card.id]
            raw = official(name)
            expected = {key: raw[key] for key in
                        ('name', 'mana_cost', 'type_line', 'oracle_text', 'colors', 'layout')}
            expected.update(
                types=raw['type_line'].split(' \u2014 ', 1)[0].removeprefix('Basic ').split(),
                power=int(raw['power']) if raw.get('power') is not None else None,
                toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
                printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
                loyalty=None, card_faces=raw.get('card_faces', []), selected_face_index=None)
            assert {key: getattr(card, key) for key in expected} == expected
            assert card.characteristic_record is not None and name in raw_seen
            physical = card.characteristic_record['physical']
            assert {key: physical[key] for key in expected} == expected
            assert physical['keywords'] == card.keywords
            assert (card.owner, card.controller, card.zone) == (owner, owner, zone)
            assert card.summoning_sick is sick and not card.tapped and card.counters == {}
            assert card.instance_order == 0 and card.image_uri is None
            poses.append(card.id)
            if card.id == target_id and kind != 'human':
                raise BeforeConsumer
        return post_init(card)

    with monkeypatch.context() as patch:
        patch.setattr(MatchFactory, 'from_decks', staticmethod(capture_factory))
        patch.setattr(CardInstance, '__post_init__', capture_card)
        if kind == 'human':
            think = original._think_twice_card

            def preserved_think(owner):
                assert len(states) == 1
                before = pickle.dumps(states[0])
                card = think(owner)
                assert pickle.dumps(states[0]) == before, 'Do not allocate IDs, advance RNG or mutate original state'
                assert card.id == 'think' and poses[-1] == card.id
                preservation.append(True)
                raise BeforeConsumer

            patch.setattr(original, '_think_twice_card', preserved_think)
        with pytest.raises(BeforeConsumer):
            if kind == 'boros':
                getattr(original, site[1])(monkeypatch)
            elif kind == 'human':
                getattr(original, site[1])(seat, pooled)
            else:
                getattr(original, site[1])()
    assert poses == (['island-0', 'island-1', 'think'] if kind == 'human' and not pooled else [target_id])
    assert raw_seen == (['Island', 'Island', 'Think Twice'] if kind == 'human' and not pooled else [site[3]])
    assert preservation == ([True] if kind == 'human' else [])
