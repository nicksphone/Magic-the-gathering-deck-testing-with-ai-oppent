"""Two canonical paid families; strict current-source/controller rules assertions."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

import pytest

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.oracle_effects import inspect_target_hints
from tests import test_soulscar_preflight_rules_audit as base
from tests import test_soulscar_affected_order_goldens as prior
from tests.test_linked_damage_targets import raw_card
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.test_batch_graveyard_publication_audit import assert_private


RAW = Path(__file__).resolve().parents[2] / 'source-controller-audit/raw'
for line in (RAW / 'SHA256SUMS').read_text().splitlines():
    digest, filename = line.split()
    assert hashlib.sha256((RAW / Path(filename).name).read_bytes()).hexdigest() == digest
ROWS = {row['name']: row for row in
        (json.loads(path.read_text()) for path in RAW.glob('*.json'))}


def record(label, state, **extra):
    directory = os.environ.get('MTG_SOURCE_CONTROLLER_EVIDENCE')
    if directory:
        with (Path(directory) / 'boundaries.jsonl').open('a') as stream:
            stream.write(json.dumps({'label': label, 'snapshot': prior.snapshot(state),
                                     **extra}, sort_keys=True) + '\n')


def send(state, actor, action):
    result = prior.act(state, actor, action)
    directory = os.environ.get('MTG_SOURCE_CONTROLLER_EVIDENCE')
    if directory:
        with (Path(directory) / 'actions.jsonl').open('a') as stream:
            stream.write(json.dumps({'actor': actor, 'action': action,
                'pending': result.pending_replacement_choice,
                'stack': [asdict(item) for item in result.stack]}, sort_keys=True) + '\n')
    return result


def add(state, name, actor, zone=Zone.BATTLEFIELD):
    card = raw_card(state, ROWS[name], actor, zone)
    if zone == Zone.BATTLEFIELD:
        # Declared ready retained-board setup, not a freshly cast sick creature.
        card.summoning_sick = False
        assign_static_order_on_battlefield_entry(state, card.id)
    return card.id


def priority(state, actor):
    if state.priority_player != actor:
        state = send(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == actor
    return state


def cast(state, name, actor, targets):
    state = priority(state, actor)
    cid = add(state, name, actor, Zone.HAND)
    pool = deepcopy(state.players[actor].mana_pool)
    state = send(state, actor, {'type': 'cast_spell', 'card_id': cid,
                              'cost_choice': {'id': 'base'}, 'targets': targets})
    assert state.cards[cid].zone == Zone.STACK
    assert state.players[actor].mana_pool != pool
    frame = next(asdict(item) for item in state.stack if item.source_card_id == cid)
    return state, cid, frame


def resolve_announced(state, frame):
    # Actual prowess triggers above a spell must resolve, never be popped by the fixture.
    for _ in range(8):
        if not any(item.id == frame['id'] for item in state.stack):
            return state
        assert not state.pending_replacement_choice and not state.pending_mechanic_choice
        state = passes(state)
    raise AssertionError('Eight real priority cycles did not resolve the announced frame')


def setup(seat, shield=True, mage=True):
    state = base.position(seat)
    state.mechanic_choice_players = {1, 2}
    target = add(state, 'Torrential Gearhulk', seat)
    other = add(state, 'Torrential Gearhulk', 3-seat)
    if shield:
        probe = add(state, 'Healing Salve', seat, Zone.HAND)
        mode = next(mode for mode in inspect_target_hints(state, state.cards[probe], seat)['modes']
                    if mode.startswith('Prevent'))
        pool = deepcopy(state.players[seat].mana_pool)
        state = send(state, seat, {'type': 'cast_spell', 'card_id': probe,
                                  'targets': {'mode_text': mode, 'target_card_id': target}})
        assert state.players[seat].mana_pool != pool
        state = base.finish(state)
        assert state.cards[probe].zone == Zone.GRAVEYARD
        assert len(state.numeric_prevention_shields) == 1
    scar = add(state, 'Soul-Scar Mage', 3-seat) if mage else None
    state.replacement_choice_required = True
    state.replacement_choice_players = {seat}
    return prior.reload_exact(state), target, other, scar


def verdict(state, seat, target, scar, first, amount):
    record('before-strict-current-controller-verdict', state, seat=seat, target=target,
           expected_scar=scar, first=first, amount=amount)
    assert_private(state)
    state = prior.reload_exact(state)
    if scar is not None and state.numeric_prevention_shields:
        pending = state.pending_replacement_choice
        assert pending is not None, 'Affected player must choose current-source conversion versus shield'
        shield = 'numeric-prevention:' + state.numeric_prevention_shields[0].receipt_id
        assert pending['player_id'] == seat
        assert {row['source_id'] for row in pending['options']} == {scar, shield}
        state = prior.choose(state, seat, scar if first == 'conversion' else shield)
    assert state.cards[target].counters.get('-1/-1', 0) == (
        amount if scar is not None and first == 'conversion' else 0)
    assert state.cards[target].counters.get('__damage_marked', 0) == (
        amount if scar is None and not state.numeric_prevention_shields else 0)
    if state.numeric_prevention_shields:
        assert state.numeric_prevention_shields[0].remaining == (
            3 if first == 'conversion' and scar is not None else 3-amount)
    assert state.players[1].life == state.players[2].life == 20
    assert_private(prior.reload_exact(state))
    record('completed-strict-current-controller-verdict', state, seat=seat, target=target)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('departed', [False, True])
@pytest.mark.parametrize('first', ['conversion', 'prevention'])
def test_actual_opposing_twincast_damage_uses_copy_controller_after_original_departure(
        seat, departed, first):
    state, target, other, scar = setup(seat)
    copier = 3-seat
    state, bolt, original = cast(state, 'Lightning Bolt', seat, {'target_card_id': other})
    state, twin, frame = cast(state, 'Twincast', copier, {'target_stack_id': original['id']})
    state = resolve_announced(state, frame)
    option = 'target_card_id:' + target
    assert option in state.pending_mechanic_choice['options']
    state = send(state, copier, {'type': 'choose_mechanic', 'card_ids': [option]})
    assert state.cards[twin].zone == Zone.GRAVEYARD
    copied = asdict(state.stack[-1])
    assert copied['controller'] == copier and copied['id'] != original['id']
    assert copied['payload']['__copied_from_stack_id'] == original['id']
    if departed:
        state, counter, frame = cast(state, 'Counterspell', copier, {'target_stack_id': original['id']})
        state = resolve_announced(state, frame)
        assert state.cards[counter].zone == state.cards[bolt].zone == Zone.GRAVEYARD
    else:
        assert state.cards[bolt].zone == Zone.STACK
    assert state.stack[-1].id == copied['id']
    record('real-opposing-copy-before-resolution', state, original=original, copied=copied)
    state = passes(prior.reload_exact(state))
    verdict(state, seat, target, scar, first, 3)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('borrow_before_activation', [False, True])
@pytest.mark.parametrize('first', ['conversion', 'prevention'])
def test_actual_ray_changes_damage_permanent_controller_not_pending_ability_controller(
        seat, borrow_before_activation, first):
    state, target, _, scar = setup(seat)
    source = add(state, 'Prodigal Sorcerer', seat)
    if borrow_before_activation:
        state, ray, frame = cast(state, 'Ray of Command', 3-seat, {'target_card_id': source})
        state = resolve_announced(state, frame)
        assert state.cards[ray].zone == Zone.GRAVEYARD
    activator = 3-seat if borrow_before_activation else seat
    state = priority(state, activator)
    state = send(state, activator, {'type': 'activate_ability', 'card_id': source,
        'ability_index': 0, 'targets': {'target_card_id': target}})
    ability = asdict(state.stack[-1])
    assert state.cards[source].tapped and ability['controller'] == activator
    if not borrow_before_activation:
        state, ray, frame = cast(state, 'Ray of Command', 3-seat, {'target_card_id': source})
        state = resolve_announced(state, frame)
        assert state.cards[ray].zone == Zone.GRAVEYARD
    assert state.cards[source].owner == seat and state.cards[source].controller == 3-seat
    assert state.stack[-1].id == ability['id']
    record('actual-ray-borrowed-permanent-before-damage', state, ability=ability,
           physical_source=source, borrowed_before=borrow_before_activation)
    state = passes(prior.reload_exact(state))
    verdict(state, seat, target, scar, first, 1)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('shield', [False, True])
def test_independent_actual_paid_bolt_no_mage_damage_or_numeric_prevention(seat, shield):
    state, target, _, scar = setup(seat, shield=shield, mage=False)
    state, bolt, _ = cast(state, 'Lightning Bolt', 3-seat, {'target_card_id': target})
    state = passes(prior.reload_exact(state))
    assert state.cards[bolt].zone == Zone.GRAVEYARD
    verdict(state, seat, target, scar, 'prevention', 3)


@pytest.mark.parametrize('seat', [1, 2])
def test_former_source_controller_mage_cannot_convert_new_controllers_friendly_damage(seat):
    state, target, _, former_mage = setup(3-seat)
    source = add(state, 'Prodigal Sorcerer', seat)
    state = priority(state, seat)
    state = send(state, seat, {'type': 'activate_ability', 'card_id': source,
        'ability_index': 0, 'targets': {'target_card_id': target}})
    ability = asdict(state.stack[-1])
    state, ray, frame = cast(state, 'Ray of Command', 3-seat, {'target_card_id': source})
    state = resolve_announced(state, frame)
    assert state.cards[ray].zone == Zone.GRAVEYARD
    assert state.cards[source].controller == state.cards[target].controller == 3-seat
    assert state.cards[former_mage].controller == ability['controller'] == seat
    record('former-controller-mage-before-friendly-damage', state, ability=ability,
           physical_source=source, target=target, former_mage=former_mage)
    state = passes(prior.reload_exact(state))
    record('former-controller-mage-after-friendly-damage', state, ability=ability,
           physical_source=source, target=target)
    assert state.pending_replacement_choice is None, 'Former controller conversion is not applicable'
    verdict(state, 3-seat, target, None, 'prevention', 1)


@pytest.mark.parametrize('seat', [1, 2])
def test_opposing_copy_keep_hits_own_creature_without_soulscar_conversion(seat):
    state, _, target, scar = setup(seat, shield=False)
    state, bolt, original = cast(state, 'Lightning Bolt', seat, {'target_card_id': target})
    state, twin, frame = cast(state, 'Twincast', 3-seat, {'target_stack_id': original['id']})
    state = resolve_announced(state, frame)
    assert 'keep' in state.pending_mechanic_choice['options']
    state = send(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.cards[twin].zone == Zone.GRAVEYARD
    copied = asdict(state.stack[-1])
    state, counter, frame = cast(state, 'Counterspell', 3-seat, {'target_stack_id': original['id']})
    state = resolve_announced(state, frame)
    assert state.cards[counter].zone == state.cards[bolt].zone == Zone.GRAVEYARD
    assert state.stack[-1].id == copied['id']
    state = passes(prior.reload_exact(state))
    assert state.cards[target].controller == state.cards[scar].controller == copied['controller']
    assert state.pending_replacement_choice is None
    verdict(state, 3-seat, target, None, 'prevention', 3)
