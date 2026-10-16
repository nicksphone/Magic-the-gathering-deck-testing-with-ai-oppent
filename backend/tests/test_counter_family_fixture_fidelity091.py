"""Observe the old whole-module inputs before their real effect consumers."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from card_data.sync import ScryfallSyncService
from game_state.state import MatchFactory, Zone
from rules_engine.engine import RulesEngine
from tests.counter_family_canonical091 import raw_card
from tests.library_canonical_fixtures import PRINTED


COUNTERS = 'test_counter_replacements'
ENTRY = 'test_entry_replacement_order'
SPELL = 'test_spell_entry_counters'
SAGA = 'test_saga_counter_events'
CASES = [
    *[(name, COUNTERS, 'test_printed_permanent_doublers', {'name': name}, 'add_counters')
      for name in ('Doubling Season', 'Corpsejack Menace', 'Branching Evolution', 'Primal Vigor')],
    *[(name, COUNTERS, 'test_plus_counter_adders_do_not_modify_other_kinds',
       {'name': name}, 'add_counters') for name in ('Hardened Scales', 'Kami of Whispered Hopes')],
    ('Vorinclex, Monstrous Raider', COUNTERS, 'test_vorinclex_depends_on_placer_not_player_recipient',
     {'player': 1}, 'add_player_counters'),
    *[(name, COUNTERS, 'test_winding_and_laezel_distinguish_recipient_and_placer', {},
       'add_player_counters') for name in ('Winding Constrictor', "Lae'zel, Vlaakith's Champion")],
    ('Grizzly Bears', COUNTERS, 'test_printed_permanent_doublers',
     {'name': 'Doubling Season'}, 'add_counters'),
    ('Forest', COUNTERS, 'test_kami_modifies_controlled_land_before_animation', {}, 'add_counters'),
    ('Sol Ring', COUNTERS, 'test_constrictor_modifies_only_controlled_artifacts',
     {'recipient': 1, 'expected': 3}, 'add_counters'),
    *[(name, ENTRY, 'test_colored_payment_does_not_offer_compleated_reduction',
       {'name': name}, 'spell') for name in ('Tamiyo, Compleated Sage', 'Nissa, Ascended Animist')],
    ('History of Benalia', SAGA, 'test_turn_based_lore_has_correct_placer_and_effect_provenance',
     {'player': 1, 'name': 'Doubling Season', 'controller': 1, 'expected': 1}, '_advance_sagas'),
    ('Binding the Old Gods', SAGA, 'test_targeted_chapter_generates_ward_above_it_after_human_selection',
     {}, '_advance_sagas'),
    ('Tolarian Terror', SAGA, 'test_targeted_chapter_generates_ward_above_it_after_human_selection',
     {}, '_advance_sagas'),
    ('The Phasing of Zhalfir', SPELL,
     'test_read_ahead_choice_survives_snapshot_and_requires_exact_replaced_lore',
     {'chosen': '1', 'expected': [2]}, 'spell'),
    ('Walking Ballista', SPELL, 'test_blocked_zero_zero_entry_dies_only_after_it_enters', {}, 'spell'),
]


class Consumed(BaseException):
    pass


def expected_card(name):
    raw = raw_card(name)
    normalized = ScryfallSyncService._normalize_payload(
        raw, ScryfallSyncService._extract_remote_image_uri(raw))
    entry = {**raw, **normalized, 'card_name': name, 'quantity': 8,
             'colors': raw['colors'], 'card_faces': json.loads(normalized['card_faces_json'])}
    state = MatchFactory.from_decks([entry], [], seed=0)
    return next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)


@pytest.mark.parametrize('name,module,function,arguments,seam', CASES,
                         ids=[case[0] for case in CASES])
def test_actual_original_first_consumer_has_complete_printed_parent(
        monkeypatch, name, module, function, arguments, seam):
    original = importlib.import_module('tests.' + module)
    expected = expected_card(name)
    owner = RulesEngine if seam == '_advance_sagas' else original
    consumer = getattr(owner, seam)

    def observe(*args, **kwargs):
        state = args[1] if owner is RulesEngine else args[0]
        matches = [card for card in state.cards.values() if card.name == name]
        if matches:
            actual = matches[0]
            mismatches = sorted(field for field in PRINTED
                                if getattr(actual, field) != getattr(expected, field))
            assert not mismatches, (name, mismatches)
            raise Consumed
        return consumer(*args, **kwargs)

    monkeypatch.setattr(owner, seam, observe)
    with pytest.raises(Consumed):
        getattr(original, function)(**arguments)


def test_original_positive_entry_tables_retain_complete_parent_objects():
    root = Path(__file__).parent / 'fixtures'
    for filename in ('compleated_entry.json', 'spell_entry_counters.json', 'saga_chapters.json'):
        for row in json.loads((root / filename).read_text()):
            assert row == raw_card(row['name']), (filename, row['name'])


def test_full_raw_objects_are_fresh_and_keep_complete_bulk_provenance():
    root = Path(__file__).parent / 'fixtures'
    proof = json.loads((root / 'counter_family091/PROVENANCE.json').read_text())
    assert proof['bulk_sha256'] == '17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13'
    for name, record in proof['rows'].items():
        data = (root / record['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record['file_sha256']
        first, second = raw_card(name), raw_card(name)
        assert first == second and first is not second
        assert first['object'] == 'card' and len(first) > 40
        first['legalities'].clear()
        assert second['legalities']
