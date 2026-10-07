"""Pure diagnostic previews; synthetic grammar inputs are not playable card fixtures."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from rules_engine.coverage import deck_pair_coverage, known_unsupported_mechanics, unsupported_resolution_clauses
from rules_engine import oracle_effects


FIXTURES = Path(__file__).parent / 'fixtures/soulscar_protection_boundaries'
SALVE = json.loads((FIXTURES / 'healing-salve.json').read_text())
PYRO = json.loads((FIXTURES / 'pyroclasm.json').read_text())
GAP = 'unsupported closed damage instruction'


@pytest.mark.parametrize('raw', [SALVE, PYRO])
def test_canonical_complete_body_has_no_closed_damage_gap(raw):
    before = deepcopy(raw)
    assert GAP not in known_unsupported_mechanics(raw['oracle_text'], card_name=raw['name'])
    assert raw == before


@pytest.mark.parametrize('tail', [' Draw a card.', ' unless you control an Island.', ' if you control a Forest.'])
@pytest.mark.parametrize('modal', [False, True])
def test_rejected_prevention_suffix_has_actual_compiler_diagnostic(tail, modal):
    body = SALVE['oracle_text'] if modal else oracle_effects._extract_modes(SALVE['oracle_text'])[1]
    body += tail
    previews = [{'mode_text': mode} for mode in oracle_effects._extract_modes(body)] or [{}]
    assert all('__unsupported_instruction' in oracle_effects._infer_closed_damage_instruction(
        body, SALVE['name'], preview)[1] for preview in previews)
    assert GAP in unsupported_resolution_clauses(body, card_name=SALVE['name'])


@pytest.mark.parametrize('body', [
    SALVE['oracle_text'].replace('Choose one', 'Choose two'),
    SALVE['oracle_text'] + '\n\u2022 Draw a card.',
    SALVE['oracle_text'].replace('Target player gains 3 life.', 'Target player gains X life.'),
    'Draw a card. ' + oracle_effects._extract_modes(SALVE['oracle_text'])[1],
])
def test_malformed_full_envelope_is_not_shortened_for_preview(body):
    assert GAP in unsupported_resolution_clauses(body, card_name=SALVE['name'])


def test_exact_mode_previews_use_full_original_body_without_targets(monkeypatch):
    actual = oracle_effects._infer_closed_damage_instruction
    calls = []
    def trace(body, name, selected):
        calls.append((body, name, deepcopy(selected)))
        return actual(body, name, selected)
    monkeypatch.setattr(oracle_effects, '_infer_closed_damage_instruction', trace)
    assert unsupported_resolution_clauses(SALVE['oracle_text'], card_name=SALVE['name']) == []
    assert calls == [(SALVE['oracle_text'], SALVE['name'], {'mode_text': mode})
                     for mode in oracle_effects._extract_modes(SALVE['oracle_text'])]
    assert actual(*calls[0]) is None  # Gain-life mode None is not rejection.


@pytest.mark.parametrize('reversed_faces', [False, True])
@pytest.mark.parametrize('bad_face', [None, 'Healing Salve', 'Pyroclasm'])
def test_independent_face_names_and_complete_bodies_are_preserved(reversed_faces, bad_face, monkeypatch):
    # API face-context envelope using real canonical records, not a claimed dual-face card.
    faces = [{'name': raw['name'], 'oracle_text': raw['oracle_text'] +
              (' Draw a card.' if raw['name'] == bad_face else '')} for raw in (SALVE, PYRO)]
    if reversed_faces:
        faces.reverse()
    before = deepcopy(faces)
    actual = oracle_effects._infer_closed_damage_instruction
    calls = []
    def trace(body, name, selected):
        calls.append((body, name, deepcopy(selected)))
        return actual(body, name, selected)
    monkeypatch.setattr(oracle_effects, '_infer_closed_damage_instruction', trace)
    gaps = known_unsupported_mechanics('', faces, card_name='')
    assert (GAP in gaps) == (bad_face is not None)
    assert faces == before
    for face in faces:
        assert any(body == face['oracle_text'] and name == face['name'] for body, name, _ in calls)
    assert all(not set(selected).difference({'mode_text'}) for _, _, selected in calls)


@pytest.mark.parametrize('text', ['', 'Draw a card.', 'Target player gains 3 life.',
                                  'Counter target spell.', 'Prevent all combat damage this turn.'])
def test_outside_closed_family_none_does_not_invent_diagnostic(text):
    assert oracle_effects._infer_closed_damage_instruction(text, '', {}) is None
    assert GAP not in unsupported_resolution_clauses(text)


def test_existing_gap_and_exploratory_status_retained():
    text = oracle_effects._extract_modes(SALVE['oracle_text'])[1] + ' Draw a card. End the turn.'
    gaps = unsupported_resolution_clauses(text)
    assert GAP in gaps and 'turn-ending procedure' in gaps
    response = deck_pair_coverage([{'card_name': SALVE['name'], 'oracle_text': text}], [])
    assert response['status'] == 'exploratory'
    assert GAP in response['known_unsupported_cards'][0]['mechanics']


def test_conversion_warning_uses_frozen_dependency_without_runtime_context():
    cards = json.loads((Path(__file__).parent / 'fixtures/soulscar_consumer_audit/cards.json').read_text())
    mage = next(card for card in cards if card['name'] == 'Soul-Scar Mage')
    assert 'unsupported counter replacement clause' not in known_unsupported_mechanics(mage['oracle_text'])


@pytest.mark.parametrize('tail', [' Draw a card.', ' if you control an Island.', ' unless you control a Forest.'])
def test_conversion_unknown_tails_retain_diagnostic(tail):
    cards = json.loads((Path(__file__).parent / 'fixtures/soulscar_consumer_audit/cards.json').read_text())
    mage = next(card for card in cards if card['name'] == 'Soul-Scar Mage')
    assert 'unsupported counter replacement clause' in known_unsupported_mechanics(mage['oracle_text'] + tail)


@pytest.mark.parametrize('tail', ['', ' Draw a card.', ' and each player.'])
def test_source_less_named_broadcast_has_no_fabricated_rejection(tail):
    body = PYRO['oracle_text'] + tail
    assert oracle_effects._infer_closed_damage_instruction(body, '', {}) is None
    assert GAP not in unsupported_resolution_clauses(body)


@pytest.mark.parametrize('tail', ['', ' Draw a card.', ' and each player.'])
def test_actual_broadcast_source_preserves_complete_body_contract(tail):
    result = oracle_effects._infer_closed_damage_instruction(PYRO['oracle_text'] + tail, PYRO['name'], {})
    assert result == ('damage_each_creature', {'amount': 2}) if not tail else (
        result[0] == 'noop' and '__unsupported_instruction' in result[1])


@pytest.mark.parametrize('tail', ['', ' Draw a card.', ' if you control an Island.'])
def test_source_less_prevention_keeps_existing_grammar(tail):
    body = oracle_effects._extract_modes(SALVE['oracle_text'])[1] + tail
    result = oracle_effects._infer_closed_damage_instruction(body, '', {})
    if tail:
        assert result[0] == 'noop' and result[1]['__unsupported_instruction'] == body
        assert GAP in unsupported_resolution_clauses(body)
    else:
        assert result == ('prevent_damage', {'amount': 3})
        assert GAP not in unsupported_resolution_clauses(body)
