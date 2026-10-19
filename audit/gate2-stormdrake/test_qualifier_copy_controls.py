"""Real paid copied abilities retain their actor despite source control changes."""
import hashlib
import json

import pytest

import domain_paid_support as g
import test_paid_exchange_desired as original
import test_exchange_edges as edges
import test_qualifier_paid_controls as controls
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind


@pytest.fixture(scope='module')
def facts():
    rows = json.loads((original.HERE / 'qualifier-v2-canonical.json').read_bytes())
    pins = json.loads((original.HERE / 'qualifier-v2-provenance.json').read_bytes())
    previous = json.loads((original.HERE / 'qualifier-canonical.json').read_bytes())
    assert all(rows[name] == raw for name, raw in previous.items())
    for name, raw in rows.items():
        body = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(body).hexdigest() == pins['cards'][name]['canonical_fullrowSHA']
    return rows


def mature_by_public_turns(state, source, seat):
    history = []
    for _ in range(96):
        if (not state.cards[source].summoning_sick and state.active_player == seat
                and state.step == Step.PRECOMBAT_MAIN and not state.stack):
            return state, history
        public = original.moves(state, state.priority_player)
        action = next((move for move in public if move['type'] == 'pass_priority'), None)
        if action is None:
            action = next((move for move in public if move['type'] == 'declare_attackers'), None)
            if action:
                action = {'type': 'declare_attackers', 'attackers': []}
        assert action is not None, ('No public quiet turn action', state.step, public)
        history.append({'actor': state.priority_player, 'action': action})
        state = checked_action(state, RulesEngine(), state.priority_player, action)
    raise AssertionError('Paid creature did not mature in96 public actions')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['activated', 'triggered'])
def test_paid_mixed_source_controller_ability_copy_target_boundary(facts, seat, kind):
    state = g.position(facts, seat)
    opponent = g.add(state, facts, original.SOURCE, 3-seat)
    own = g.add(state, facts, original.SOURCE, seat)
    target = g.add(state, facts, 'Raging Goblin', 3-seat)
    state.cards[own].counters['+1/+1'] = 1  # Declared initial resource.
    state.cards[target].counters['+1/+1'] = 1
    name = 'Lithoform Engine' if kind == 'activated' else 'Strionic Resonator'
    state, copier = controls.paid_permanent(state, facts, seat, name,
                                           {'C': 4 if kind == 'activated' else 2})
    history = []
    if kind == 'activated':
        state, source = controls.paid_permanent(state, facts, seat, 'Prodigal Pyromancer', {'C': 2, 'R': 1})
        state, history = mature_by_public_turns(state, source, seat)
        state = checked_action(state, RulesEngine(), seat, controls.activation(state, seat, source, target))
    else:
        state, source = controls.paid_permanent(state, facts, seat, 'Suncleanser', {'C': 1, 'W': 1})
        public = original.moves(state, seat)
        options = [option for move in public if move['type'] == 'choose_mechanic'
                   for option in move.get('options', [])
                   if move.get('option_labels', {}).get(option, '').startswith('Remove all counters from target creature')]
        assert len(options) == 1
        state = g.act(state, seat, 'choose_mechanic', choice_id=options[0])
        choice = next(move for move in original.moves(state, seat)
                      if move['type'] == 'choose_trigger_target' and move.get('target_card_id') == target)
        state = checked_action(state, RulesEngine(), seat, choice)
    original_item = state.stack[-1].id
    assert stack_object_kind(state, state.stack[-1]) == kind
    private = (list(state.players[3-seat].hand), list(state.players[3-seat].library))
    # Real opponent instant changes current source controller, not stack actor.
    state = edges.paid_instant(state, facts, 3-seat, 'Ray of Command', {'C': 3, 'U': 1}, source)
    assert state.cards[source].controller == 3-seat
    assert next(item for item in state.stack if item.id == original_item).controller == seat
    state = g.respond(state, seat)
    state.players[seat].mana_pool = {'C': 2}
    public = original.moves(state, seat)
    choices = [move for move in public if move['type'] == 'activate_ability' and move.get('card_id') == copier
               and any(candidate.get('id') == original_item
                       for candidate in move.get('target_hints', {}).get('stack_targets', []))]
    if not choices:
        choices = [move for move in public if move['type'] == 'activate_ability' and move.get('card_id') == copier
                   and move.get('ability_index') == 0]
    assert len(choices) == 1
    state = g.act(state, seat, 'activate_ability', card_id=copier,
                  ability_index=choices[0]['ability_index'], targets={'target_stack_id': original_item})
    assert state.cards[copier].tapped and sum(state.players[seat].mana_pool.values()) == 0
    state = edges.settle(state)
    pending = state.pending_mechanic_choice
    assert pending and pending['kind'] == 'copy_target' and pending['player_id'] == seat
    copied = next(item for item in state.stack if item.payload.get('__stack_copy_kind'))
    assert copied.controller == seat and stack_object_kind(state, copied) == kind
    public = original.moves(state, seat)
    options = [option for move in public if move['type'] == 'choose_mechanic' for option in move.get('options', [])]
    lawful = next(option for option in options if option.endswith(':' + own))
    assert not any(option.endswith(':' + opponent) for option in options)
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        g.act(state, seat, 'choose_mechanic', card_ids=['target_card_id:' + opponent])
    assert serialize_match_snapshot(state) == before
    state = g.act(g.restore(state), seat, 'choose_mechanic', card_ids=[lawful])
    original.record(f'qualifier-mixed-copy-{kind}-{seat}-retargeted', state,
                    offered=public, original_item=original_item, copied_item=copied.id)
    state = edges.settle(state)
    original.record(f'qualifier-mixed-copy-{kind}-{seat}-resolved', state,
                    public_turn_history=history)
    assert not state.stack and not state.pending_mechanic_choice
    assert state.cards[opponent].zone == Zone.BATTLEFIELD
    if kind == 'activated':
        assert state.cards[own].counters['__damage_marked'] == 1
        assert state.cards[target].counters['__damage_marked'] == 1
    else:
        assert state.cards[own].counters.get('+1/+1', 0) == 0
        assert state.cards[target].counters.get('+1/+1', 0) == 0
    assert (state.players[3-seat].hand, state.players[3-seat].library) == private
    original.record(f'qualifier-mixed-copy-{kind}-{seat}', state, offered=public,
                    public_turn_history=history, original_item=original_item, copied_item=copied.id)
