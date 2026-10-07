"""Genuine canonical temporary-control episodes; no injected effects/timeline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view
from game_state.state import Step, Zone
from rules_engine.ability_model import build_ability_spec
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import has_keyword
from rules_engine.engine import RulesEngine
from tests.test_targeted_library_search_compiler import setup, act, snap
from tests.test_paid_counter_family_audit import raw_card, passes, restart
from tests.test_batch_graveyard_publication_audit import assert_private

FIXTURE = Path(__file__).parent / 'fixtures/temporary_control_audit'
for line in (FIXTURE / 'SHA256SUMS').read_text().splitlines():
    digest, filename = line.split()
    assert hashlib.sha256((FIXTURE / Path(filename).name).read_bytes()).hexdigest() == digest
ROWS = {name: json.loads((FIXTURE / (name + '.json')).read_text())
        for name in ('ray-of-command', 'act-of-treason', 'cloudshift')}
FAMILIES = ['ray-of-command', 'act-of-treason']


def position(seat, family, foreign=False):
    state, _, target, _ = setup('Fertilid', seat)
    # Controlled canonical starting hand/board, not natural pregame qualification.
    for player in state.players.values():
        for cid in list(player.hand):
            player.hand.remove(cid)
            state.cards[cid].move_to_zone(Zone.LIBRARY)
            player.library.append(cid)
    card = state.cards[target]
    card.owner = seat if foreign else 3-seat  # Lawful stolen starting-board variant.
    card.tapped = True
    card.summoning_sick = False
    spell = raw_card(state, ROWS[family], seat, Zone.HAND).id
    state.players[seat].mana_pool = {'C': 3, 'U': 1, 'R': 1, 'W': 1}
    state.players[3-seat].mana_pool = {'W': 1}
    return state, spell, target


def cast(state, seat, spell, target):
    return act(state, seat, {'type': 'cast_spell', 'card_id': spell,
                            'targets': {'target_card_id': target}, 'cost_choice': {'id': 'base'}})


def advance(state, *, attack_step=False, send=act):
    turn = state.turn
    for _ in range(100):
        if attack_step and state.step == Step.DECLARE_ATTACKERS and not state.attackers_declared:
            return state
        if not attack_step and (state.step == Step.CLEANUP or state.turn != turn):
            return state
        if state.step == Step.DECLARE_ATTACKERS and not state.attackers_declared:
            state = send(state, state.active_player, {'type': 'attack', 'attackers': []})
        elif state.step == Step.DECLARE_BLOCKERS and state.attackers and not state.blockers_declared:
            state = send(state, 3-state.active_player, {'type': 'block', 'blocks': {}})
        else:
            state = send(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('100 genuine public actions did not reach the declared turn boundary')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_full_canonical_control_instruction_is_admitted_without_noop(family, seat):
    state, spell, target = position(seat, family)
    before = snap(state)
    spec = build_ability_spec(state, state.cards[spell], seat,
                              {'target_card_id': target}, report_unsupported=False)
    assert snap(state) == before
    assert not spec.used_fallback and spec.effect.key != 'noop'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('foreign', [False, True])
def test_real_paid_control_untap_haste_and_natural_cleanup_restore_prior_controller(
        family, seat, foreign, tmp_path):
    state, spell, target = position(seat, family, foreign)
    owner = state.cards[target].owner
    sequence = state.cards[target].zone_change_sequence
    state = cast(state, seat, spell, target)
    assert state.stack[-1].controller == seat
    assert state.stack[-1].payload['mana_spent'] == (4 if family == 'ray-of-command' else 3)
    state = passes(restart(state, tmp_path, 'paid-temporary-control'))
    card = state.cards[target]
    assert card.controller == seat and card.owner == owner and not card.tapped
    assert card.zone_change_sequence == sequence and card.summoning_sick
    assert has_keyword(state, target, 'haste')
    assert state.cards[spell].zone == Zone.GRAVEYARD
    assert_private(state)
    if family == 'ray-of-command':
        retained_delay = deepcopy(state.delayed_triggers[-1])
    state = advance(restart(state, tmp_path, 'control-active-source-already-graveyard'))
    assert state.cards[target].controller == 3-seat
    assert state.cards[target].owner == owner and target in state.players[3-seat].battlefield
    assert not has_keyword(state, target, 'haste')
    assert state.cards[target].summoning_sick
    assert not state.temporary_control_changes
    if family == 'ray-of-command':
        from game_state.state import Step
        from rules_engine.targeting import spell_cant_be_countered
        assert state.step == Step.CLEANUP and state.cleanup_repeat_required
        assert not state.cards[target].tapped
        trigger = state.stack[-1]
        assert trigger.effect_key == 'control_loss_tap' and trigger.controller == seat
        assert trigger.source_card_id == spell == retained_delay['source_card_id']
        assert trigger.payload['card_id'] == target
        for key in ('incarnation', 'zone_change_sequence', '__delayed_source_reference'):
            assert trigger.payload[key] == retained_delay['payload'][key]
        assert trigger.targets == [] and 'target_card_id' not in trigger.payload
        assert not spell_cant_be_countered(state, trigger)
        state = passes(restart(state, tmp_path, 'cleanup-delayed-before-native-passes'))
    assert state.cards[target].tapped == (family == 'ray-of-command')
    assert_private(restart(state, tmp_path, 'control-cleanup'))


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_actually_gained_creature_can_be_deliberately_declared_attacking(family, seat, tmp_path):
    state, spell, target = position(seat, family)
    state = passes(cast(state, seat, spell, target))
    state = advance(state, attack_step=True)
    state = act(restart(state, tmp_path, 'gained-attacker'), seat,
                {'type': 'attack', 'attackers': [target]})
    assert target in state.attackers and state.cards[target].tapped


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_real_opponent_blink_response_does_not_steal_new_target_incarnation(family, seat, tmp_path):
    state, spell, target = position(seat, family)
    blink = raw_card(state, ROWS['cloudshift'], 3-seat, Zone.HAND).id
    sequence = state.cards[target].zone_change_sequence
    state = cast(state, seat, spell, target)
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = cast(state, 3-seat, blink, target)
    state = passes(state)
    assert state.cards[target].controller == 3-seat
    assert state.cards[target].zone_change_sequence == sequence + 2
    state = passes(restart(state, tmp_path, 'new-target-old-control-spell-stacked'))
    assert state.cards[target].controller == 3-seat
    assert target not in state.temporary_control_changes


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_unknown_target_rejects_without_any_payment_or_root_mutation(seat, family):
    state, spell, _ = position(seat, family)
    before = snap(state)
    with pytest.raises(ActionRejected):
        cast(state, seat, spell, 'not-a-card')
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_blink_after_theft_does_not_revert_fresh_object_at_old_effect_cleanup(family, seat, tmp_path):
    state, spell, target = position(seat, family)
    blink = raw_card(state, ROWS['cloudshift'], seat, Zone.HAND).id
    state = passes(cast(state, seat, spell, target))
    assert state.cards[target].controller == seat
    sequence = state.cards[target].zone_change_sequence
    state = passes(cast(state, seat, blink, target))
    assert state.cards[target].controller == seat
    assert state.cards[target].zone_change_sequence == sequence + 2
    state = advance(restart(state, tmp_path, 'blink-new-object-old-control-duration'))
    assert state.cards[target].controller == seat
    assert target in state.players[seat].battlefield
    assert target not in state.temporary_control_changes


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_unobserved_canonical_control_spell_identity_swap_is_private(seat, family):
    state, _, _ = position(seat, family)
    first = raw_card(state, ROWS['ray-of-command'], 3-seat, Zone.HAND)
    second = raw_card(state, ROWS['act-of-treason'], 3-seat, Zone.LIBRARY)
    changed = deepcopy(state)
    for cid, replacement in [(first.id, second), (second.id, first)]:
        card = deepcopy(replacement)
        original = changed.cards[cid]
        card.id, card.zone = cid, original.zone
        card.zone_change_sequence = original.zone_change_sequence
        changed.cards[cid] = card
    before = snap(state)
    view, moves = decision_view(state, seat, RulesEngine().legal_moves(state, seat))
    alternate, other_moves = decision_view(changed, seat, RulesEngine().legal_moves(changed, seat))
    assert snap(view) == snap(alternate) and moves == other_moves
    assert snap(state) == before
