"""Native canonical paid Elf entry; malformed vectors below are codec negatives."""
from copy import deepcopy
import json

import pytest

from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.card_types import is_token_card
from tests.scheduler_fixture_position import ordinary_position
from tests.test_training_environment import cast, keep
from training import TrainingEnvironment
from training.decision_frame import build_decision_frame, encode_action, encode_state


@pytest.fixture(scope='module')
def native_orders():
    result = {}
    for seat in (1, 2):
        environment = TrainingEnvironment()
        environment.reset(*(('Tribal', 'Burn') if seat == 1 else ('Burn', 'Tribal')), seed=17)
        keep(environment)
        state = environment._state
        state.active_player = state.priority_player = seat
        state.step = Step.PRECOMBAT_MAIN
        ordinary_position(state)

        def pose(name, count, zone):
            cards = [card for card in state.cards.values() if card.name == name and card.owner == seat][:count]
            assert len(cards) == count
            for card in cards:
                for player in state.players.values():
                    for location in (Zone.HAND, Zone.LIBRARY, Zone.BATTLEFIELD, Zone.GRAVEYARD, Zone.EXILE):
                        ids = getattr(player, location.value)
                        if card.id in ids:
                            ids.remove(card.id)
                getattr(state.players[seat], zone.value).append(card.id)
                card.move_to_zone(zone)
                card.tapped = False
            return [card.id for card in cards]

        # Trusted pose only; the entry, payments, trigger generation and order are native.
        pose('Elvish Warmaster', 2, Zone.BATTLEFIELD)
        forests = pose('Forest', 3, Zone.BATTLEFIELD)
        elf = pose('Llanowar Elves', 1, Zone.HAND)[0]
        environment.step(cast(environment, elf))
        assert sum(environment._state.cards[cid].tapped for cid in forests) == 1
        assert environment._state.stack[-1].source_card_id == elf
        environment.step({'type': 'pass_priority'})
        environment.step({'type': 'pass_priority'})
        assert environment.acting_seat == seat and environment._state.pending_trigger_order
        observation, prompts = environment.observe(seat), environment.prompts(seat)
        assert len(prompts) == 2 and all(p['hint']['type'] == 'choose_trigger_order' for p in prompts)
        assert all(len(p['hint']['trigger_order']) == 2 for p in prompts)
        assert len(set(prompts[0]['hint']['trigger_labels'])) == 1
        result[seat] = (environment, observation, prompts, environment.decision_context(seat))
    return result


@pytest.mark.parametrize('seat', [1, 2])
def test_native_trigger_permutations_alias_roundtrip_and_execute(native_orders, seat):
    environment, observation, prompts, context = native_orders[seat]
    before = environment.snapshot()
    original = deepcopy((observation, prompts, context))
    frame, bindings = build_decision_frame(observation, prompts, public_context=context)
    raw_ids = prompts[0]['hint']['trigger_order']
    assert len(set(raw_ids)) == 2
    assert not set(raw_ids) & set(observation['known_cards'])
    assert 'hand' not in observation['players'][str(3-seat)]
    encoded = json.dumps(encode_state(frame), sort_keys=True)
    assert all(choice not in encoded for choice in raw_ids)
    assert not {'seed', 'starting_decks', 'rng_state'} & frame['observation'].keys()
    orders = []
    for prompt in prompts:
        actual = {'type': 'choose_trigger_order', 'trigger_order': prompt['hint']['trigger_order']}
        public = bindings.action(actual)
        assert all(choice.startswith('option:') for choice in public['trigger_order'])
        assert bindings.actual_action(public) == actual
        encode_action(frame, public)
        branch = TrainingEnvironment()
        branch.restore(before)
        branch.step(bindings.actual_action(public))
        for _ in range(8):
            if not branch._state.stack and not branch._state.pending_trigger_order:
                break
            branch.step({'type': 'pass_priority'})
        assert not branch._state.stack and not branch._state.pending_trigger_order
        tokens = [cid for cid in branch._state.players[seat].battlefield
                  if is_token_card(branch._state.cards[cid])]
        assert len(tokens) == 2
        orders.append(public['trigger_order'])
    assert orders[0] == list(reversed(orders[1]))
    with pytest.raises(ValueError):
        bindings.action({'type': 'choose_trigger_order', 'trigger_order': ['unoffered-trigger']})
    with pytest.raises(ValueError):
        bindings.actual_action({'type': 'choose_trigger_order', 'trigger_order': ['option:unoffered']})
    with pytest.raises(ActionRejected):
        environment.lookup({'type': 'choose_trigger_order', 'trigger_order': [raw_ids[0], raw_ids[0]]})
    assert environment.snapshot() == before and (observation, prompts, context) == original


@pytest.mark.parametrize('invalid', ['missing-labels', 'short-labels', 'nonstring-label',
    'empty-label', 'duplicate-id', 'nonlist-order', 'incomplete-permutation', 'conflicting-label'])
def test_malformed_public_trigger_descriptors_fail_closed(native_orders, invalid):
    _, original, original_prompts, context = native_orders[1]
    observation, prompts = deepcopy((original, original_prompts))
    hint = prompts[0]['hint']
    if invalid == 'missing-labels':
        del hint['trigger_labels']
    elif invalid == 'short-labels':
        hint['trigger_labels'].pop()
    elif invalid == 'nonstring-label':
        hint['trigger_labels'][0] = None
    elif invalid == 'empty-label':
        hint['trigger_labels'][0] = ''
    elif invalid == 'duplicate-id':
        hint['trigger_order'][1] = hint['trigger_order'][0]
    elif invalid == 'nonlist-order':
        hint['trigger_order'] = hint['trigger_order'][0]
    elif invalid == 'incomplete-permutation':
        hint['trigger_order'].pop()
        hint['trigger_labels'].pop()
    else:
        prompts[1]['hint']['trigger_labels'][0] = 'Contradictory public codec label'
    observation['pending_choice']['prompts'] = deepcopy(prompts)
    with pytest.raises(ValueError):
        build_decision_frame(observation, prompts, public_context=context)
