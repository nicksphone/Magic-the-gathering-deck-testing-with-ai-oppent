"""Observe four named positive inputs before native printed-fact capture."""
from copy import deepcopy
from importlib import import_module
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import CardInstance, Zone


FIXTURES = Path(__file__).parent / 'fixtures'
SUBJECTS = (
    ('test_aftermath_casts',
     'test_aftermath_waits_for_resumed_draw_choices_before_exiling',
     'Stinkweed Imp', 'stinkweed', 1, Zone.GRAVEYARD),
    ('test_aftermath_casts',
     'test_cooperate_retarget_choice_resumes_then_exiles_its_own_card',
     'Shock', 'target-shock', 2, Zone.STACK),
    ('test_damage_replacements',
     'test_noncombat_damage_replacement_puts_minus_counters_on_opposing_creature',
     'Shock', 'spell', 1, Zone.STACK),
    ('test_damage_replacements',
     'test_noncombat_damage_replacement_does_not_apply_to_controller_creature',
     'Shock', 'spell-own', 1, Zone.STACK),
)


def official(name):
    if name == 'Stinkweed Imp':
        path = FIXTURES / 'trigger_instruction_product/stinkweed-imp.json'
        pin = '3a12356ed9fa1de98b56500f5c0bb3a26f3ef6949e549e81184441ba19dab1e9'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == pin
        raw = json.loads(data)
        expected_id = '2ab08d69-210b-4b06-88a2-45281a1a4e1e'
        expected_oracle = 'e005bc76-4985-4ec6-b9f6-cf6d0d9f5df4'
    else:
        assert name == 'Shock'
        path = FIXTURES / 'browser_inline26/canonical.jsonl'
        pin = '3c0ac6f8912b171a0712ed3fb4d17aafae3d5e5190530e6ad960f8c147369fdd'
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == pin
        raw = json.loads(data.splitlines()[32])
        expected_id = 'b23900fb-efe9-43ab-9f67-4545dd01fb9c'
        expected_oracle = 'a9d288b8-cdc1-4e55-a0c9-d6edfc95e65d'
    assert raw['object'] == 'card' and raw['name'] == name
    assert raw['id'] == expected_id and raw['oracle_id'] == expected_oracle
    return raw


@pytest.mark.parametrize('module_name,test_name,name,object_id,seat,zone', SUBJECTS,
                         ids=[row[1] for row in SUBJECTS])
def test_actual_named_input_has_full_printing_before_capture(
        monkeypatch, module_name, test_name, name, object_id, seat, zone):
    original = import_module('tests.' + module_name)
    raw = official(name)
    expected = {key: raw[key] for key in
                ('name', 'mana_cost', 'oracle_text', 'type_line', 'colors', 'layout')}
    expected.update(
        types=raw['type_line'].split(' \u2014 ', 1)[0].split(),
        power=int(raw['power']) if raw.get('power') is not None else None,
        toughness=int(raw['toughness']) if raw.get('toughness') is not None else None,
        printed_power=raw.get('power'), printed_toughness=raw.get('toughness'),
        loyalty=None, keywords=['flying'] if name == 'Stinkweed Imp' else [],
        card_faces=raw.get('card_faces', []), selected_face_index=None,
    )
    before = CardInstance.__post_init__
    native_births, seen = [], []

    class BeforeConsumer(BaseException):
        pass

    def capture(card):
        if card.name == name:
            assert {key: getattr(card, key) for key in expected} == expected
            if card.characteristic_record is None:
                native_births.append(deepcopy(expected))
            else:
                physical = card.characteristic_record['physical']
                assert {key: physical[key] for key in expected} == expected
            if card.id == object_id:
                assert native_births, 'Full printing must precede native capture'
                assert (card.owner, card.controller, card.zone) == (seat, seat, zone)
                assert card.summoning_sick and not card.tapped and card.counters == {}
                seen.append(card.id)
                raise BeforeConsumer
        return before(card)

    with monkeypatch.context() as patch:
        patch.setattr(CardInstance, '__post_init__', capture)
        with pytest.raises(BeforeConsumer):
            getattr(original, test_name)()
    assert seen == [object_id]
