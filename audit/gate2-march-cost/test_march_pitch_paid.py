"""Independent complete-printed-body payments; no admission or AI-strength claim."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

import api_contracts
import inventory as inv
import domain_paid_support as g
import training.environment as training
from ai.agent import AIAgent
from ai.information import decision_view, is_unknown
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.mana import mana_value
from rules_engine.spell_cost_clauses import spell_additional_costs
from rules_engine.targeting import stack_object_kind

MARCH = 'March of Otherworldly Light'
OUT = inv.ROOT.parent / 'evidence'
PHASE = os.environ['ADMISSION_PHASE']


@pytest.fixture(scope='module')
def facts():
    seed, selected, proof = inv.load_inputs()
    raws = {name: selected[row['scryfall_id']] for name, row in seed.items()}
    pins = {}
    for module in (api_contracts, training):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(inv.ROOT)
        pins[module.__name__] = {'path': str(path), 'sha256': inv.sha(path)}
    with (OUT / (PHASE + '-pitch-facts.json')).open('x') as stream:
        json.dump({'source': proof, 'module_pins': pins,
                   'march': raws[MARCH]}, stream, indent=2)
    return raws


def setup(facts, seat, x=4, n=2):
    state = g.position(facts, seat)
    target = g.add(state, facts, "Witch's Oven", 3-seat)
    source = g.add(state, facts, MARCH, seat, Zone.HAND)
    whites = [g.add(state, facts, name, seat, Zone.HAND) for name in
              ['Leyline Binding', 'Boros Charm', 'Intangible Virtue']]
    red = g.add(state, facts, 'Searing Blaze', seat, Zone.HAND)
    foreign = g.add(state, facts, 'Leyline Binding', 3-seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': max(0, x-2*n), 'W': 1}
    action = {'type': 'cast_spell', 'card_id': source,
              'cost_choice': {'id': 'base', 'exile_card_ids': whites[:n]},
              'targets': {'x_value': x, 'target_card_id': target}}
    return state, action, whites, red, foreign


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x,n', [(2, 0), (2, 1), (4, 1), (4, 2), (2, 3), (4, 3)])
def test_paid_selected_white_and_multicolor_white_discount(facts, seat, x, n):
    state, action, whites, red, foreign = setup(facts, seat, x, n)
    before = serialize_match_snapshot(state)
    selected = action['cost_choice']['exile_card_ids']
    action = api_contracts.CastAction.model_validate(action).model_dump(exclude_none=True)
    assert training.decode_action(training.encode_action(action)) == action
    paid = checked_action(g.restore(state), RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) == before
    source, target = action['card_id'], action['targets']['target_card_id']
    assert paid.cards[source].zone == Zone.STACK
    item = paid.stack[-1]
    assert stack_object_kind(paid, item) == 'spell' and item.controller == seat
    assert item.source_card_id == source
    assert item.payload['mana_spent'] == max(0, x-2*n)+1
    assert sum(paid.players[seat].mana_pool.values()) == 0
    assert paid.cards[source].mana_cost == '{X}{W}'
    assert mana_value(paid.cards[source].mana_cost, x_value=x) == x+1
    assert item.payload['__announced_targets'] == action['targets']
    for cid in selected:
        assert paid.cards[cid].owner == seat and paid.cards[cid].zone == Zone.EXILE
        assert cid in paid.players[seat].exile and cid not in paid.players[seat].hand
        assert cid not in paid.players[seat].graveyard
    for cid in whites[n:]+[red, foreign]:
        assert paid.cards[cid].zone == Zone.HAND
    paid = g.restore(paid)
    g.resolve(paid)
    assert paid.cards[source].zone == Zone.GRAVEYARD
    assert paid.cards[target].zone == Zone.EXILE and not paid.stack
    g.restore(paid)
    with (OUT / (PHASE + f'-pitch-paid-{seat}-{x}-{n}.json')).open('x') as stream:
        json.dump({'snapshot': serialize_match_snapshot(paid), 'paid_mana': max(0, x-2*n)+1,
                   'selected': selected, 'announced_x': x}, stream, indent=2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['checked', 'direct'])
@pytest.mark.parametrize('bad', ['null', 'bool', 'string', 'duplicate', 'foreign', 'red',
                                  'source', 'unknown', 'wrong-zone', 'missing-id',
                                  'missing-choice', 'no-white-mana', 'insufficient', 'bool-x'])
def test_bad_selections_reject_before_root_mutation(facts, seat, route, bad):
    state, action, whites, red, foreign = setup(facts, seat)
    values = {'null': None, 'bool': True, 'string': whites[0], 'duplicate': [whites[0]]*2,
              'foreign': [foreign], 'red': [red], 'source': [action['card_id']],
              'unknown': ['missing-object'], 'wrong-zone': [action['targets']['target_card_id']]}
    if bad in values:
        action['cost_choice']['exile_card_ids'] = values[bad]
    elif bad == 'missing-id':
        del action['cost_choice']['id']
    elif bad == 'missing-choice':
        del action['cost_choice']
    elif bad == 'no-white-mana':
        state.players[seat].mana_pool = {'C': 20}
    elif bad == 'insufficient':
        action['cost_choice']['exile_card_ids'] = []
    elif bad == 'bool-x':
        action['targets']['x_value'] = True
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        if route == 'checked':
            checked_action(state, RulesEngine(), seat, action)
        else:
            RulesEngine().take_action(state, seat, action, reject_invalid=True)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('value', [None, True, 'object', [False], ['x']*251])
def test_typed_rejects_shapes_before_exclude_none(facts, seat, value):
    state, action, *_ = setup(facts, seat)
    action['cost_choice']['exile_card_ids'] = value
    before = serialize_match_snapshot(state)
    with pytest.raises(ValidationError):
        api_contracts.CastAction.model_validate(action)
    with pytest.raises(ActionRejected):
        training.encode_action(action)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['checked', 'direct'])
@pytest.mark.parametrize('value', [[], None])
def test_unmatched_option_rejects_even_empty_or_null(facts, seat, route, value):
    state = g.position(facts, seat)
    source = g.add(state, facts, 'Intangible Virtue', seat, Zone.HAND)
    state.players[seat].mana_pool = {'C': 1, 'W': 1}
    action = {'type': 'cast_spell', 'card_id': source,
              'cost_choice': {'id': 'base', 'exile_card_ids': value}, 'targets': {}}
    control = checked_action(state, RulesEngine(), seat,
                             {**action, 'cost_choice': {'id': 'base'}})
    assert control.cards[source].zone == Zone.STACK
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        if route == 'checked':
            checked_action(state, RulesEngine(), seat, action)
        else:
            RulesEngine().take_action(state, seat, action, reject_invalid=True)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('selected', [False, True])
def test_public_candidates_and_readonly_materialization_preserve_selection(facts, seat, selected):
    state, action, whites, red, foreign = setup(facts, seat)
    state.players[seat].mana_pool = {'C': 4, 'W': 1}
    if not selected:
        del action['cost_choice']['exile_card_ids']
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    move = next(row for row in moves if row.get('card_id') == action['card_id'] and row['type'] == 'cast_spell')
    option = next(row for row in move['cost_options'] if row['id'] == 'base')
    assert option['hand_exile_color'] == 'W' and option['hand_exile_generic_reduction'] == 2
    assert set(option['exile_card_ids']) == set(whites)
    assert foreign not in option['exile_card_ids'] and red not in option['exile_card_ids']
    public, public_moves = decision_view(state, seat, moves)
    assert is_unknown(public.cards[foreign]) and public.cards[foreign].name == ''
    agent = AIAgent()
    proposal = {**move, **action}
    for materialize in (agent._materialize_action_without_resources, agent._materialize_action):
        result = materialize(public, deepcopy(proposal), seat)
        assert not result.get('_invalid_ai_choice')
        assert result['cost_choice'] == action['cost_choice']
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('tail', [' Unknown unsupported instruction.', '\nDraw a card.',
                                 '\nWhen this enters, draw a card.', ' (unknown suffix)'])
def test_unknown_complete_body_tail_cannot_admit_partial_cost(facts, tail):
    assert spell_additional_costs(facts[MARCH]['oracle_text'], MARCH) == [
        {'hand_exile_color': 'W', 'hand_exile_generic_reduction': 2}]
    assert spell_additional_costs(facts[MARCH]['oracle_text'] + tail, MARCH) is None
