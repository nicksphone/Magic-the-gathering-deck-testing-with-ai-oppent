"""Observe the original mode tests' named cards before their real consumers."""
import hashlib
import json
from pathlib import Path

import pytest

from tests import test_cast_choice_modes as original
from tests.canonical_positive_fixtures import raw_card


FIXTURES = Path(__file__).parent / 'fixtures'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
CRYPTIC_SHA = 'fc9c7da365cf96777fcc285fcbc741fb1ad98e2627f063013618ead70897ac2a'
IZZET_SHA = '08e925516702e32a190f344cf2b239a99670d6018c03071f8551b124466f3353'
IZZET_SUBJECTS = (
    ('test_choose_one_mode_with_no_target_remains_castable', 'Izzet Charm', 'legal_moves'),
    ('test_izzet_charm_discard_choice_uses_hand_after_drawing', 'Izzet Charm', 'checked_action'),
)
SUBJECTS = (
    ('test_mode_specific_hints_only_expose_targets_for_selected_mode', 'Drown in the Loch', 'build_cast_hints'),
    ('test_planeswalker_cast_does_not_require_x_value_from_loyalty_text', 'Ugin, the Spirit Dragon', 'inspect_target_hints'),
    ('test_memory_deluge_does_not_require_x_value_for_cast', 'Memory Deluge', 'inspect_target_hints'),
    ('test_shark_typhoon_does_not_require_x_value_for_cast', 'Shark Typhoon', 'inspect_target_hints'),
    ('test_non_divide_x_spell_does_not_auto_set_divide_total', 'March of Otherworldly Light', 'enrich_divide_total'),
    ('test_cryptic_command_can_choose_two_untargeted_modes_without_targets', 'Cryptic Command', 'legal_moves'),
    ('test_cryptic_command_counter_then_draw_resolves_both_modes', 'Cryptic Command', 'checked_action'),
    ('test_cryptic_command_draw_mode_fizzles_when_its_only_target_disappears', 'Cryptic Command', 'checked_action'),
    ('test_choose_one_spell_with_no_legal_mode_is_not_offered', 'Drown in the Loch', 'legal_moves'),
) + IZZET_SUBJECTS


def official(name):
    if name == 'Izzet Charm':
        data = (FIXTURES / 'cast_choice_modes/izzet-charm-scryfall-raw.json').read_bytes()
        proof = json.loads((FIXTURES / 'cast_choice_modes/PROVENANCE.json').read_bytes())
        assert hashlib.sha256(data).hexdigest() == IZZET_SHA == proof['response_sha256']
        return json.loads(data)
    if name != 'Cryptic Command':
        return raw_card(name)
    rows = json.loads((FIXTURES / 'counter_native_frames/canonical.json').read_bytes())
    proof = json.loads((FIXTURES / 'counter_native_frames/provenance.json').read_bytes())
    raw = rows[name]
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert digest == CRYPTIC_SHA == proof['cards'][name]['canonical_fullrow_sha256']
    return raw


def actual_input(monkeypatch, test_name, name, boundary):
    seen = []

    class BeforeConsumer(BaseException):
        pass

    def capture(*args, **kwargs):
        if boundary == 'enrich_divide_total':
            card = args[0]
        elif boundary in ('legal_moves', 'checked_action'):
            state = args[1] if boundary == 'legal_moves' else args[0]
            matches = [card for card in state.cards.values() if card.name == name]
            if not matches:
                return delegate(*args, **kwargs)
            assert len(matches) == 1
            card = matches[0]
        else:
            card = args[1]
        assert card.name == name
        seen.append(card)
        raise BeforeConsumer

    owner = original.RulesEngine if boundary == 'legal_moves' else original
    delegate = getattr(owner, boundary)
    with monkeypatch.context() as patch:
        patch.setattr(owner, boundary, capture)
        with pytest.raises(BeforeConsumer):
            getattr(original, test_name)()
    assert len(seen) == 1
    return seen[0]


@pytest.mark.parametrize('test_name,name,boundary', SUBJECTS, ids=[row[0] for row in SUBJECTS])
def test_actual_named_input_has_complete_official_printed_facts(monkeypatch, test_name, name, boundary):
    card = actual_input(monkeypatch, test_name, name, boundary)
    raw = official(name)
    keys = ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout')
    assert {key: getattr(card, key) for key in keys} == {key: raw[key] for key in keys}
    assert card.card_faces == raw.get('card_faces', [])
    assert card.printed_power == raw.get('power') and card.printed_toughness == raw.get('toughness')
    assert card.loyalty == (int(raw['loyalty']) if raw.get('loyalty') is not None else None)
    assert card.owner == card.controller == 1 and card.zone == original.Zone.HAND


