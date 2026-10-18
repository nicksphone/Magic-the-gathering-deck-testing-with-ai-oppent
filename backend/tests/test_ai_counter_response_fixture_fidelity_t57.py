"""Observe the original checked consumer; expected printing comes from RAW."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.copiable_values import values as copiable_values
from tests import test_ai_stack_response_delta as stack_original
from tests import test_ai_strategic_score_reuse as reuse_original


FIXTURES = Path(__file__).parent / 'fixtures'
SEED_BYTES = (FIXTURES / 'knowledge_profiles/seed155-scryfall.jsonl').read_bytes()
assert hashlib.sha256(SEED_BYTES).hexdigest() == '194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732'
PROVENANCE_BYTES = (FIXTURES / 'library_canonical_88/PROVENANCE.json').read_bytes()
assert hashlib.sha256(PROVENANCE_BYTES).hexdigest() == '2c2750acb82ff6746cfbb4cb49c6118f276e9129fd2c819cbc2b5187e0b22f76'
PROOF = json.loads(PROVENANCE_BYTES)['objects']['Counterspell']
RAW = json.loads(SEED_BYTES.splitlines()[PROOF['source_line'] - 1])
assert hashlib.sha256(json.dumps(RAW, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False).encode()).hexdigest() == '87c5de7dc9a4472644d597d6212310c86d25fe8697150dd7e78263eb989f036e'
assert RAW['id'] == PROOF['id'] and RAW['oracle_id'] == PROOF['oracle_id']
assert RAW['name'] == 'Counterspell' and RAW['layout'] == 'normal'
assert {'id', 'oracle_id', 'legalities', 'set', 'uri', 'scryfall_uri',
        'image_uris', 'type_line', 'oracle_text', 'colors', 'keywords'} <= RAW.keys()


def _observe_first_checked_counter(monkeypatch, original, seat):
    real = original.checked_action
    seen = []

    def forward(state, engine, actor, action, *args, **kwargs):
        if not seen and 'counter' in state.cards:
            card = state.cards['counter']
            assert (actor, action['type'], action['card_id']) == (seat, 'cast_spell', 'candidate')
            assert (card.id, card.owner, card.controller, card.zone) == ('counter', 3-seat, 3-seat, Zone.HAND)
            assert (card.summoning_sick, card.instance_order, card.zone_change_sequence,
                    card.tapped, card.counters) == (True, 0, 0, False, {})
            expected = {
                'name': RAW['name'], 'mana_cost': RAW['mana_cost'],
                'type_line': RAW['type_line'],
                'types': RAW['type_line'].split('\u2014', 1)[0].split(),
                'power': RAW.get('power'), 'toughness': RAW.get('toughness'),
                'printed_power': RAW.get('power'), 'printed_toughness': RAW.get('toughness'),
                'loyalty': RAW.get('loyalty'), 'oracle_text': RAW['oracle_text'],
                'keywords': deepcopy(RAW['keywords']), 'colors': deepcopy(RAW['colors']),
            }
            assert {key: deepcopy(getattr(card, key)) for key in expected} == expected
            physical = {**deepcopy(expected), 'card_faces': deepcopy(RAW.get('card_faces') or []),
                        'layout': RAW['layout'], 'selected_face_index': None,
                        'image_uri': RAW['image_uris']['normal']}
            assert {key: deepcopy(getattr(card, key)) for key in physical} == physical
            assert card.printed_characteristics == {} and card.knowledge_snapshot == {}
            record = {'version': 1, 'physical': physical, 'values': expected}
            assert card.characteristic_record == record
            copied = copiable_values(card)
            assert copied == expected
            copied['colors'].append('R')  # Returned-value mutation, never a card edit.
            assert card.characteristic_record == record and card.colors == RAW['colors']
            before = serialize_match_snapshot(state)
            result = real(state, engine, actor, action, *args, **kwargs)
            assert serialize_match_snapshot(state) == before
            seen.append(card.id)
            return result
        return real(state, engine, actor, action, *args, **kwargs)

    monkeypatch.setattr(original, 'checked_action', forward)
    return seen


@pytest.mark.parametrize('seat', [1, 2])
def test_stack_delta_original_checked_consumer_receives_full_counterspell(monkeypatch, seat):
    seen = _observe_first_checked_counter(monkeypatch, stack_original, seat)
    stack_original.test_real_counter_response_is_negative_and_score_offset_invariant(seat)
    assert seen == ['counter']


@pytest.mark.parametrize('seat', [1, 2])
def test_score_reuse_original_checked_consumer_receives_full_counterspell(monkeypatch, seat):
    seen = _observe_first_checked_counter(monkeypatch, reuse_original, seat)
    reuse_original.test_supplied_baseline_preserves_delta_and_avoids_root_revaluation(seat, True)
    assert seen == ['counter']
