"""Explicit noncanonical protocol bodies must not crash read-only consumers."""
from copy import deepcopy
from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from game_state.state import Zone
from rules_engine.ability_model import build_ability_spec, build_spell_spec
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.graveyard_batch_entry import CLAUSE, KEY, compile_instruction, resolve
from rules_engine.oracle_effects import infer_effect_from_oracle
from scripts import oracle_corpus_report as report
from tests.graveyard_batch_native_support_bf62 import cast_vaults, locate, place, position, raw_card
from tests.test_oracle_corpus_report import LocalRepository


RAW = raw_card('Open the Vaults')['oracle_text']
# Neither mutant describes a printed card or claims canonical fixture fidelity.
BAD = {
    'unknown-parenthesized-tail': RAW + ' (then draw a card)',
    'embedded-conditional': RAW.replace('cards from', 'cards(if you control a Plains) from'),
}


def observed_state(state):
    result = deepcopy(vars(state))
    result['rng'] = state.rng.getstate()
    return result


def protocol_state(text):
    state = position(('Open the Vaults',))
    cid = place(state, 'Open the Vaults', Zone.HAND)
    state.cards[cid].oracle_text = text
    state.players[1].mana_pool.update(C=4, W=2)
    return state, state.cards[cid]


@pytest.mark.parametrize('name', BAD)
@pytest.mark.parametrize('consumer', ['infer', 'ability', 'spell'])
def test_readonly_inference_and_specs_report_unsupported_without_raising(name, consumer):
    state, card = protocol_state(BAD[name])
    before = observed_state(state)
    if consumer == 'infer':
        key, payload = infer_effect_from_oracle(state, card, 1, report_unsupported=False)
    else:
        spec = (build_ability_spec if consumer == 'ability' else build_spell_spec)(
            state, card, 1, report_unsupported=False)
        key, payload = spec.effect.key, spec.effect.payload
        assert spec.used_fallback is True
        if consumer == 'spell':
            assert spec.unsupported_resolution
    assert key == 'noop'
    assert payload['__unsupported_instruction'] == BAD[name]
    assert observed_state(state) == before


@pytest.mark.parametrize('name', BAD)
def test_ordinary_hand_legal_view_remains_readonly_even_if_it_does_not_compile_effect(name):
    state, _ = protocol_state(BAD[name])
    before = observed_state(state)
    moves = RulesEngine().legal_moves(state, 1)
    assert {'type': 'pass_priority'} in moves
    assert observed_state(state) == before


@pytest.mark.parametrize('name', BAD)
def test_activated_protocol_legal_view_omits_unsupported_ability_without_crashing(name):
    state = position(('Sol Ring',))
    cid = place(state, 'Sol Ring', Zone.BATTLEFIELD)
    state.cards[cid].oracle_text = '{0}: ' + BAD[name]
    before = observed_state(state)
    moves = RulesEngine().legal_moves(state, 1)
    assert {'type': 'pass_priority'} in moves
    assert not any(move['type'] == 'activate_ability' and move['card_id'] == cid for move in moves)
    assert observed_state(state) == before


@pytest.mark.parametrize('name', BAD)
def test_actual_readonly_corpus_report_classifies_protocol_instead_of_aborting(monkeypatch, name):
    raw = deepcopy(raw_card('Open the Vaults'))
    raw['oracle_text'] = BAD[name]
    row = SimpleNamespace(name=raw['name'], scryfall_id=raw['id'], oracle_source='scryfall',
                          profiles_json=json.dumps({'card_data': raw}))
    repo = LocalRepository(knowledge={raw['name'].casefold(): row})
    monkeypatch.setattr(report, 'collect_corpus', lambda: {
        raw['name'].casefold(): {'name': raw['name'], 'copies': 2,
                               'decks': ['noncanonical protocol'], 'sources': ['protocol']}})
    monkeypatch.setattr(report, 'init_db', lambda: pytest.fail('Read-only injected corpus opened DB'))
    result = report.analyze_corpus(repo)
    assert result['corpus']['unique_cards'] == 1
    card = result['cards'][0]
    assert card['effect_key'] == 'noop' and card['status'] == 'parser_fallback'
    assert card['semantics_verified'] is False
    assert card['oracle_preview'] == ' '.join(BAD[name].split())[:240]


@pytest.mark.parametrize('name', BAD)
def test_private_compiler_and_real_frame_mutant_still_reject_before_any_commit(name):
    with pytest.raises(ActionRejected):
        compile_instruction(BAD[name])
    state = position(('Open the Vaults', 'Sol Ring'))
    place(state, 'Sol Ring', Zone.GRAVEYARD)
    state, source = cast_vaults(state, 1)
    frame = asdict(state.stack[-1])
    assert frame['effect_key'] == KEY and frame['source_card_id'] == source
    frame['payload'][CLAUSE] = BAD[name]
    payload = {CLAUSE: BAD[name], '__resolving_item': frame, '__source_card_id': source}
    before = observed_state(state)
    with pytest.raises(ActionRejected):
        resolve(state, 1, payload)
    assert observed_state(state) == before


@pytest.mark.parametrize('location', ['compiler-runtime-error', 'later-parser-action-rejected'])
def test_narrow_boundary_does_not_swallow_unrelated_original_errors(monkeypatch, location):
    from rules_engine import graveyard_batch_entry, spree
    state, card = protocol_state('Draw a card.')
    error = RuntimeError('compiler sentinel') if location == 'compiler-runtime-error' else ActionRejected('later sentinel')

    def fail(*args, **kwargs):
        raise error

    if location == 'compiler-runtime-error':
        monkeypatch.setattr(graveyard_batch_entry, 'compile_instruction', fail)
    else:
        monkeypatch.setattr(spree, 'is_spree', lambda text: True)
        monkeypatch.setattr(spree, 'compile_instruction', fail)
    with pytest.raises(type(error)) as caught:
        infer_effect_from_oracle(state, card, 1, report_unsupported=False)
    assert caught.value is error


def test_unchanged_full_raw_and_supported_aura_reminder_still_compile_natively():
    state, card = protocol_state(RAW)
    before = observed_state(state)
    spec = build_spell_spec(state, card, 1, report_unsupported=False)
    assert spec.effect.key == KEY and spec.effect.payload[CLAUSE] == RAW
    assert not spec.used_fallback and not spec.unsupported_resolution
    assert observed_state(state) == before