def test_original_island_decks_pass_complete_facts_to_factory(monkeypatch):
    before = original.MatchFactory.from_decks
    seen = []

    def capture(first, second, *args, **kwargs):
        raw = official('Island')
        for deck in (first, second):
            assert deck == [{**raw, 'card_name': raw['name'], 'quantity': 60}]
        seen.append(True)
        return before(first, second, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(original.MatchFactory, 'from_decks', capture)
        original._state()
    assert seen == [True]


def test_existing_full_sources_are_pinned_and_independent():
    data = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    proof = json.loads((FIXTURES / 'knowledge_profiles/PROVENANCE.json').read_bytes())
    assert proof['snapshot_sha256'] == SEED_SHA and proof['oracle_modified'] is False
    for name in sorted({row[1] for row in SUBJECTS} | {'Island'}):
        raw = official(name)
        assert raw['name'] == name and raw['object'] == 'card'
        assert raw['id'] and raw['oracle_id'] and raw['legalities']
        raw['legalities'].clear()
        assert official(name)['legalities']


def test_original_consumer_inputs_do_not_share_mutable_printed_metadata(monkeypatch):
    test_name, name, boundary = SUBJECTS[1]
    first = actual_input(monkeypatch, test_name, name, boundary)
    second = actual_input(monkeypatch, test_name, name, boundary)
    assert first is not second
    first.colors.append('NONCANONICAL INDEPENDENCE SENTINEL')
    first.counters['independence'] = 1
    assert second.colors == official(name)['colors'] and second.counters == {}


@pytest.mark.parametrize('test_name,name,boundary', IZZET_SUBJECTS)
def test_izzet_actual_functions_send_full_raw_to_template_factory(monkeypatch, test_name, name, boundary):
    delegate = original.MatchFactory.from_decks
    seen = []

    def capture(first, second, *args, **kwargs):
        if any(row.get('name') == name for row in first):
            raw = official(name)
            assert first == [{**raw, 'quantity': 8, 'card_name': name}]
            assert second == [] and kwargs == {'seed': 0}
            seen.append(first[0])
        return delegate(first, second, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(original.MatchFactory, 'from_decks', capture)
        getattr(original, test_name)()
    assert len(seen) == 1
    assert {key: value for key, value in seen[0].items() if key not in ('quantity', 'card_name')} == official(name)


@pytest.mark.parametrize('test_name,name,boundary', IZZET_SUBJECTS)
def test_izzet_original_consumer_inputs_are_independent(monkeypatch, test_name, name, boundary):
    first = actual_input(monkeypatch, test_name, name, boundary)
    second = actual_input(monkeypatch, test_name, name, boundary)
    assert first is not second
    assert first.colors == second.colors == official(name)['colors']
    first.colors.clear()
    first.counters['independence'] = 1
    assert second.colors == official(name)['colors'] and second.counters == {}
    assert original._official_card(name) == official(name)


def test_izzet_checked_paid_and_discard_boundaries_receive_official_card(monkeypatch):
    delegate = original.checked_action
    seen = []
    raw = official('Izzet Charm')

    def capture(state, engine, player_id, action):
        cards = [card for card in state.cards.values() if card.name == raw['name']]
        assert len(cards) == 1
        card = cards[0]
        keys = ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout')
        assert {key: getattr(card, key) for key in keys} == {key: raw[key] for key in keys}
        assert card.owner == card.controller == player_id == 1
        seen.append((action['type'], card.zone))
        after = delegate(state, engine, player_id, action)
        if action['type'] == 'cast_spell':
            assert after.players[1].mana_pool == {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
            assert any(item.source_card_id == card.id for item in after.stack)
        return after

    with monkeypatch.context() as patch:
        patch.setattr(original, 'checked_action', capture)
        original.test_izzet_charm_discard_choice_uses_hand_after_drawing()
    assert seen == [('cast_spell', original.Zone.HAND), ('choose_mechanic', original.Zone.STACK)]


def test_izzet_full_raw_response_provenance_and_loader_are_independent():
    raw = official('Izzet Charm')
    proof = json.loads((FIXTURES / 'cast_choice_modes/PROVENANCE.json').read_bytes())
    assert proof['provider'] == 'Scryfall' and proof['http_status'] == 200
    assert proof['request_url'] == 'https://api.scryfall.com/cards/named?exact=Izzet%20Charm'
    assert proof['spacing_before_request_seconds'] >= 0.25
    assert proof['request_count'] == 1 and proof['retries'] == 0
    assert proof['oracle_modified'] is False and proof['response_bytes'] == 4990
    assert raw['id'] == proof['id'] and raw['oracle_id'] == proof['oracle_id']
    assert raw['object'] == 'card' and raw['legalities'] and raw['image_uris']
    assert len(raw) > 50
    first = original._official_card(raw['name'])
    second = original._official_card(raw['name'])
    assert first == second == raw and first is not second
    first['colors'].clear()
    first['legalities'].clear()
    assert second == original._official_card(raw['name']) == official(raw['name'])
