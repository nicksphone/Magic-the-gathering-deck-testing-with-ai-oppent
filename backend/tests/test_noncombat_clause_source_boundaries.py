"""Closed parser and real paid departures; corrupted old frames remain strict RED."""
from dataclasses import FrozenInstanceError, asdict
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.engine import RulesEngine
from ai.information import decision_view, is_unknown
from game_state.observations import remembered_hand_card
from tests import test_damage_source_controller_audit as audit
from tests import test_soulscar_affected_order_goldens as prior
from tests.test_linked_damage_targets import raw_card
from tests.test_kozilek_graveyard_trigger_audit import passes


FIXTURES = Path(__file__).parent / 'fixtures'
EXTRA = {
    'Unsummon': json.loads((FIXTURES / 'targeted_search_lifecycle/unsummon.json').read_text()),
    'Cloudshift': json.loads((FIXTURES / 'temporary_control_audit/cloudshift.json').read_text()),
}
CLAUSE = audit.ROWS['Soul-Scar Mage']['oracle_text'].splitlines()[-1]


@pytest.mark.parametrize('body', [CLAUSE, CLAUSE.upper(), '  ' + CLAUSE + '  ',
                                 CLAUSE.replace(' controls, ', ' controls,\n  ')])
def test_statefree_complete_canonical_clause_and_frozen_descriptor(body):
    from rules_engine.replacement import noncombat_damage_counter_clause
    result = noncombat_damage_counter_clause(body)
    assert asdict(result) == {'noncombat': True, 'source_controller': 'you',
                             'recipient': 'opposing_creature', 'quantity': 'that_many',
                             'counter_type': '-1/-1'}
    with pytest.raises(FrozenInstanceError):
        result.quantity = 'two'


@pytest.mark.parametrize('body', [None, False, [], {}, '', 'Prowess\n' + CLAUSE,
    'If you gained life this turn, ' + CLAUSE, CLAUSE + ' Draw a card.',
    CLAUSE + '\nand draw a card.', CLAUSE + '\nIf you gained life this turn.',
    CLAUSE.replace('noncombat', 'combat'), CLAUSE.replace('that many', 'two'),
    CLAUSE.replace('-1/-1', '+1/+1'), CLAUSE.replace('an opponent', 'your opponent'),
    CLAUSE.replace('a creature an opponent', 'target creature an opponent'),
    CLAUSE.replace('a source you control', 'any source'), CLAUSE[:-1],
    'Whenever you cast a spell, ' + CLAUSE])
def test_unknown_or_conditional_clause_never_partially_converts(body):
    from rules_engine.replacement import noncombat_damage_counter_clause
    assert noncombat_damage_counter_clause(body) is None


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [CLAUSE + ' Draw a card.',
    CLAUSE.replace(' controls, ', ' controls,\n'),
    'If you gained life this turn, ' + CLAUSE])
def test_runtime_uses_closed_paragraph_authority_without_mutating_query_root(seat, bad):
    from rules_engine.replacement import replacement_options
    state, target, _, mage = audit.setup(seat, shield=False)
    source = audit.add(state, 'Prodigal Sorcerer', 3-seat)
    # Controlled parser-negative Oracle mutation, never a claimed canonical episode.
    state.cards[mage].oracle_text = bad
    before = prior.snapshot(state)
    options = replacement_options(state, 'damage_to_permanent', target_card_id=target,
                                  source_card_id=source, amount=1, combat=False)
    assert mage not in {row['source_id'] for row in options}
    assert prior.snapshot(state) == before


def extra_cast(state, name, actor, target):
    state = audit.priority(state, actor)
    cid = raw_card(state, EXTRA[name], actor, Zone.HAND).id
    pool = deepcopy(state.players[actor].mana_pool)
    state = audit.send(state, actor, {'type': 'cast_spell', 'card_id': cid,
                                    'targets': {'target_card_id': target}})
    assert state.players[actor].mana_pool != pool and state.cards[cid].zone == Zone.STACK
    frame = next(asdict(item) for item in state.stack if item.source_card_id == cid)
    return audit.resolve_announced(state, frame), cid


