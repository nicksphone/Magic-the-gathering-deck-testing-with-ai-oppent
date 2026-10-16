"""Observe every remaining real-name family at its original first consumer.

The real consumer runs once, then a local sentinel ends this duplicate body.
The original whole module separately retains every action and assertion. This
separates fixture fidelity from any old clause contract contradicted by RAW.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import MatchFactory, Zone
from tests.oracle_effects_positive_fixtures_8d import EXTRA, HERE, raw_card
from tests.oracle_effects_semantic_support_8d import full_raw
from tests.rules_printed_facts_e4 import SOURCES
import tests.test_oracle_effects as original


CASES = (
    ('test_oracle_copy_ability_parsing', 'record_activation_complete',
     ('Rings of Brighthearth',)),
    ('test_lithoform_ability_copy_targets_only_controlled_abilities', 'legal_moves',
     ('Lithoform Engine', 'Prodigal Pyromancer', 'Prodigal Pyromancer')),
    ('test_copy_target_permanent_spell_excludes_instants_and_sorceries', 'legal_moves',
     ('Lithoform Engine',)),
    ('test_oracle_target_hints_include_nonland_permanent_targets', 'inspect_target_hints',
     ('Vindicate', 'Island')),
    ('test_nonland_permanent_removal_chooses_nonland_target', 'infer_effect_from_oracle',
     ('Vindicate', 'Island')),
    ('test_oracle_can_return_graveyard_artifact_or_enchantment', 'inspect_target_hints',
     ('Open the Vaults',)),
    ('test_oracle_can_return_generic_permanent_from_graveyard', 'inspect_target_hints',
     ('Tropical Island',)),
    ('test_oracle_search_library_can_put_creature_onto_battlefield', 'infer_effect_from_oracle',
     ('Collected Company', 'Elvish Mystic')),
    ('test_oracle_search_library_honors_count_and_mana_value_on_battlefield_tutors', 'infer_effect_from_oracle',
     ('Llanowar Elves', 'Elvish Mystic', 'Steel Hellkite')),
    ('test_oracle_mass_artifact_and_enchantment_removal_is_inferred', 'infer_effect_from_oracle',
     ('Purify',)),
    ('test_nissa_loyalty_lines_animate_land_and_put_green_creature', 'infer_effect_from_oracle',
     ('Nissa, Who Shakes the World', 'Forest')),
    ('test_real_noncreature_land_loyalty_clause_uses_legal_target_and_keywords', 'legal_moves',
     ('Nissa, Who Shakes the World',)),
    ('test_light_up_the_stage_style_exiles_cards_with_temporary_play_permission', 'infer_effect_from_oracle',
     ('Light Up the Stage',)),
    ('test_torrential_gearhulk_style_casts_target_instant_from_graveyard', 'infer_effect_from_oracle',
     ('Torrential Gearhulk', 'Lightning Bolt')),
)
FIELDS = ('name', 'oracle_text', 'mana_cost', 'type_line', 'types', 'power',
          'toughness', 'printed_power', 'printed_toughness', 'loyalty', 'colors',
          'keywords', 'layout', 'card_faces', 'selected_face_index',
          'printed_characteristics')


class Consumed(Exception):
    """Test-only stop after the first genuine consumer, never a game result."""


def capture(case, monkeypatch):
    body_name, boundary, names = case
    records = []

    def observe(state, source=None):
        candidates = list(state.cards.values())
        # Legacy Nissa's separate clause Proxy is protocol, not a second card.
        if source is not None and not any(source.name == card.name for card in candidates):
            candidates.append(source)
        for name in names:
            matches = [card for card in candidates if card.name == name]
            if name in ('Island', 'Forest'):
                matches = [card for card in matches if card.zone == Zone.BATTLEFIELD]
            for card in matches:
                if all(card is not record['card'] for record in records):
                    records.append({'card': card, 'printed': {
                        field: deepcopy(getattr(card, field, '<MISSING>')) for field in FIELDS}})

    with monkeypatch.context() as patch:
        if boundary == 'record_activation_complete':
            from rules_engine import activation_copy

            real = activation_copy.record_activation_complete

            def consume(state, item, *args, **kwargs):
                observe(state)
                real(state, item, *args, **kwargs)
                raise Consumed

            patch.setattr(activation_copy, boundary, consume)
        elif boundary == 'legal_moves':
            real = original.RulesEngine.legal_moves

            def consume(engine, state, *args, **kwargs):
                observe(state)
                real(engine, state, *args, **kwargs)
                raise Consumed

            patch.setattr(original.RulesEngine, boundary, consume)
        else:
            real = getattr(original, boundary)

            def consume(state, source, *args, **kwargs):
                observe(state, source)
                real(state, source, *args, **kwargs)
                raise Consumed

            patch.setattr(original, boundary, consume)
        with pytest.raises(Consumed):
            getattr(original, body_name)()
    assert sorted(record['printed']['name'] for record in records) == sorted(names)
    return records


def expected(name):
    raw = full_raw(name)
    state = MatchFactory.from_decks([{**raw, 'card_name': name, 'quantity': 8}], [], seed=100)
    card = next(card for card in state.cards.values() if card.zone == Zone.LIBRARY)
    return {field: deepcopy(getattr(card, field)) for field in FIELDS}


@pytest.mark.parametrize('case', CASES, ids=[case[0].removeprefix('test_') for case in CASES])
def test_actual_first_consumer_has_complete_official_printed_facts(case, monkeypatch):
    for record in capture(case, monkeypatch):
        assert record['printed'] == expected(record['printed']['name'])


def test_all_four_new_raw_bodies_and_http_provenance_are_pinned():
    proof = json.loads((HERE / 'PROVENANCE.json').read_bytes())
    assert len(proof['records']) == len(EXTRA) == 4
    for name, (filename, digest) in EXTRA.items():
        assert hashlib.sha256((HERE / filename).read_bytes()).hexdigest() == digest
        row = raw_card(name)
        assert row['object'] == 'card' and row['name'] == name
        assert row['id'] and row['oracle_id'] and row['legalities'] and row['scryfall_uri']
        item = next(item for item in proof['records'] if item['name'] == name)
        assert item['http_status'] == 200 and item['body_sha256'] == digest
        assert item['retries'] == 0 and item['redirects_allowed'] is False


def test_every_existing_full_raw_binding_and_provenance_file_remains_pinned():
    names = {name for _, _, family in CASES for name in family} - EXTRA.keys() - {'Purify'}
    fixtures = Path(original.__file__).parent / 'fixtures'
    for name in names:
        row = raw_card(name)
        source = SOURCES[name]
        assert hashlib.sha256((fixtures / source['file']).read_bytes()).hexdigest() == source['sha256']
        assert row['object'] == 'card' and row['name'] == name
        assert row['id'] and row['oracle_id'] and row['legalities']
        for receipt in source['provenance']:
            path = Path(original.__file__).parents[2] / receipt['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt['file_sha256']


def test_actual_consumed_printed_mutables_and_raw_are_independent(monkeypatch):
    raw_before = raw_card('Lithoform Engine')
    first = capture(CASES[1], monkeypatch)[0]['card']
    second = capture(CASES[1], monkeypatch)[0]['card']
    assert first is not second and first.colors is not second.colors
    first.card_faces.append({'noncanonical_independence_sentinel': True})
    first.colors.append('noncanonical_independence_sentinel')
    first.counters['noncanonical_independence_sentinel'] = 1
    assert second.card_faces == [] and second.counters == {}
    assert 'noncanonical_independence_sentinel' not in second.colors
    assert raw_card('Lithoform Engine') == raw_before
