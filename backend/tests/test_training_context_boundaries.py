"""Native stale-reference/privacy cases and labeled detached schema protocols."""
from copy import deepcopy
import json

import pytest

from game_state.state import Zone
from tests.test_training_environment import cast, position, resolve
from tests.test_training_reference_context import _field, _paid_two_bolts
from training import decision_frame as features
from training.dataset import episode_groups, episode_records, model_input


def _bolt_decision(seat):
    environment, cid = position(seat)
    environment.step(cast(environment, cid, target_player=3-seat), seat)
    return environment


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_native_competing_counterspells_leave_explicit_unknown_stack_reference(seat):
    environment, actions, announced = _paid_two_bolts(seat, True)
    state = environment._state
    first_counter = actions[seat]['card_id']
    second = next(card for card in state.cards.values()
                  if card.owner == seat and card.name == 'Counterspell' and card.id != first_counter)
    # Retained C2 resource/zone pose only; both following casts/payments are genuine.
    for zone in ('hand', 'library', 'battlefield', 'graveyard', 'exile'):
        ids = getattr(state.players[seat], zone)
        if second.id in ids:
            ids.remove(second.id)
    state.players[seat].hand.append(second.id)
    second.move_to_zone(Zone.HAND)
    state.players[seat].mana_pool = {'U': 4}
    expired = announced[seat]
    environment.step(actions[seat], seat)
    remaining_counter = environment.observe(seat)['stack'][-1]['id']
    environment.step(cast(environment, second.id, target_stack_id=expired), seat)
    assert environment.observe(seat)['players'][str(seat)]['mana_pool'].get('U', 0) == 0
    resolve(environment)
    assert expired not in [item['id'] for item in environment.observe(environment.acting_seat)['stack']]
    if environment.acting_seat != seat:
        environment.step({'type': 'pass_priority'})
    assert environment.acting_seat == seat
    before = environment.snapshot()
    observation, prompts = environment.observe(seat), environment.prompts(seat)
    context = environment.decision_context(seat)
    retained = next(item for item in context['stack'] if item['stack_id'] == remaining_counter)
    assert retained['announcement_available'] is True
    assert retained['announced_targets'] == {'target_stack_id': expired}
    assert retained['reference_lifecycle'] == 'unknown'
    frame, _ = features.build_decision_frame(observation, prompts, public_context=context)
    encoded = features.encode_state(frame)
    unknown = [entry for entry in encoded['entities']
               if _field(entry, 'entity_kind') == {'kind': 'text', 'value': 'public_reference'}]
    assert len(unknown) == 1
    assert {key['value'] for key, _ in unknown[0]['items']} == {'entity_kind', 'reference_role', 'visibility'}
    assert _field(unknown[0], 'reference_role') == {'kind': 'text', 'value': 'stack'}
    assert _field(unknown[0], 'visibility') == {'kind': 'text', 'value': 'unknown'}
    assert expired not in json.dumps(encoded, sort_keys=True)
    assert environment.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2], ids=['seat1', 'seat2'])
def test_actor_public_context_ignores_hidden_order_rng_and_private_log(seat):
    environment = _bolt_decision(seat)
    expected = environment.decision_context(seat)
    # Controlled privacy perturbation of generated builtin state, not a gameplay proof.
    for player in environment._state.players.values():
        player.library.reverse()
    environment._state.rng.random()
    environment._state.log.append('PRIVATE-CONTEXT-CANARY')
    before = environment.snapshot()
    assert environment.decision_context(seat) == expected
    assert environment.snapshot() == before
    groups = episode_groups(17, ['context-privacy'], before['provenance']['deck_hashes'])
    rows = list(episode_records(environment, lambda _: {'type': 'pass_priority'},
                               episode='episode-0000', groups=groups, tick_budget=1,
                               decision_frame=True, public_context=True))
    assert rows[1]['accepted'] is True
    frame = model_input(rows[1])
    assert frame['version'] == 'mtg.decision.v2'
    assert 'hand' not in frame['observation']['players'][str(3-seat)]
    assert all('library' not in player for player in frame['observation']['players'].values())
    assert set(frame) == {'version', 'observation', 'prompts', 'public_context'}
    assert set(frame['public_context']) == {'version', 'seat', 'stack'}
    assert 'PRIVATE-CONTEXT-CANARY' not in json.dumps(frame)
    assert all(set(item) == {'stack_id', 'announcement_available', 'announced_targets', 'reference_lifecycle'}
               and item['announced_targets'] == {'target_player': 3-seat}
               for item in expected['stack'])
    assert rows[-1]['complete'] is False and rows[-1]['terminal_rewards'] is None


@pytest.mark.parametrize('mutation', ['lifecycle', 'availability-int', 'unavailable-targets',
                                    'target-bool', 'wrong-actor', 'duplicate-stack',
                                    'private-top-field', 'private-mode-field'])
def test_detached_context_protocol_rejects_malformed_or_private_fields_atomically(mutation):
    environment = _bolt_decision(1)
    observation, prompts = environment.observe(1), environment.prompts(1)
    context = environment.decision_context(1)
    item = context['stack'][0]
    if mutation == 'lifecycle':
        item['reference_lifecycle'] = 'verified'
    elif mutation == 'availability-int':
        item['announcement_available'] = 1
    elif mutation == 'unavailable-targets':
        item['announcement_available'] = False
    elif mutation == 'target-bool':
        item['announced_targets'] = {'target_player': True}
    elif mutation == 'wrong-actor':
        context['seat'] = 2
    elif mutation == 'duplicate-stack':
        context['stack'].append(deepcopy(item))
    elif mutation == 'private-top-field':
        context['private_continuation'] = {'marker': 'PRIVATE-CONTEXT-CANARY'}
    elif mutation == 'private-mode-field':
        item['announced_targets'] = {'mode_targets': {'Public mode': {
            'target_player': 2, 'draw_payload': 'PRIVATE-CONTEXT-CANARY'}}}
    inputs = deepcopy((observation, prompts, context))
    before = environment.snapshot()
    with pytest.raises(ValueError):
        features.build_decision_frame(observation, prompts, public_context=context)
    assert (observation, prompts, context) == inputs
    assert environment.snapshot() == before