def departed(seat, route):
    state, target, _, mage = audit.setup(seat)
    source = audit.add(state, 'Prodigal Sorcerer', seat)
    reference = {'incarnation': object_incarnation(state.cards[source]),
                 'zone_change_sequence': state.cards[source].zone_change_sequence}
    state = audit.priority(state, seat)
    state = audit.send(state, seat, {'type': 'activate_ability', 'card_id': source,
        'ability_index': 0, 'targets': {'target_card_id': target}})
    ability = asdict(state.stack[-1])
    assert ability['controller'] == seat and state.cards[source].tapped
    state, ray, frame = audit.cast(state, 'Ray of Command', 3-seat, {'target_card_id': source})
    state = audit.resolve_announced(state, frame)
    assert state.cards[ray].zone == Zone.GRAVEYARD and state.cards[source].controller == 3-seat
    if route == 'hand':
        state, spell = extra_cast(state, 'Unsummon', seat, source)
        assert state.cards[source].zone == Zone.HAND
    elif route == 'graveyard':
        state, spell, frame = audit.cast(state, 'Lightning Bolt', seat, {'target_card_id': source})
        state = audit.resolve_announced(state, frame)
        assert state.cards[source].zone == Zone.GRAVEYARD
    else:
        state, spell = extra_cast(state, 'Cloudshift', 3-seat, source)
        assert state.cards[source].zone == Zone.BATTLEFIELD
        assert object_incarnation(state.cards[source]) != reference['incarnation']
        state, second_ray, frame = audit.cast(state, 'Ray of Command', seat,
                                             {'target_card_id': source})
        state = audit.resolve_announced(state, frame)
        assert state.cards[second_ray].zone == Zone.GRAVEYARD
        assert state.cards[source].controller == seat
    assert state.cards[spell].zone == Zone.GRAVEYARD
    for _ in range(8):
        if state.stack[-1].id == ability['id']:
            break
        # Ray's genuine control-loss trigger is a response opportunity, not fixture debris.
        assert state.stack[-1].effect_key == 'control_loss_tap'
        state = passes(state)
    assert state.stack[-1].id == ability['id']
    item = next(item for item in state.stack if item.id == ability['id'])
    assert item.controller == seat and item.payload['__activation_source_reference'] == reference
    receipt = deepcopy(item.payload['__source_lki'])
    assert receipt['controller'] == 3-seat
    assert receipt['battlefield_incarnation'] == reference['incarnation']
    assert state.cards[source].zone_change_sequence > reference['zone_change_sequence']
    audit.record('paid-native-departure-old-source', state, route=route, source=source,
                 ability=ability, retained_lki=receipt)
    state = prior.reload_exact(state)
    assert next(item for item in state.stack if item.id == ability['id']).payload['__source_lki'] == receipt
    return state, target, mage, source, ability['id'], receipt


def private_with_known_return(state, source):
    for viewer in (1, 2):
        view, _ = decision_view(state, viewer, RulesEngine().legal_moves(state, viewer))
        for cid in state.players[3-viewer].hand + state.players[3-viewer].library:
            if cid == source and state.cards[cid].zone == Zone.HAND:
                remembered = remembered_hand_card(state, viewer, state.cards[cid])
                assert remembered is not None and remembered.name == 'Prodigal Sorcerer'
                assert view.cards[cid].__dict__ == remembered.__dict__
            else:
                assert is_unknown(view.cards[cid])


def old_source_verdict(state, seat, target, mage, source, first):
    private_with_known_return(state, source)
    pending = state.pending_replacement_choice
    assert pending is not None, 'True departed LKI must preserve both affected-player options'
    shield = 'numeric-prevention:' + state.numeric_prevention_shields[0].receipt_id
    assert pending['player_id'] == seat
    assert {row['source_id'] for row in pending['options']} == {mage, shield}
    state = prior.choose(prior.reload_exact(state), seat, mage if first == 'conversion' else shield)
    assert state.cards[target].counters.get('-1/-1', 0) == (1 if first == 'conversion' else 0)
    assert state.numeric_prevention_shields[0].remaining == (3 if first == 'conversion' else 2)
    assert not state.cards[target].counters.get('__damage_marked', 0)
    assert state.players[1].life == state.players[2].life == 20
    private_with_known_return(prior.reload_exact(state), source)
    audit.record('paid-old-source-exact-outcome', state, first=first, target=target, source=source)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('route', ['hand', 'graveyard', 'new-battlefield-object'])
@pytest.mark.parametrize('first', ['conversion', 'prevention'])
def test_actual_paid_departure_or_reentry_uses_true_old_lki_not_current_card(seat, route, first):
    state, target, mage, source, _, _ = departed(seat, route)
    state = passes(state)
    old_source_verdict(state, seat, target, mage, source, first)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', ['missing-lki', 'invalid-controller', 'wrong-old-incarnation',
                                'new-object-receipt'])
def test_corrupt_actual_departed_frame_rejects_before_pop_or_root_mutation(seat, bad):
    route = 'new-battlefield-object' if bad == 'new-object-receipt' else 'graveyard'
    state, _, _, source, item_id, _ = departed(seat, route)
    item = next(item for item in state.stack if item.id == item_id)
    assert state.stack[-1].id == item_id
    # Corrupt a genuinely paid native old frame, not a fabricated valid StackItem.
    if bad == 'missing-lki':
        item.payload.pop('__source_lki')
    elif bad == 'invalid-controller':
        item.payload['__source_lki']['controller'] = None
    elif bad == 'wrong-old-incarnation':
        item.payload['__source_lki']['battlefield_incarnation'] += 1000
    else:
        item.payload['__source_lki']['battlefield_incarnation'] = object_incarnation(state.cards[source])
        item.payload['__source_lki']['controller'] = state.cards[source].controller
    before = prior.snapshot(state)
    audit.record('controlled-corruption-of-paid-old-frame', state, bad=bad, source=source)
    try:
        with pytest.raises(ActionRejected):
            resolve_top_of_stack(state)
    finally:
        assert prior.snapshot(state) == before, 'Corrupt persisted frame mutated before rejection'
