"""Canonical paid permissions; trusted ABA probes are explicitly labeled."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, Step, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_empty_hand_attack_witness import position, ROWS
from tests.test_linked_damage_targets import raw_card


FIXTURES = Path(__file__).parent / 'fixtures'


def canonical(path, digest):
    data = (FIXTURES / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    return json.loads(data)


COPY = canonical('creature_observer_fix/lithoform-engine.json',
    '7930e96a947ed3edc2310b8e8ec20e13d2cdb9f2291ccf49b69bd243d7a4c799')
CREMATE = canonical('kozilek_trigger_audit/cremate.json',
    '1c3e8c658013778a3930a61fda2ca9a4a3d8fe4b9f547f23079f73d80e61b481')
UNSUMMON = canonical('creature_observer_audit/unsummon.json',
    '9affc85f38bc98cec2218a89bbdbbc0dee444cb3151be63ecad6ee30fd0b66de')


def ref(card):
    return [object_incarnation(card), card.zone_change_sequence]


def snap(state):
    return serialize_match_snapshot(state)


def restart(state):
    return deserialize_match_snapshot(snap(state))


def act(state, seat, action):
    return checked_action(state, RulesEngine(), seat, action)


def paid_hulk(seat, human=False, optional=False):
    state, source = position(seat, 'Torrential Gearhulk')
    # Funded retained setup, followed by checked paid cast and real ETB.
    state.step = Step.PRECOMBAT_MAIN
    state.players[seat].battlefield.remove(source)
    state.cards[source].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(source)
    card = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    if human:
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {seat}
    if optional:
        state.mechanic_choice_players = {seat}
    state.players[seat].mana_pool = {'U': 2, 'C': 4}
    state = act(state, seat, {'type': 'cast_spell', 'card_id': source})
    assert resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.players[seat].mana_pool.get('U', 0) == 0
    if human:
        state = restart(state)
        state = act(state, seat, {'type': 'choose_trigger_target',
            'stack_id': state.pending_trigger_order['current_stack_id'],
            'target_card_id': card.id})
    assert state.stack[-1].effect_key == 'cast_from_graveyard'
    assert state.stack[-1].payload['target_card_id'] == card.id
    return state, source, card.id


def optional_state(seat):
    state, source, target = paid_hulk(seat, optional=True)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'effect_cast'
    return restart(state), source, target


def trusted_aba(state, target):
    """Trusted native object transition, not a paid reentry episode."""
    from effects.registry import resolve_effect
    owner = state.cards[target].owner
    resolve_effect(state, owner, 'exile_from_graveyard', {'target_card_id': target})
    state.players[owner].exile.remove(target)
    state.cards[target].move_to_zone(Zone.GRAVEYARD)
    state.players[owner].graveyard.append(target)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('human', [False, True])
def test_authoritative_selection_capture_and_restore(seat, human):
    state, source, target = paid_hulk(seat, human)
    seal = state.stack[-1].payload['__trigger_target_reference']
    assert seal == ref(state.cards[target])
    state = restart(state)
    assert state.stack[-1].payload['__trigger_target_reference'] == seal
    assert resolve_top_of_stack(state)
    assert state.cards[target].zone == Zone.STACK
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.stack[-1].payload['__exile_instead_of_graveyard'] is True


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['aba', 'missing', 'null', 'empty', 'bool', 'string',
    'extra', 'tuple', 'choice-false', 'choice-null', 'clause-null', 'event-null',
    'only-choice', 'only-clause', 'only-event', 'only-bad-seal'])
def test_real_optional_permission_faults_decline_only_and_pure_rejection(seat, fault, monkeypatch):
    state, _, target = optional_state(seat)
    payload = state.pending_mechanic_choice['effect_payload']
    if fault == 'aba':
        trusted_aba(state, target)
        state = restart(state)
    elif fault == 'missing': payload.pop('__trigger_target_reference', None)
    elif fault == 'null': payload['__trigger_target_reference'] = None
    elif fault == 'empty': payload['__trigger_target_reference'] = []
    elif fault == 'bool': payload['__trigger_target_reference'] = [False, False]
    elif fault == 'string': payload['__trigger_target_reference'] = '0:1'
    elif fault == 'extra': payload['__trigger_target_reference'] = ref(state.cards[target]) + [0]
    elif fault == 'tuple': payload['__trigger_target_reference'] = tuple(ref(state.cards[target]))
    elif fault == 'choice-false': payload['__trigger_target_choice'] = False
    elif fault == 'choice-null': payload['__trigger_target_choice'] = None
    elif fault == 'clause-null': payload['__trigger_target_clause'] = None
    elif fault == 'event-null': payload['__trigger_event'] = None
    else:
        for key in ('__trigger_target_choice', '__trigger_target_clause', '__trigger_event', '__trigger_target_reference'):
            payload.pop(key, None)
        key = {'only-choice': '__trigger_target_choice', 'only-clause': '__trigger_target_clause',
            'only-event': '__trigger_event', 'only-bad-seal': '__trigger_target_reference'}[fault]
        payload[key] = True if fault == 'only-choice' else None
    before = snap(state)
    from rules_engine.effect_casts import cast_moves, admit_cast, finish_cast_choice
    assert [m['type'] for m in cast_moves(state, seat)] == ['choose_mechanic']
    assert snap(state) == before
    action = {'type': 'cast_spell', 'card_id': target, 'from_graveyard': True,
        'targets': {'target_player': 3-seat}}
    def forbidden(*args, **kwargs):
        pytest.fail('Stale permission reached planning/payment helper')
    import ai.pending_effects
    monkeypatch.setattr(ai.pending_effects, 'planning_copy', forbidden)
    with pytest.raises(ActionRejected):
        admit_cast(state, seat, action, state.pending_mechanic_choice['effect_payload'])
    assert snap(state) == before
    with pytest.raises(ActionRejected):
        finish_cast_choice(state, seat, action)
    assert snap(state) == before
    with pytest.raises(ActionRejected):
        act(state, seat, action)
    assert snap(state) == before
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
    assert not state.pending_mechanic_choice and not state.stack
    assert state.cards[target].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('response', ['Cremate', 'Unsummon'])
def test_actual_paid_departure_response_source_independence(seat, response):
    state, source, target = paid_hulk(seat)
    opponent = 3-seat
    raw = CREMATE if response == 'Cremate' else UNSUMMON
    spell = raw_card(state, raw, opponent, Zone.HAND)
    state.players[opponent].mana_pool = {'B': 1} if response == 'Cremate' else {'U': 1}
    # Actual priority transfer; no direct fabricated response event.
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    assert state.priority_player == opponent
    before_hand = len(state.players[opponent].hand)
    state = act(state, opponent, {'type': 'cast_spell', 'card_id': spell.id,
        'targets': {'target_card_id': target if response == 'Cremate' else source}})
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[spell.id].zone == Zone.GRAVEYARD
    assert sum(state.players[opponent].mana_pool.values()) == 0
    if response == 'Cremate':
        assert state.cards[target].zone == Zone.EXILE
        assert len(state.players[opponent].hand) == before_hand
    else:
        assert state.cards[source].zone == Zone.HAND
    state = restart(state)
    assert resolve_top_of_stack(state)
    if response == 'Cremate':
        assert not state.stack
    else:
        assert state.cards[target].zone == Zone.STACK
        assert state.stack[-1].payload['__exile_instead_of_graveyard'] is True


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('choice', ['keep', 'new'])
@pytest.mark.parametrize('depart', [False, True])
def test_actual_paid_ability_copy_keep_or_retarget_reference(seat, choice, depart):
    state, _, first = paid_hulk(seat)
    second = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    # Distinguish two real graveyard incarnations; never guess an identity number.
    trusted_aba(state, second.id)
    engine = raw_card(state, COPY, seat, Zone.BATTLEFIELD)
    original = state.stack[-1]
    old_seal = deepcopy(original.payload.get('__trigger_target_reference'))
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
        'ability_index': 0, 'targets': {'target_stack_id': original.id}})
    assert state.cards[engine.id].tapped
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    copy_id = state.pending_mechanic_choice['stack_id']
    state = restart(state)
    chosen = 'keep' if choice == 'keep' else 'target_card_id:' + second.id
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, 3-seat, {'type': 'choose_mechanic', 'card_ids': [chosen]})
    assert snap(state) == before
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': [chosen]})
    copied = next(item for item in state.stack if item.id == copy_id)
    selected = first if choice == 'keep' else second.id
    assert copied.payload['target_card_id'] == selected
    assert copied.payload['__trigger_target_reference'] == ref(state.cards[selected])
    if choice == 'keep': assert copied.payload['__trigger_target_reference'] == old_seal
    else: assert copied.payload['__trigger_target_reference'] != old_seal
    if depart:
        trusted_aba(state, selected)
    state = restart(state)
    assert resolve_top_of_stack(state)
    assert state.cards[selected].zone == (Zone.GRAVEYARD if depart else Zone.STACK)
    if not depart:
        assert state.stack[-1].payload['__exile_instead_of_graveyard'] is True


@pytest.mark.parametrize('seat', [1, 2])
def test_generic_unsealed_permission_and_ai_probe_still_usable(seat):
    from ai.effect_cast_policy import usable_cast
    from effects.registry import resolve_effect
    state, _, target = paid_hulk(seat)
    # Resolve real triggered permission first; add a distinct generic permission.
    assert resolve_top_of_stack(state)
    assert resolve_top_of_stack(state)
    card = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    before = snap(state)
    assert usable_cast(state, seat, card.id) is not None
    assert snap(state) == before
    state.mechanic_choice_players = {seat}
    resolve_effect(state, seat, 'cast_from_graveyard', {'target_card_id': card.id})
    assert 'cast_spell' in [m['type'] for m in RulesEngine().legal_moves(state, seat)]
    state = act(restart(state), seat, {'type': 'cast_spell', 'card_id': card.id,
        'from_graveyard': True, 'targets': {'target_player': 3-seat}})
    assert state.cards[card.id].zone == Zone.STACK


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['departed-new', 'duplicate', 'keep-stale'])
def test_real_copy_choice_stale_or_duplicate_is_atomic_and_keep_never_reseals(seat, fault):
    state, _, first = paid_hulk(seat)
    second = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    engine = raw_card(state, COPY, seat, Zone.BATTLEFIELD)
    state.players[seat].mana_pool = {'C': 2}
    state = act(state, seat, {'type': 'activate_ability', 'card_id': engine.id,
        'ability_index': 0, 'targets': {'target_stack_id': state.stack[-1].id}})
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    copy_id = state.pending_mechanic_choice['stack_id']
    copied = next(item for item in state.stack if item.id == copy_id)
    seal = deepcopy(copied.payload['__trigger_target_reference'])
    if fault == 'keep-stale':
        trusted_aba(state, first)
        state = act(restart(state), seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
        copied = next(item for item in state.stack if item.id == copy_id)
        assert copied.payload['__trigger_target_reference'] == seal
        assert copied.payload['__trigger_target_reference'] != ref(state.cards[first])
        assert resolve_top_of_stack(state)
        assert state.cards[first].zone == Zone.GRAVEYARD
    else:
        chosen = 'target_card_id:' + second.id
        if fault == 'departed-new':
            from effects.registry import resolve_effect
            resolve_effect(state, seat, 'exile_from_graveyard', {'target_card_id': second.id})
        state = restart(state)
        before = snap(state)
        ids = [chosen, chosen] if fault == 'duplicate' else [chosen]
        with pytest.raises(ActionRejected):
            act(state, seat, {'type': 'choose_mechanic', 'card_ids': ids})
        assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('valid', [False, True])
def test_seal_only_generic_permission_is_validated_without_trigger_reclassification(seat, valid):
    from rules_engine.effect_casts import admit_cast
    from tests.test_activation_modifiers import board
    state = board(seat)
    card = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.GRAVEYARD)
    payload = {'target_card_id': card.id,
        '__trigger_target_reference': ref(card) if valid else None}
    before = snap(state)
    action = {'type': 'cast_spell', 'card_id': card.id, 'from_graveyard': True,
        'targets': {'target_player': 3-seat}}
    if valid:
        admit_cast(state, seat, action, payload)
        assert state.cards[card.id].zone == Zone.STACK
    else:
        with pytest.raises(ActionRejected):
            admit_cast(state, seat, action, payload)
        assert snap(state) == before
