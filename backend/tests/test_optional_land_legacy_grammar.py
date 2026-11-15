"""Byte-preserved pure neighbor functions; no mixed SQL test-module import."""
import pytest
from rules_engine import oracle_effects


@pytest.mark.parametrize('tapped', [False, True])
@pytest.mark.parametrize('draw', [None, 'a', 'two', '0', '12'])
def test_complete_optional_land_grammar_has_exact_order_and_no_inferred_choice(tapped, draw):
    body = 'You may put a land card from your hand onto the battlefield'
    body += ' tapped.' if tapped else '.'
    land = {'effect_key': 'put_land_from_hand', 'payload': {'optional': True, 'tapped': tapped}}
    if draw is None:
        expected = (land['effect_key'], land['payload'])
    else:
        body = f'Draw {draw} cards. ' + body
        amount = {'a': 1, 'two': 2, '0': 0, '12': 12}[draw]
        expected = ('effect_sequence', {'effects': [
            {'effect_key': 'draw_cards', 'payload': {'amount': amount}}, land,
        ]})
    assert oracle_effects.compile_optional_land_instruction(body) == expected


@pytest.mark.parametrize('tail', [
    ' Then draw a card.', ' If you control a creature.', ' and scry 1.',
    ' unless an opponent pays {1}.', ' until end of turn.',
    ' Then discard a card.',
])
@pytest.mark.parametrize('draw_first', [False, True])
def test_new_prefix_unknown_tail_never_compiles_partial_reward(tail, draw_first):
    body = ('Draw a card. ' if draw_first else '')
    body += 'You may put a land card from your hand onto the battlefield.' + tail
    assert oracle_effects.optional_land_instruction_candidate(body)
    assert oracle_effects.compile_optional_land_instruction(body) is None


@pytest.mark.parametrize('body', [
    'Put a land card from your hand onto the battlefield tapped.',
    'Target player draws a card.', 'You may draw a card.',
    'Search your library for a basic land card.',
    'You gain half X life and draw half X cards. Round down each time.',
])
def test_other_families_do_not_enter_optional_land_admission(body):
    assert not oracle_effects.optional_land_instruction_candidate(body)
    assert oracle_effects.compile_optional_land_instruction(body) is None
