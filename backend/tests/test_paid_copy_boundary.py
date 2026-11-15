"""Regression tests for optional referred-ability copy trigger boundaries.

Synthetic in-memory states exercise the real trigger collector and compiler.
Non-activation events return the unsupported-instruction noop; completed
activations retain their strict binding checks and produce one copy trigger.
"""
import copy
from dataclasses import asdict

import pytest

from game_state.state import CardInstance, MatchState, PlayerState, StackItem, Zone, object_incarnation
from rules_engine import events
from rules_engine.activation_copy import collect_activation_copy_triggers, compile_clause
from rules_engine.paid_triggers import compile_paid_instruction

PAID_REFERRED_COPY = 'you may pay {2}. if you do, copy that ability. you may choose new targets for the copy.'
FAMILY_ORACLE = {
    'spell_cast': 'whenever you cast a spell, ' + PAID_REFERRED_COPY,
    'spell_copy': 'whenever you copy a spell, ' + PAID_REFERRED_COPY,
    'discard': 'whenever you discard a card, ' + PAID_REFERRED_COPY,
    'cycle': 'whenever you cycle a card, ' + PAID_REFERRED_COPY,
}
GENUINE_CLAUSE = ("Whenever you activate an ability, if it isn't a mana ability, you may pay {2}. "
                  "If you do, copy that ability. You may choose new targets for the copy.")
GENUINE_INSTRUCTION = 'you may pay {2}. If you do, copy that ability. You may choose new targets for the copy.'
INVALID = 'Invalid retained completed activation'
UNBOUND = 'Activation event does not bind its completed item'
LACKS = 'Paid copy lacks its genuine activation binding'


def permanent(cid, name, seat, oracle, types=('Enchantment',), zone=Zone.BATTLEFIELD):
    return CardInstance(id=cid, name=name, owner=seat, controller=seat, zone=zone, types=list(types),
                        type_line=' '.join(types), oracle_text=oracle)


def match(*cards_):
    state = MatchState(id='paid-copy-boundary-diagnostic', players={1: PlayerState(id=1, name='Seat 1'),
                                                                    2: PlayerState(id=2, name='Seat 2')},
                       cards={card.id: card for card in cards_}, stack=[])
    for card in cards_:
        if card.zone == Zone.BATTLEFIELD:
            state.players[card.controller].battlefield.append(card.id)
    return state


def frozen(state):
    """Every MatchState field (deep-copied) except rng, whose generator state is compared separately."""
    data = {key: copy.deepcopy(value) for key, value in vars(state).items() if key != 'rng'}
    data['rng_state'] = state.rng.getstate()
    return data


def assert_only_log_appended(before, state, lines):
    after = frozen(state)
    assert after['log'] == before['log'] + lines
    assert {k: v for k, v in after.items() if k != 'log'} == {k: v for k, v in before.items() if k != 'log'}


def completed_item(seat):
    return StackItem(id='diagnostic-activation', source_card_id='activator', controller=seat,
                     label='Diagnostic activation', effect_key='diagnostic_effect',
                     payload={'__announced_stack_kind': 'activated', '__completed_nonmana_activation': True})


def genuine_state(seat):
    return match(permanent('watcher', 'Diagnostic Copy Watcher', seat, GENUINE_CLAUSE),
                 permanent('plain', 'Diagnostic Plain Permanent', seat, 'Flying'),
                 permanent('activator', 'Diagnostic Activator', seat, 'Diagnostic activated text.'),
                 permanent('opponent-watcher', 'Diagnostic Opponent Watcher', 3 - seat, GENUINE_CLAUSE))


@pytest.mark.parametrize('family,seat', [(family, seat) for family in FAMILY_ORACLE for seat in (1, 2)],
                         ids=[f'{family}-seat{seat}' for family in FAMILY_ORACLE for seat in (1, 2)])
def test_nonactivation_referred_copy_is_milestone_noop(family, seat):
    watcher = permanent('watcher', 'Diagnostic Paid Watcher', seat, FAMILY_ORACLE[family])
    if family in ('spell_cast', 'spell_copy'):
        subject = permanent('subject', 'Diagnostic Spell', seat, '', types=('Instant',), zone=Zone.STACK)
        payload = {'controller': seat, 'source_card_id': 'subject'}
    else:
        subject = permanent('subject', 'Diagnostic Card', seat, '', types=('Instant',), zone=Zone.GRAVEYARD)
        payload = {'controller': seat, 'card_id': 'subject'}
    state = match(watcher, subject)
    payload_before, before = copy.deepcopy(payload), frozen(state)
    trigger = events._trigger_from_oracle(state, 'watcher', seat, FAMILY_ORACLE[family],
                                          'Diagnostic Paid Watcher trigger', family, payload)
    assert trigger == {'source_card_id': 'watcher', 'controller': seat, 'label': 'Diagnostic Paid Watcher trigger',
                       'effect_key': 'noop', 'payload': {'__trigger_full_clause': FAMILY_ORACLE[family],
                                                         '__unsupported_trigger_instruction': PAID_REFERRED_COPY}}
    assert_only_log_appended(before, state, ['Unsupported optional trigger payment for Diagnostic Paid Watcher.'])
    assert payload == payload_before


