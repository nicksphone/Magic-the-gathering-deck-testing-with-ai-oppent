"""Real paid siblings, unchanged semantic targets and public counter continuations."""
import hashlib
import json
from pathlib import Path

import pytest
import domain_paid_support as g
import test_springheart_paid_body as original
import test_complete_copy_payment_roots as complete
from free_owner_support import fund
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import checked_action, ActionRejected


@pytest.fixture(scope='module')
def sibling_facts():
    folder = Path(__file__).resolve().parent/'fixtures'
    facts = json.loads((folder/'canonical.json').read_bytes())
    proof = json.loads((folder/'provenance.json').read_bytes())
    for name, raw in facts.items():
        assert hashlib.sha256(json.dumps(raw, sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == proof['cards'][name]['canonical_fullrow_sha256']
    return facts


def residents(state, facts, seat, *, linked=False):
    for name in ('Renata, Called to the Hunt', 'Doubling Season',
                 'Branching Evolution' if linked else 'Hardened Scales'):
        g.add(state, facts, name, seat, Zone.BATTLEFIELD)


def cast_paid(state, seat, card, cost, request, **targets):
    state = g.respond(state, seat)
    before = serialize_match_snapshot(state)
    action = {'type': 'cast_spell', 'card_id': card, 'targets': targets}
    state = checked_action(state, RulesEngine(), seat, action)
    assert serialize_match_snapshot(state) != before
    frame = next(item for item in state.stack if item.source_card_id == card)
    assert frame.payload['mana_spent'] == cost
    original.record(request, state, 'actual-paid-sibling', actual_action=action,
                    actual_frame_id=frame.id, actual_effect_key=frame.effect_key)
    return state


def reach_choice_or_terminal(state, request):
    for _ in range(32):
        if state.pending_mechanic_choice or state.pending_replacement_choice or not state.stack:
            original.record(request, state, 'native-sibling-publication')
            return state
        assert not state.pending_trigger_order
        state = g.act(state, state.priority_player, 'pass_priority')
    raise AssertionError('Native sibling did not publish/finish within bounded actions')


def finish_counter_batch(state, request, restore, target_ids, *, expected_target=None):
    assert state.pending_replacement_choice
    pending = state.pending_replacement_choice
    data = pending['counter_payload']
    completion = data['entry_completion_payload']
    actual_ids = [row.get('card_id', row.get('candidate', {}).get('id')) for row in data['entry_targets']]
    assert set(actual_ids) == set(target_ids)
    if expected_target is not None:
        assert completion['target_card_id'] == expected_target
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, pending['player_id'])
    assert moves
    invalid = {'type': 'choose_replacement', 'replacement_source_id': 'not-an-actual-source'}
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), pending['player_id'], invalid)
    assert serialize_match_snapshot(state) == before
    original.record(request, state, 'actual-sibling-retained-target-payload',
                    actual_completion_payload=completion, actual_entry_ids=actual_ids,
                    invalid_choice_root_equal=True)
    state, choices = complete.complete_public_choices(g.restore(state) if restore else state, request, restore)
    assert choices
    for cid in target_ids:
        assert state.cards[cid].zone == Zone.BATTLEFIELD
        assert state.cards[cid].counters.get('+1/+1') in (3, 4)
    assert not state.pending_mechanic_choice and not state.pending_replacement_choice and not state.stack
    return state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_collected_company_two_entry_batch_preserves_selected_ids(sibling_facts, seat, restore, request):
    state = g.position(sibling_facts, seat)
    residents(state, sibling_facts, seat)
    targets = [g.add(state, sibling_facts, name, seat, Zone.LIBRARY)
               for name in ('Raging Goblin', 'Hopeful Eidolon')]
    spell = g.add(state, sibling_facts, 'Collected Company', seat, Zone.HAND)
    fund(state, seat, G=4)
    state = cast_paid(state, seat, spell, 4, request)
    state = reach_choice_or_terminal(state, request)
    assert state.pending_mechanic_choice and state.pending_mechanic_choice['kind'] == 'topdeck_put'
    assert set(targets).issubset(state.pending_mechanic_choice['options'])
    action = {'type': 'choose_mechanic', 'card_ids': targets}
    state = checked_action(g.restore(state) if restore else state, RulesEngine(), seat, action)
    state = finish_counter_batch(state, request, restore, targets)
    original.record(request, state, 'company-two-entry-terminal')
    assert all(cid not in state.players[seat].library for cid in targets)
    assert all(state.cards[cid].owner == state.cards[cid].controller == seat for cid in targets)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_actual_lockdown_multireturn_counter_continuation_preserves_rows(sibling_facts, seat, restore, request):
    state = g.position(sibling_facts, seat)
    residents(state, sibling_facts, seat, linked=True)
    targets = [g.add(state, sibling_facts, name, seat, Zone.BATTLEFIELD)
               for name in ('Raging Goblin', 'Hopeful Eidolon')]
    source = g.add(state, sibling_facts, 'Temporary Lockdown', seat, Zone.HAND)
    removal = g.add(state, sibling_facts, 'Naturalize', seat, Zone.HAND)
    fund(state, seat, W=3)
    state = cast_paid(state, seat, source, 3, request)
    state = original.finish(state)
    assert all(state.cards[cid].zone == Zone.EXILE for cid in targets)
    assert state.cards[source].zone == Zone.BATTLEFIELD
    fund(state, seat, G=2)
    state = cast_paid(g.restore(state) if restore else state, seat, removal, 2, request, target_card_id=source)
    state = reach_choice_or_terminal(state, request)
    state = finish_counter_batch(state, request, restore, targets)
    original.record(request, state, 'lockdown-two-return-terminal')
    assert state.cards[source].zone == Zone.GRAVEYARD
    assert all(cid not in state.players[seat].exile for cid in targets)
    assert all(state.cards[cid].owner == state.cards[cid].controller == seat for cid in targets)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
@pytest.mark.parametrize('route', ['blink', 'graveyard-return'])
def test_paid_single_entry_preserves_original_semantic_target(sibling_facts, seat, restore, route, request):
    state = g.position(sibling_facts, seat)
    residents(state, sibling_facts, seat)
    origin = Zone.BATTLEFIELD if route == 'blink' else Zone.GRAVEYARD
    target = g.add(state, sibling_facts, 'Raging Goblin', seat, origin)
    name = 'Cloudshift' if route == 'blink' else 'Zombify'
    spell = g.add(state, sibling_facts, name, seat, Zone.HAND)
    fund(state, seat, W=1) if route == 'blink' else fund(state, seat, B=1, C=3)
    state = cast_paid(state, seat, spell, 1 if route == 'blink' else 4, request, target_card_id=target)
    state = reach_choice_or_terminal(state, request)
    state = finish_counter_batch(state, request, restore, [target], expected_target=target)
    original.record(request, state, 'single-entry-target-roundtrip-terminal')
    assert state.cards[target].name == 'Raging Goblin'
    assert state.cards[target].owner == state.cards[target].controller == seat
