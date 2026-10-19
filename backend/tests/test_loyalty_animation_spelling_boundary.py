"""Declared full-body grammar specimens; no canonical Oracle row is rewritten."""
from copy import copy, deepcopy
import json

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body, compile_instruction
from rules_engine.continuous import effective_keywords, effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from rules_engine.loyalty_instructions import compile_extended
from rules_engine.oracle_effects import infer_effect_from_oracle
from tests.test_builtin_metadata_refresh import repo
from tests.test_copy_nissa_paid_contract import PaidEpisode
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import snap


SPELLINGS = [
    pytest.param('0/0', False, id='native-literal'),
    pytest.param('0/0', True, id='native-uppercase-animation'),
    pytest.param('00/0', False, id='leading-power-zero'),
    pytest.param('0/00', False, id='native-leading-toughness-zero'),
    pytest.param('00/00', False, id='both-leading-zeroes'),
    pytest.param('000/000', False, id='three-zeroes'),
    pytest.param('\u0660/0', False, id='arabic-power-zero'),
    pytest.param('0/\uff10', False, id='fullwidth-toughness-zero'),
]


def specimen(stats, uppercase=False):
    instruction = ("Put three +1/+1 counters on up to one target noncreature land you control. "
                   f"Untap it. It becomes a {stats} Elemental creature with vigilance and haste "
                   "that's still a land.")
    if uppercase:
        instruction = instruction.replace('It becomes a', 'IT BECOMES A').replace(
            'Elemental', 'ELEMENTAL')
    return {'name': 'Spelling Boundary Walker', 'mana_cost': '{G}', 'colors': ['G'],
            'type_line': 'Legendary Planeswalker - Boundary', 'loyalty': '3',
            'oracle_text': '+1: ' + instruction + '\n-1: You gain 1 life.'}, instruction


def episode(seat, stats, uppercase=False):
    h = PaidEpisode(seat)
    raw, instruction = specimen(stats, uppercase)
    source = raw_card(h.state, raw, seat, Zone.HAND).id
    land = h.add('Forest', Zone.BATTLEFIELD)
    h.state.cards[land].tapped = True
    assert h.state.cards[source].oracle_text == raw['oracle_text']
    return h, raw, instruction, source, land


@pytest.mark.parametrize('stats,uppercase', SPELLINGS)
def test_native_lowering_requires_compatible_stat_spelling_not_only_numeric_zero(stats, uppercase):
    raw, instruction = specimen(stats, uppercase)
    extended = compile_extended(instruction, raw['name'])
    assert [step['effect_key'] for step in extended] == ['loyalty_counter', 'loyalty_animate']
    assert extended[0]['data']['amount'] == 3
    assert extended[1]['data']['power'] == extended[1]['data']['toughness'] == 0
    expected = ([{'effect_key': 'add_counters', 'instruction': instruction[:-1]}]
                if stats in {'0/0', '0/00'} else extended)
    assert compile_instruction(instruction, raw['name']) == expected
    body = compile_body(raw['oracle_text'], raw['name'])
    assert [ability['text'] for ability in body['abilities']] == [instruction, 'You gain 1 life.']
    assert [ability['delta'] for ability in body['abilities']] == [1, -1]
    assert body['abilities'][0]['instructions'] == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stats,uppercase', SPELLINGS)