COLLECTOR_REFUSALS = {
    'incomplete-original': (lambda seat, item: dict(controller=seat, source_stack_id=item['id'], original_item=dict(
        item, payload={**item['payload'], '__completed_nonmana_activation': False})), INVALID),
    'copied-original': (lambda seat, item: dict(controller=seat, source_stack_id=item['id'], original_item=dict(
        item, payload={**item['payload'], '__stack_copy_kind': 'copy'})), INVALID),
    'missing-original': (lambda seat, item: dict(controller=seat, source_stack_id=item['id']), INVALID),
    'wrong-stack-id': (lambda seat, item: dict(controller=seat, source_stack_id='other-activation', original_item=item), UNBOUND),
    'wrong-controller': (lambda seat, item: dict(controller=3 - seat, source_stack_id=item['id'], original_item=item), UNBOUND),
}
DIRECT_REFUSALS = {
    'wrong-stack-id': (lambda seat, item: dict(controller=seat, source_stack_id='other-activation', original_item=item), LACKS),
    'wrong-controller': (lambda seat, item: dict(controller=3 - seat, source_stack_id=item['id'], original_item=item), LACKS),
    'missing-original': (lambda seat, item: dict(controller=seat, source_stack_id=item['id']), INVALID),
}


@pytest.mark.parametrize('case,seat', [(case, seat) for case in COLLECTOR_REFUSALS for seat in (1, 2)],
                         ids=[f'{case}-seat{seat}' for case in COLLECTOR_REFUSALS for seat in (1, 2)])
def test_collector_fails_closed(case, seat):
    build, message = COLLECTOR_REFUSALS[case]
    state, payload = genuine_state(seat), build(seat, asdict(completed_item(seat)))
    payload_before, before = copy.deepcopy(payload), frozen(state)
    with pytest.raises(ValueError) as refused:
        collect_activation_copy_triggers(state, payload)
    assert type(refused.value) is ValueError and str(refused.value) == message
    assert_only_log_appended(before, state, [])
    assert payload == payload_before


@pytest.mark.parametrize('case,seat', [(case, seat) for case in DIRECT_REFUSALS for seat in (1, 2)],
                         ids=[f'{case}-seat{seat}' for case in DIRECT_REFUSALS for seat in (1, 2)])
def test_direct_referred_compile_fails_closed(case, seat):
    build, message = DIRECT_REFUSALS[case]
    state, payload = genuine_state(seat), build(seat, asdict(completed_item(seat)))
    payload_before, before = copy.deepcopy(payload), frozen(state)
    with pytest.raises(ValueError) as refused:
        compile_paid_instruction(state, state.cards['watcher'], seat, GENUINE_INSTRUCTION, payload, referred_activation=True)
    assert type(refused.value) is ValueError and str(refused.value) == message
    assert_only_log_appended(before, state, [])
    assert payload == payload_before


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_genuine_collector_yields_one_referred_copy(seat):
    state, item = genuine_state(seat), completed_item(seat)
    payload = {'controller': seat, 'source_stack_id': item.id, 'original_item': asdict(item)}
    payload_before, before = copy.deepcopy(payload), frozen(state)
    watcher = state.cards['watcher']
    assert compile_clause(GENUINE_CLAUSE) == GENUINE_INSTRUCTION
    triggers = collect_activation_copy_triggers(state, payload)
    assert triggers == [{'source_card_id': 'watcher', 'controller': seat,
                         'label': 'Diagnostic Copy Watcher activation trigger', 'effect_key': 'copy_referred_ability',
                         'payload': {'__activation_copy_original': asdict(item), '__may': True,
                                     '__optional_payment_cost': '{2}', '__optional_payment_instruction': GENUINE_INSTRUCTION,
                                     '__activation_copy_clause': GENUINE_CLAUSE,
                                     '__activation_copy_source': {'card_id': 'watcher', 'incarnation': object_incarnation(watcher),
                                                                  'zone_change_sequence': watcher.zone_change_sequence,
                                                                  'controller': seat}}}]
    assert_only_log_appended(before, state, [])
    assert payload == payload_before
