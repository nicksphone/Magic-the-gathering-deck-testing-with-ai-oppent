"""Closed producer accounting and actual paid synthetic grammar witnesses."""
from copy import deepcopy
from types import SimpleNamespace
import hashlib
import json

import pytest
import test_paid_context_goldens as c
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.closed_loyalty import compile_body
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.oracle_effects import extract_loyalty_abilities

facts = c.facts
TAILS = ['\nThen perform an unspecified operation.', ' Then perform an unspecified operation.',
         ' (Then perform an unspecified operation.)',
         '\nWhenever an unspecified event occurs, perform an unspecified operation.',
         '\nAs long as an unspecified condition holds, perform an unspecified operation.']


@pytest.fixture(autouse=True)
def clear_synthetic_action_transcript():
    c.ACTIONS.clear()


def synthetic_receipt(request, state, raw, **observed):
    path = c.OUT / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')
    path.write_text(json.dumps({'node': request.node.nodeid, 'synthetic_declaration': raw,
        'not_canonical_card_certificate': True, 'observed': observed,
        'snapshot': c.snapshot(state), 'checked_action_transcript': c.ACTIONS}, indent=2) + '\n')


@pytest.mark.parametrize('name', ['The Wandering Emperor', 'Renamed Closed Walker'])
def test_canonical_complete_body_compilation(facts, name):
    raw = facts['The Wandering Emperor']
    text = raw['oracle_text'].replace(raw['name'], name)
    compiled = compile_body(text, name)
    assert compiled is not None and len(compiled['abilities']) == 3
    assert len(compiled['companions']) == 2
    assert [len(a['instructions']) for a in compiled['abilities']] == [2, 1, 2]
    assert [a['text'] for a in extract_loyalty_abilities(SimpleNamespace(oracle_text=text, name=name))] \
        == [a['text'] for a in compiled['abilities']]
    assert 'unsupported complete loyalty body' not in known_unsupported_mechanics(text, card_name=name)


@pytest.mark.parametrize('cost', ['+7', '-4', '0', '-X', '+X'])
@pytest.mark.parametrize('body', ['Draw three cards.', 'You gain 5 life.',
    'Target player loses 4 life.', 'Put two +1/+1 counters on target creature. It gains flying until end of turn.',
    'Create three 3/4 blue Bird creature tokens with flying.',
    'Exile target creature. You gain 7 life.'])
def test_generic_costs_and_complete_lines_are_not_effect_tuple_recipes(cost, body):
    compiled = compile_body(f'{cost}: {body}', 'Any Walker')
    assert compiled is not None and len(compiled['abilities']) == 1
    assert compiled['abilities'][0]['text'] == body


@pytest.mark.parametrize('tail', TAILS)
@pytest.mark.parametrize('name', ['The Wandering Emperor', 'Renamed Closed Walker'])
def test_unknown_raw_body_no_projection_or_coverage_waiver(facts, name, tail):
    text = facts['The Wandering Emperor']['oracle_text'].replace('The Wandering Emperor', name) + tail
    assert compile_body(text, name) is None
    assert extract_loyalty_abilities(SimpleNamespace(oracle_text=text, name=name)) == []
    assert 'unsupported complete loyalty body' in known_unsupported_mechanics(text, card_name=name)


@pytest.mark.parametrize('body', ['+1: Draw a card. It gains flying until end of turn.',
    '+1: Put a +1/+1 counter on target creature. Target creature gains flying until end of turn.',
    '+1: Draw a card. Then perform an unspecified operation.',
    '+1: Draw a card. (Unknown reminder.)', '+1: Draw a card without paying costs.',
    '+1: It gains first strike until end of turn.', '+1: Deal X damage to any target.',
    '+1: Target player loses 2 life. It gains first strike until end of turn.',
    '+1: Create a 2/2 white Soldier creature token with unknown keyword.',
    '+1: Draw a card.\nUnknown line.', 'Flash\n+1: Unknown operation.'])
def test_unaccounted_operands_and_sentences_reject_all(body):
    assert compile_body(body, 'Any Walker') is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ability', [0, 1, 2])