def test_checked_paid_spelling_animation_both_seats_sql_and_child_restore(
        seat, stats, uppercase, repo, tmp_path):
    h, raw, instruction, source, land = episode(seat, stats, uppercase)
    # Observe the unchanged native parser independently of loyalty compilation.
    proxy = copy(h.state.cards[source])
    proxy.types, proxy.oracle_text, proxy.loyalty_program = [], instruction, False
    before = snap(h.state)
    native = infer_effect_from_oracle(h.state, proxy, seat, {'target_card_id': land},
                                      report_unsupported=False)
    assert snap(h.state) == before
    counter_payload = (native[1] if native[0] == 'add_counters'
                       else native[1]['effects'][0]['payload'])
    assert counter_payload['animate_land'] is (stats in {'0/0', '0/00'})
    h.paid(source, {'G': 1})
    h.restore_owned(repo, tmp_path, 'paid-boundary-cast')
    h.until(lambda: not h.state.stack)
    assert h.state.cards[source].zone == Zone.BATTLEFIELD
    assert h.state.cards[source].loyalty == 3
    assert h.state.cards[land].tapped and not h.state.cards[land].counters
    h.act(seat, {'type': 'activate_loyalty', 'card_id': source, 'ability_index': 0,
                 'targets': {'target_card_id': land}})
    assert h.state.cards[source].loyalty == 4
    frame = deepcopy(h.state.stack[-1])
    assert frame.payload['__announced_targets'] == {'target_card_id': land}
    assert frame.payload['__announced_target_references']['version'] == 1
    assert h.state.cards[land].tapped and not h.state.cards[land].counters
    h.restore_owned(repo, tmp_path, 'paid-boundary-activation')
    h.until(lambda: not h.state.stack)
    h.restore_owned(repo, tmp_path, 'resolved-boundary-animation')
    (tmp_path / 'episode.json').write_text(json.dumps({
        'declared_print': raw, 'seat': seat, 'native_projection': native,
        'extended_program': compile_extended(instruction, raw['name']),
        'compiled_program': compile_instruction(instruction, raw['name']),
        'activation_frame': vars(frame), 'actions': h.trace, 'after': snap(h.state),
    }, default=str))
    target = h.state.cards[land]
    assert target.zone == Zone.BATTLEFIELD
    assert target.counters['+1/+1'] == 3
    assert {'Land', 'Creature', 'Elemental'}.issubset(target.types)
    assert effective_power(h.state, land) == effective_toughness(h.state, land) == 3
    assert {'vigilance', 'haste'}.issubset(effective_keywords(h.state, land))
    assert not target.tapped
    assert h.state.cards[source].oracle_text == raw['oracle_text']
    assert h.state.cards[source].loyalty == 4
    assert not any(h.state.players[seat].mana_pool.values())
    if stats in {'0/0', '0/00'}:
        assert frame.effect_key == 'add_counters'
        assert frame.payload['animate_land'] and frame.payload['animate_untap']
    else:
        assert frame.effect_key == 'effect_sequence'
        assert [step['effect_key'] for step in frame.payload['effects']] == [
            'loyalty_counter', 'loyalty_animate']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('stats', ['0/0', '00/0'])
def test_spelling_boundary_invalid_target_keeps_announced_cost_root_pure(seat, stats):
    h, raw, _, source, land = episode(seat, stats)
    h.paid(source, {'G': 1})
    h.until(lambda: not h.state.stack)
    foreign = raw_card(h.state, {'name': 'Forest', 'type_line': 'Basic Land - Forest',
                               'oracle_text': '{T}: Add {G}.'}, 3-seat, Zone.BATTLEFIELD).id
    before = snap(h.state)
    for target in (source, foreign, 'missing-target'):
        with pytest.raises(ActionRejected):
            checked_action(h.state, RulesEngine(), seat, {
                'type': 'activate_loyalty', 'card_id': source, 'ability_index': 0,
                'targets': {'target_card_id': target}})
        assert snap(h.state) == before
    assert h.state.cards[source].oracle_text == raw['oracle_text']
    assert h.state.cards[source].loyalty == 3
    assert h.state.cards[land].tapped and not h.state.cards[land].counters


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suffix', [' Unknown instruction.', ' and draw a card.',
                                  ' (Unknown instruction.)'])
def test_extended_spelling_unknown_suffix_rejects_whole_body_before_payment(seat, suffix):
    h, raw, instruction, source, _ = episode(seat, '00/0')
    rejected = instruction + suffix
    body = '+1: ' + rejected + '\n-1: You gain 1 life.'
    h.state.cards[source].oracle_text = body
    h.state.players[seat].mana_pool = {'G': 1}
    before = snap(h.state)
    assert compile_instruction(rejected, raw['name']) is None
    assert compile_body(body, raw['name']) is None
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(h.state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source})
    assert snap(h.state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_all_uppercase_keyword_body_stays_unadmitted_before_payment(seat):
    h, raw, instruction, source, _ = episode(seat, '0/0')
    rejected = instruction.upper()
    body = '+1: ' + rejected + '\n-1: You gain 1 life.'
    h.state.cards[source].oracle_text = body
    h.state.players[seat].mana_pool = {'G': 1}
    before = snap(h.state)
    assert compile_extended(rejected, raw['name']) is None
    assert compile_body(body, raw['name']) is None
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(h.state, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source})
    assert snap(h.state) == before
