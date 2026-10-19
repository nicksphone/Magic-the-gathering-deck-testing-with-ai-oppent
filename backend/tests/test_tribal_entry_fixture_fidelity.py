"""Observe the original tribal tests' real named source before their actions."""
import hashlib
import json
from pathlib import Path

import pytest

import tests.test_tribal_entry_trigger as original
from tests.canonical_positive_fixtures import raw_card


NAME = 'Elvish Warmaster'
SEED_SHA = '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
RAW_SHA = '686c827295fa497372527b45b4119788b1e9c1fa779a16c436020d6e0325e215'
SUBJECTS = (
    original.test_other_elf_triggers_once_after_irrelevant_entries_and_makes_typed_token,
    original.test_first_trigger_stays_used_if_countered_but_resets_next_turn,
    original.test_tribal_activated_bonus_affects_only_current_matching_creatures,
)


@pytest.mark.parametrize('body', SUBJECTS, ids=['entry-snapshot', 'countered', 'activation'])
def test_actual_original_source_has_complete_canonical_rules_before_actions(body, monkeypatch):
    real = original._state
    seen = []

    def observe():
        state = real()
        card = state.cards['watcher']
        raw = raw_card(NAME)
        keys = ('name', 'oracle_text', 'mana_cost', 'type_line', 'colors', 'layout')
        assert {key: getattr(card, key) for key in keys} == {key: raw[key] for key in keys}
        assert card.types == ['Creature'] and card.card_faces == []
        assert (card.power, card.toughness, card.loyalty) == (int(raw['power']), int(raw['toughness']), None)
        assert card.owner == card.controller == 1 and card.zone == original.Zone.BATTLEFIELD
        seen.append(card)
        return state

    with monkeypatch.context() as patch:
        patch.setattr(original, '_state', observe)
        body()
    assert len(seen) == 1


def test_actual_fixture_and_official_objects_are_independent():
    first = original._state().cards['watcher']
    second = original._state().cards['watcher']
    assert first is not second
    first.types.append('Declared protocol independence sentinel')
    first.counters['independence-sentinel'] = 1
    assert second.types == ['Creature'] and second.counters == {}
    raw = raw_card(NAME)
    raw['legalities'].clear()
    raw['colors'].clear()
    again = raw_card(NAME)
    assert again['legalities'] and again['colors'] == ['G']


def test_full_official_source_and_provenance_are_pinned():
    root = Path(__file__).parent / 'fixtures/knowledge_profiles'
    data = (root / 'seed155-scryfall.jsonl').read_bytes()
    assert hashlib.sha256(data).hexdigest() == SEED_SHA
    provenance = json.loads((root / 'PROVENANCE.json').read_bytes())
    assert provenance['snapshot_sha256'] == SEED_SHA
    assert provenance['oracle_modified'] is False and provenance['response_statuses'] == [200, 200, 200]
    rows = [json.loads(line) for line in data.splitlines()]
    raw = raw_card(NAME)
    assert [row for row in rows if row['name'] == NAME] == [raw]
    assert raw['object'] == 'card' and raw['id'] and raw['oracle_id'] and raw['legalities']
    assert raw['rulings_uri'].startswith('https://api.scryfall.com/cards/')
    assert hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == RAW_SHA
