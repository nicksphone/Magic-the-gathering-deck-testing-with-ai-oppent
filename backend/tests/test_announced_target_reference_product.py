"""Full canonical paid responses, not injected effects, frames, or events."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from tests.favor_lifecycle_support import position, ROWS, act, snap, restart
from tests.test_paid_counter_family_audit import ROWS as COUNTER_ROWS
from tests.test_linked_damage_targets import raw_card
from tests.test_kozilek_graveyard_trigger_audit import passes
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_batch_graveyard_publication_audit import client
from tests.test_paid_counter_family_audit import http_position
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_targeted_search_lifecycle_audit import cold_sql

FIXTURE = Path(__file__).parent / 'fixtures/announced_target_references'
for line in (FIXTURE / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split()
    assert hashlib.sha256((FIXTURE / Path(name).name).read_bytes()).hexdigest() == digest
EXTRA = {name: json.loads((FIXTURE / (name + '.json')).read_text())
         for name in ('pyrotechnics', 'kolaghans-command', 'twincast', 'ornithopter',
                      'unholy-heat', 'leafcrown-dryad', 'reclamation-sage')}


def setup(seat):
    state, data = position(seat)
    state.players[seat].mana_pool = {'R': 5, 'B': 2, 'U': 4, 'G': 8, 'C': 20}
    state.players[3-seat].mana_pool = {'W': 2}
    return state, data['target']


def ref(card):
    return {'card_id': card.id, 'incarnation': object_incarnation(card),
            'zone_change_sequence': card.zone_change_sequence}


def cast(state, seat, cid, targets):
    return act(state, seat, {'type': 'cast_spell', 'card_id': cid, 'targets': targets,
                             'cost_choice': {'id': 'base'}})


def blink(state, owner, target):
    if state.priority_player != owner:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    card = raw_card(state, ROWS['Cloudshift'], owner, Zone.HAND)
    state = cast(state, owner, card.id, {'target_card_id': target})
    return passes(state)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['bolt', 'activated-lux'])
def test_actual_paid_single_target_does_not_hit_blinked_new_object(seat, family, tmp_path):
    state, target = setup(seat)
    original = ref(state.cards[target])
    if family == 'bolt':
        source = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.HAND)
        state = cast(state, seat, source.id, {'target_card_id': target})
    else:
        source = raw_card(state, COUNTER_ROWS['Lux Cannon'], seat, Zone.BATTLEFIELD)
        source.counters['charge'] = 3  # Explicit retained canonical board, not cast/ETB proof.
        state = act(state, seat, {'type': 'activate_ability', 'card_id': source.id,
                                 'ability_index': 1, 'targets': {'target_card_id': target}})
        assert state.cards[source.id].tapped and state.cards[source.id].counters['charge'] == 0
    frame = deepcopy(state.stack[-1])
    state = blink(state, 3-seat, target)
    assert ref(state.cards[target]) != original and state.cards[target].zone == Zone.BATTLEFIELD
    state = passes(restart(state, tmp_path, family + '-after-real-blink'))
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].counters.get('__damage_marked', 0) == 0
    assert frame.payload['__announced_target_references']['targets']['target_card_id'] == original
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_modal_one_stale_target_keeps_other_mode(seat, tmp_path):
    state, target = setup(seat)
    artifact = raw_card(state, COUNTER_ROWS['Lux Cannon'], 3-seat, Zone.BATTLEFIELD)
    card = raw_card(state, EXTRA['kolaghans-command'], seat, Zone.HAND)
    damage = "Kolaghan's Command deals 2 damage to any target"
    destroy = 'Destroy target artifact'
    state = cast(state, seat, card.id, {'mode_texts': [destroy, damage], 'mode_targets': {
        destroy: {'target_card_id': artifact.id}, damage: {'target_card_id': target}}})
    frame = deepcopy(state.stack[-1])
    state = blink(state, 3-seat, target)
    state = passes(restart(state, tmp_path, 'modal-after-real-blink'))
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].counters.get('__damage_marked', 0) == 0
    assert state.cards[artifact.id].zone == Zone.GRAVEYARD
    assert frame.payload['__announced_target_references']['targets']['mode_targets'][destroy]['target_card_id']['card_id'] == artifact.id
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('all_stale', [False, True])
def test_actual_divided_damage_keeps_fixed_shares_after_blink(seat, all_stale, tmp_path):
    state, first = setup(seat)
    second = raw_card(state, ROWS['Grizzly Bears'], 3-seat, Zone.BATTLEFIELD).id
    card = raw_card(state, EXTRA['pyrotechnics'], seat, Zone.HAND)
    state = cast(state, seat, card.id, {'target_distribution': {first: 2, second: 2}})
    frame = deepcopy(state.stack[-1])
    state = blink(state, 3-seat, first)
    if all_stale:
        state = blink(state, 3-seat, second)
    state = passes(restart(state, tmp_path, 'divided-after-real-blink'))
    assert state.cards[first].zone == Zone.BATTLEFIELD
    assert state.cards[first].counters.get('__damage_marked', 0) == 0
    assert state.cards[second].zone == (Zone.BATTLEFIELD if all_stale else Zone.GRAVEYARD)
    assert frame.payload['__announced_target_references']['targets']['target_distribution'][first]['card_id'] == first
    assert state.players[1].life == state.players[2].life == 20
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keep', [False, True])
def test_real_twincast_keep_vs_explicit_same_id_new_object(seat, keep, tmp_path):
    state, target = setup(seat)
    original = ref(state.cards[target])
    bolt = raw_card(state, ROWS['Lightning Bolt'], seat, Zone.HAND)
    state = cast(state, seat, bolt.id, {'target_card_id': target})
    original_stack_id = state.stack[-1].id
    state = blink(state, 3-seat, target)
    current = ref(state.cards[target])
    assert current != original
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    copy_spell = raw_card(state, EXTRA['twincast'], seat, Zone.HAND)
    state = cast(state, seat, copy_spell.id, {'target_stack_id': original_stack_id})
    state = passes(state)
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'copy_target' and pending['player_id'] == seat
    assert 'target_card_id:' + target in pending['options']
    copy_id = pending['stack_id']
    selected = 'keep' if keep else 'target_card_id:' + target
    state = act(restart(state, tmp_path, 'copy-choice'), seat,
                {'type': 'choose_mechanic', 'card_ids': [selected]})
    copied = next(item for item in state.stack if item.id == copy_id)
    original_frame = next(item for item in state.stack if item.id == original_stack_id)
    assert copied.payload['__announced_target_references']['targets']['target_card_id'] == (original if keep else current)
    assert original_frame.payload['__announced_target_references']['targets']['target_card_id'] == original
    state = passes(state)
    assert state.cards[target].zone == (Zone.BATTLEFIELD if keep else Zone.GRAVEYARD)
    state = passes(state)
    assert not state.stack and state.cards[copy_spell.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1, 2])
def test_real_modal_copy_migrates_scalar_old_reference_and_refreshes_only_selected_mode(seat, tmp_path):
    state, _ = setup(seat)
    target = raw_card(state, EXTRA['ornithopter'], 3-seat, Zone.BATTLEFIELD).id
    original = ref(state.cards[target])
    destroy, damage = 'Destroy target artifact', "Kolaghan's Command deals 2 damage to any target"
    card = raw_card(state, EXTRA['kolaghans-command'], seat, Zone.HAND)
    state = cast(state, seat, card.id, {'mode_texts': [destroy, damage], 'target_card_id': target})
    original_id = state.stack[-1].id
    state = blink(state, 3-seat, target)
    current = ref(state.cards[target])
    copier = raw_card(state, EXTRA['twincast'], seat, Zone.HAND)
    state = cast(state, seat, copier.id, {'target_stack_id': original_id})
    state = passes(state)
    pending = state.pending_mechanic_choice
    copy_id = pending['stack_id']
    copied = next(item for item in state.stack if item.id == copy_id)
    for mode in (destroy, damage):
        assert copied.payload['__announced_target_references']['targets']['mode_targets'][mode]['target_card_id'] == original
    assert pending['mode_target_text'] == destroy
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert state.pending_mechanic_choice['mode_target_text'] == damage
    assert 'target_card_id:' + target in state.pending_mechanic_choice['options']
    state = act(restart(state, tmp_path, 'modal-copy-choice'), seat,
                {'type': 'choose_mechanic', 'card_ids': ['target_card_id:' + target]})
    copied = next(item for item in state.stack if item.id == copy_id)
    selected = copied.payload['__announced_target_references']['targets']['mode_targets']
    assert selected[destroy]['target_card_id'] == original
    assert selected[damage]['target_card_id'] == current
    assert next(item for item in state.stack if item.id == original_id).payload['__announced_target_references']['targets']['target_card_id'] == original
    state = passes(state)
    assert state.cards[target].zone == Zone.GRAVEYARD
    state = passes(state)
    assert not state.stack


def early_path(seat, path):
    state, target = setup(seat)
    if path == 'trigger':
        target = raw_card(state, EXTRA['ornithopter'], 3-seat, Zone.BATTLEFIELD).id
        state.trigger_order_choice_required = True
        state.trigger_order_choice_players = {seat}
        source = raw_card(state, EXTRA['reclamation-sage'], seat, Zone.HAND)
        state = cast(state, seat, source.id, {})
        state = passes(state)
        assert state.pending_trigger_order['phase'] == 'targets'
        item_id = state.pending_trigger_order['current_stack_id']
        state = act(state, seat, {'type': 'choose_trigger_target', 'stack_id': item_id,
                                 'target_card_id': target})
        assert state.stack[-1].payload['__trigger_target_choice']
    elif path == 'bestow':
        source = raw_card(state, EXTRA['leafcrown-dryad'], seat, Zone.HAND)
        state = act(state, seat, {'type': 'cast_spell', 'card_id': source.id,
                                 'cost_choice': {'id': 'bestow'}, 'targets': {'target_card_id': target}})
    else:
        source = raw_card(state, EXTRA['unholy-heat'], seat, Zone.HAND)
        state = cast(state, seat, source.id, {'target_card_id': target})
        assert state.stack[-1].effect_key == 'conditional_instruction'
    return blink(state, 3-seat, target), source.id, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('path', ['conditional', 'trigger', 'bestow'])
@pytest.mark.parametrize('bad', [None, {'version': True, 'targets': {}}, {'version': 1, 'targets': {'unexpected': 0}}])
def test_malformed_real_frame_rejects_before_early_pop_or_bestow_mutation(seat, path, bad):
    state, _, _ = early_path(seat, path)
    # Explicit negative internal corruption after a real paid episode, never positive fake context.
    state.stack[-1].payload['__announced_target_references'] = deepcopy(bad)
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    before = snap(state)
    with pytest.raises(ActionRejected, match='Malformed announced target references'):
        act(state, state.priority_player, {'type': 'pass_priority'})
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_real_bestow_fallback_retires_target_receipt_without_fizzling(seat):
    from rules_engine.stack_engine import resolve_top_of_stack
    state, source, target = early_path(seat, 'bestow')
    item = state.stack[-1]
    assert '__announced_target_references' in item.payload
    assert resolve_top_of_stack(state)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    assert state.cards[source].attached_to is None and state.cards[target].zone == Zone.BATTLEFIELD
    assert '__announced_targets' not in item.payload
    assert '__announced_target_references' not in item.payload


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('path', ['conditional', 'trigger', 'bestow'])
def test_real_episode_malformed_http_422_preserves_full_root_sql_and_restart(seat, path, repo, client):
    import main
    state, _, _ = early_path(seat, path)
    state.stack[-1].payload['__announced_target_references'] = {'version': True, 'targets': {}}
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    controller, _, _, url = http_position(repo, client, seat, 'Fertilid')
    state.id = controller.state.id
    controller.state = state  # Controlled installation of the actual paid episode, not runtime repair.
    controller.engine = RulesEngine()
    main._persist_active_match(repo, controller)
    mid = state.id
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    cold_sql(repo, mid, before)
    main.ACTIVE_MATCHES.pop(mid)
    main._restore_active_matches(repo, mid)
    controller = main.ACTIVE_MATCHES[mid]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post(url + '/action', json={'player_id': state.priority_player,
        'action': {'type': 'pass_priority'}})
    assert response.status_code == 422, response.text
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
