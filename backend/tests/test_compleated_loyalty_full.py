"""Full canonical intake and checked announcements, never shortened Oracle."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.closed_loyalty import compile_body
from tests.test_restricted_mana import clean
from tests.test_linked_damage_targets import raw_card
from tests.test_counter_replacements import ROWS as MODIFIERS

FIX = Path(__file__).parent / 'fixtures/compleated_loyalty_full'
RAW = json.loads((FIX / 'tamiyo.raw.json').read_bytes())
SEED = json.loads((Path(__file__).parents[1] / 'card_data/builtin_oracle_seed.json').read_bytes())['cards']
for name, path in [('Ornithopter', 'attached_characteristics/ornithopter.json'),
                   ('Ponder', 'library_reorder/ponder.json'),
                   ('Divination', 'global_flash_timing_audit/divination.json')]:
    SEED[name] = json.loads((FIX.parent / path).read_bytes())


def act(state, seat, action):
    before = serialize_match_snapshot(state)
    result = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    return deserialize_match_snapshot(serialize_match_snapshot(result))


def settle(state):
    for _ in range(32):
        if not state.stack:
            return state
        assert not state.pending_mechanic_choice and not state.pending_replacement_choice
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Unresolved canonical stack')


def next_main(state, seat):
    from game_state.state import Step
    turn = state.turn
    for _ in range(160):
        if state.turn > turn and state.active_player == seat and state.step == Step.PRECOMBAT_MAIN and not state.stack:
            return state
        if state.step == Step.UNTAP and not state.stack:
            assert RulesEngine().advance_no_priority_step(state)
        else:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Public turn advancement exceeded bound')


def reject(state, seat, action):
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before


def cast_walker(seat, branch='G', *, doubling=False):
    state = clean(seat)
    if doubling:
        raw_card(state, MODIFIERS['Doubling Season'], seat, Zone.BATTLEFIELD)
    card = raw_card(state, RAW, seat, Zone.HAND)
    pool = {'C': 2, 'G': 1, 'U': 1}
    if branch != 'P':
        pool[branch] += 1
    state.players[seat].mana_pool = pool
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
        'cost_choice': {'id': 'base'}, 'hybrid_choices': [branch]})
    assert state.cards[card.id].zone == Zone.STACK
    assert state.stack[-1].payload['__phyrexian_life_symbols'] == (1 if branch == 'P' else 0)
    assert not any(state.players[seat].mana_pool.values())
    assert state.players[seat].life == (18 if branch == 'P' else 20)
    return settle(state), card.id


def activate(state, seat, cid, index, targets=None):
    return act(state, seat, {'type': 'activate_loyalty', 'card_id': cid,
        'ability_index': index, 'targets': targets or {}})


def test_archived_primary_intake_matches_existing_full_fixture():
    assert hashlib.sha256((FIX / 'tamiyo.raw.json').read_bytes()).hexdigest() == 'dcbfd8d6648620cf3a466af951b7db1aee9b40f9fa0956edc9c0aba1a2dbea55'
    old = next(row for row in json.loads((FIX.parent / 'compleated_entry.json').read_bytes()) if row['name'] == RAW['name'])
    for key in ('oracle_id', 'mana_cost', 'oracle_text', 'type_line', 'loyalty'):
        assert old[key] == RAW[key]
    program = compile_body(RAW['oracle_text'], RAW['name'])
    assert program is not None and len(program['abilities']) == 3


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('branch,loyalty', [('G', 5), ('U', 5), ('P', 3)])
def test_full_canonical_checked_cast_all_hybrid_branches(seat, branch, loyalty):
    state, cid = cast_walker(seat, branch)
    assert state.cards[cid].zone == Zone.BATTLEFIELD
    assert state.cards[cid].loyalty == loyalty
    assert state.cards[cid].oracle_text == RAW['oracle_text']
    assert state.spells_cast_this_turn[seat] == 1


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['short_mana', 'wrong_color', 'short_life', 'life_lock', 'bad_branch'])
def test_rejected_hybrid_payments_leave_entire_root_unmodified(seat, bad):
    state = clean(seat)
    card = raw_card(state, RAW, seat, Zone.HAND)
    branch = 'P'
    state.players[seat].mana_pool = {'C': 2, 'G': 1, 'U': 1}
    if bad == 'short_mana':
        state.players[seat].mana_pool['C'] = 1
    elif bad == 'wrong_color':
        state.players[seat].mana_pool['G'] = 0
        state.players[seat].mana_pool['R'] = 1
    elif bad == 'short_life':
        state.players[seat].life = 1
    elif bad == 'life_lock':
        raw_card(state, json.loads((FIX.parent / 'life_conversion/platinum-emperion.json').read_bytes()), seat, Zone.BATTLEFIELD)
    else:
        branch = 'R'
    reject(state, seat, {'type': 'cast_spell', 'card_id': card.id,
        'cost_choice': {'id': 'base'}, 'hybrid_choices': [branch]})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', [' Draw a card.', '\nWhenever you cast a spell, draw a card.', ' (unsupported)', '; draw a card.'])
def test_unknown_full_body_tails_reject_cast_root_pure(seat, tail):
    state = clean(seat)
    raw = {**RAW, 'oracle_text': RAW['oracle_text'] + tail}
    assert compile_body(raw['oracle_text'], raw['name']) is None
    card = raw_card(state, raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 2, 'G': 2, 'U': 1}
    reject(state, seat, {'type': 'cast_spell', 'card_id': card.id,
        'cost_choice': {'id': 'base'}, 'hybrid_choices': ['G']})


@pytest.mark.parametrize('replacement', ['{G/P}', '{G/U}', '{G}, {R}', 'three fewer', 'If mana was paid'])
def test_reminder_accounting_is_exact_not_keyword_admission(replacement):
    text = RAW['oracle_text']
    if replacement.startswith('{G/'):
        text = text.replace('{G/U/P}', replacement)
    elif replacement.startswith('{G},'):
        text = text.replace('{G}, {U}', replacement)
    elif replacement == 'three fewer':
        text = text.replace('two fewer', replacement)
    else:
        text = text.replace('If life was paid', replacement)
    assert compile_body(text, RAW['name']) is None


def test_generic_complete_families_are_not_a_card_name_allowlist():
    text = RAW['oracle_text'].replace("Tamiyo's Notebook", "Inventor's Journal")
    assert compile_body(text, 'An Unrelated Walker') is not None
    assert compile_body(text.replace('cost {2}', 'cost {3}').replace('Draw a card', 'Draw two cards'), 'Another Walker') is not None


@pytest.mark.parametrize('text', [None, '', 'Draw a card.', 'Create a Treasure token.', RAW['oracle_text']])
def test_new_hint_delegate_does_not_parse_unrelated_or_full_card_surfaces(text):
    from types import SimpleNamespace
    from rules_engine.loyalty_instructions import target_hints
    state = clean()
    card = SimpleNamespace(id='hint-boundary', name='Generic', oracle_text=text)
    before = serialize_match_snapshot(state)
    assert target_hints(state, card, 1) is None
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_permanent_spell_copy_suppresses_source_life_payment(seat):
    state = clean(seat)
    engine_raw = json.loads((FIX.parent / 'archangel_pair/lithoform-engine.json').read_bytes())
    engine = raw_card(state, engine_raw, seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 4}
    state = settle(act(state, seat, {'type': 'cast_spell', 'card_id': engine.id, 'cost_choice': {'id': 'base'}}))
    card = raw_card(state, RAW, seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 6, 'G': 1, 'U': 1}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': card.id,
        'cost_choice': {'id': 'base'}, 'hybrid_choices': ['P']})
    original = state.stack[-1].id
    assert state.stack[-1].payload['__phyrexian_life_symbols'] == 1
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
        'ability_index': 2, 'targets': {'target_stack_id': original}})
    assert state.cards[engine.id].tapped and not any(state.players[seat].mana_pool.values())
    from rules_engine.stack_engine import resolve_top_of_stack
    assert resolve_top_of_stack(state)  # Actual paid copy activation.
    assert resolve_top_of_stack(state)  # Native spell copy becomes an uncast token.
    token, = [c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD]
    assert token.oracle_text == RAW['oracle_text'] and token.loyalty == 5
    assert state.players[seat].life == 18 and state.spells_cast_this_turn[seat] == 2
    from effects.handlers import counter_spell
    counter_spell(state, 3-seat, {'target_stack_id': original})
    assert token.loyalty == 5 and state.cards[card.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['freeze', 'graveyard'])
def test_paid_loyalty_copy_can_choose_a_new_legal_target(seat, family):
    state, cid = cast_walker(seat)
    state.mechanic_choice_players = {seat}
    zone = Zone.BATTLEFIELD if family == 'freeze' else Zone.GRAVEYARD
    first = raw_card(state, SEED['Llanowar Elves'], seat, zone)
    second = raw_card(state, SEED['Llanowar Elves'], seat, zone)
    index = 0 if family == 'freeze' else 1
    targets = {'target_card_id': first.id}
    if index: targets['x_value'] = 1
    state = activate(state, seat, cid, index, targets)
    engine = raw_card(state, json.loads((FIX.parent / 'archangel_pair/lithoform-engine.json').read_bytes()), seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id, 'ability_index': 0,
        'targets': {'target_stack_id': state.stack[-1].id}})
    from rules_engine.stack_engine import resolve_top_of_stack
    assert not resolve_top_of_stack(state), 'Native copy resolution pauses for the target choice'
    assert state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] == 'copy_target'
    assert 'target_card_id:' + second.id in state.pending_mechanic_choice['options']
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['target_card_id:' + second.id]})
    state = settle(state)
    if family == 'freeze':
        assert state.cards[first.id].tapped and state.cards[second.id].tapped
    else:
        assert state.cards[first.id].zone == state.cards[second.id].zone == Zone.EXILE
        assert len([c for c in state.cards.values() if c.is_token and c.zone == Zone.BATTLEFIELD]) == 2
