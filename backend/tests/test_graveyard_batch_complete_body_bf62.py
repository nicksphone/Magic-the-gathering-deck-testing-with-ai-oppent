"""Noncanonical protocol negatives derived from pinned, intact Vaults RAW."""
from copy import copy

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.graveyard_batch_entry import CLAUSE, KEY, compile_instruction
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.graveyard_batch_native_support_bf62 import locate, position, raw_card


RAW = raw_card('Open the Vaults')['oracle_text']
REMINDER = '(Auras with nothing to enchant remain in graveyards.)'
BARE = RAW.removesuffix(' ' + REMINDER)
# These are adversarial protocol strings, not claims about any printed card.
BAD = {
    'raw-plus-executable-parenthesis': RAW + ' (then draw a card)',
    'raw-plus-adjacent-executable-parenthesis': RAW + '(then draw a card)',
    'bare-plus-executable-parenthesis': BARE + ' (then draw a card)',
    'embedded-executable-parenthesis': RAW.replace('graveyards', 'graveyards(then draw a card)'),
    'embedded-conditional-parenthesis': RAW.replace('cards from', 'cards(if you control a Plains) from'),
    'unknown-inside-known-reminder': RAW.replace(REMINDER, '(Auras with nothing to enchant remain in graveyards. Then draw a card.)'),
    'conditional-suffix': BARE + ' If you control a Plains, draw a card.',
    'executable-suffix': RAW + ' Then draw a card.',
}


@pytest.mark.parametrize('text', [RAW, BARE], ids=['intact-full-RAW', 'bare-complete-instruction-protocol'])
def test_complete_instruction_and_actual_supported_reminder_retain_full_clause(text):
    assert compile_instruction(text) == (KEY, {CLAUSE: text})


@pytest.mark.parametrize('name', BAD)
def test_unknown_executable_body_never_admits_a_partial_batch(name):
    try:
        result = compile_instruction(BAD[name])
    except ActionRejected:
        return
    assert result is None


@pytest.mark.parametrize('name', BAD)
def test_actual_inference_cannot_fall_through_to_partial_reward(name):
    state = position(('Open the Vaults',))
    protocol = copy(state.cards[locate(state, 'Open the Vaults')])
    protocol.oracle_text = BAD[name]
    try:
        effect_key, _ = infer_effect_from_oracle(state, protocol, 1, report_unsupported=False)
    except ActionRejected:
        return
    assert effect_key == 'noop'


@pytest.mark.parametrize('value', [None, {}, [], 1, True])
def test_non_string_protocol_input_is_not_admitted(value):
    assert compile_instruction(value) is None