def test_actual_paid_generic_closed_effects(facts, seat, ability, request):
    derived = deepcopy(facts)
    name = 'Declared Closed Walker'
    raw = deepcopy(facts['The Wandering Emperor'])
    raw.update(name=name, loyalty='7', oracle_text=
        '+4: Draw three cards.\n-3: Target player loses 4 life.\n'
        '-2: Create three 3/4 blue Bird creature tokens with flying.')
    derived[name] = raw
    state = c.g.position(facts, seat)
    source = c.g.add(state, derived, name, seat, Zone.HAND)
    state, frame = c.paid(state, seat, source, {'C': 2, 'W': 2})
    state = c.advance(state, lambda s: all(i.id != frame for i in s.stack))
    state = c.priority(c.cold(state), seat)
    assert state.cards[source].loyalty == 7
    hand_before = len(state.players[seat].hand)
    board_before = set(state.players[seat].battlefield)
    action = {'type': 'activate_loyalty', 'card_id': source, 'ability_index': ability,
              'targets': {'target_player': 3-seat} if ability == 1 else {}}
    state = c.act(state, seat, action)
    assert state.cards[source].loyalty == [11, 4, 5][ability]
    state = c.advance(c.cold(state), lambda s: not s.stack)
    if ability == 0:
        assert len(state.players[seat].hand) == hand_before + 3
    elif ability == 1:
        assert state.players[3-seat].life == 16
    else:
        tokens = [state.cards[cid] for cid in set(state.players[seat].battlefield) - board_before]
        assert len(tokens) == 3
        assert all(t.power == 3 and t.toughness == 4 and t.colors == ['U']
                   and c.has_keyword(state, t.id, 'flying') for t in tokens)
    synthetic_receipt(request, c.cold(state), raw, ability=ability)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('tail', TAILS)
def test_malformed_cast_and_legacy_battlefield_loyalty_are_atomic(facts, seat, tail, request):
    derived = deepcopy(facts)
    derived['The Wandering Emperor']['oracle_text'] += tail
    state = c.g.position(facts, seat)
    state.active_player = 3-seat
    state.step = Step.END_STEP
    source = c.g.add(state, derived, 'The Wandering Emperor', seat, Zone.HAND)
    state = c.priority(state, seat)
    state.players[seat].mana_pool = {'C': 2, 'W': 2}
    cast = {'type': 'cast_spell', 'card_id': source,
            'cost_choice': {'id': 'base'}, 'targets': {}}
    before_cast = c.snapshot(state)
    with pytest.raises(ActionRejected, match='unsupported complete loyalty body'):
        checked_action(state, c.RULES, seat, cast)
    assert c.snapshot(state) == before_cast
    with pytest.raises(ActionRejected, match='unsupported complete loyalty body'):
        c.RULES.take_action(state, seat, cast, reject_invalid=True)
    assert c.snapshot(state) == before_cast

    # Pay and resolve the complete canonical card, never an unsupported body.
    state.cards[source].oracle_text = facts['The Wandering Emperor']['oracle_text']
    state = c.act(state, seat, cast)
    item = next(i for i in state.stack if i.source_card_id == source)
    assert item.payload['mana_spent'] == 4 and sum(state.players[seat].mana_pool.values()) == 0
    assert state.cards[source].zone == Zone.STACK
    frame = item.id
    state = c.advance(state, lambda s: all(i.id != frame for i in s.stack))
    # Explicit legacy-state defense probe, not an in-game text-changing effect.
    state.cards[source].oracle_text = derived['The Wandering Emperor']['oracle_text']
    state = c.priority(c.cold(state), seat)
    assert not any(m['type'] == 'activate_loyalty' for m in c.offers(state, seat))
    before = c.snapshot(state)
    action = {'type': 'activate_loyalty', 'card_id': source, 'ability_index': 1, 'targets': {}}
    with pytest.raises(ActionRejected):
        checked_action(state, c.RULES, seat, action)
    assert c.snapshot(state) == before
    assert state.cards[source].loyalty == 3
    synthetic_receipt(request, state, derived['The Wandering Emperor'], tail=tail,
                      malformed_loyalty_rejected_atomically=True,
                      malformed_cast_rejected_before_payment=True,
                      legacy_battlefield_surface_probe=True)
