"""Real canonical paid cast/entry triggers; desired effects, not noop witnesses."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ai.information import decision_view, is_unknown
from game_state.state import Step, Zone
from rules_engine import events, ability_model
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.targeting import stack_object_kind
from tests.test_library_reorder import setup
from tests.test_linked_damage_targets import raw_card
from tests.test_self_graveyard_replacement_audit import act, restart, snap

FIXTURE = Path(__file__).parent / 'fixtures/trigger_instruction_audit'
HASHES = {
    'kozilek': '1d6014c13740b848fedfa5da19a5d2a4916169c7f39c81d4bd09f66e676fe5ce',
    'cloudblazer': '1b189f5c7dc159e102f902d8311103873503508754036ef40e13688162ac7dfa',
    'thought-reflection': 'be46dc4724e675d029e095db7e065399de74e1b33b0379fd498e3ac90592128f',
    'elvish-visionary': 'a961487190f41f513161a4439db9d9a174d709c875e6d959828f2eeb73c0bd4c',
}
ROWS = {}
for slug, digest in HASHES.items():
    data = (FIXTURE / (slug + '.json')).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    row = json.loads(data)
    assert row['object'] == 'card' and row['oracle_id'] and row['oracle_text']
    ROWS[row['name']] = row

KOZILEK = 'Kozilek, Butcher of Truth'
FAMILIES = [KOZILEK, 'Cloudblazer']


@pytest.fixture(autouse=True)
def compilation_trace(monkeypatch, tmp_path):
    trace = []
    original = events._trigger_from_oracle
    build = ability_model.build_ability_spec

    def observe(state, source_card_id, controller, oracle, default_label, event, payload):
        result = original(state, source_card_id, controller, oracle, default_label, event, payload)
        trace.append({'kind': 'trigger', 'source': source_card_id, 'controller': controller,
                      'oracle': oracle, 'event': event, 'event_payload': deepcopy(payload),
                      'compiled': deepcopy(result)})
        return result

    def observe_build(*args, **kwargs):
        result = build(*args, **kwargs)
        trace.append({'kind': 'ability_spec', 'instruction': args[1].oracle_text,
                      'effect': {'key': result.effect.key, 'payload': deepcopy(result.effect.payload)}})
        return result

    monkeypatch.setattr(events, '_trigger_from_oracle', observe)
    monkeypatch.setattr(ability_model, 'build_ability_spec', observe_build)
    yield trace
    (tmp_path / 'actual-compilation.json').write_text(json.dumps(trace, sort_keys=True, default=str))


def position(name, seat, reflection=False):
    state, unused = setup('Index', seat, size=16)
    state.players[seat].hand.remove(unused.id)
    unused.move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(unused.id)
    source = raw_card(state, ROWS[name], seat, Zone.HAND)
    state.players[seat].mana_pool = ({'C': 10} if name == KOZILEK else
                                   {'C': 3, 'W': 1, 'U': 1} if name == 'Cloudblazer' else
                                   {'C': 1, 'G': 1})
    state.priority_stops = {pid: set(Step) for pid in (1, 2)}
    if reflection:
        # Trusted canonical retained battlefield position, not a claimed cast.
        raw_card(state, ROWS['Thought Reflection'], seat, Zone.BATTLEFIELD)
    return state, source.id, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}}


def passes(state):
    for _ in range(2):
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    return state


def pending(state, seat, action, name):
    state = act(state, seat, action)
    if name != KOZILEK:
        state = passes(state)
    return state


def item_for(state, cid):
    items = [item for item in state.stack if item.source_card_id == cid
             and stack_object_kind(state, item) == 'triggered']
    assert len(items) == 1
    return items[0]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('reflection', [False, True])
def test_paid_trigger_complete_effect_after_both_responses_restart(seat, name, reflection, tmp_path):
    state, cid, action = position(name, seat, reflection)
    other = snap(state)['players'][str(3-seat)]
    library = list(state.players[seat].library)
    life = state.players[seat].life
    state = pending(state, seat, action, name)
    assert item_for(state, cid).controller == seat
    assert state.players[seat].mana_pool == {key: 0 for key in state.players[seat].mana_pool}
    state = restart(state, tmp_path, 'pending-trigger')
    result = restart(passes(state), tmp_path, 'resolved-trigger')
    count = (4 if name == KOZILEK else 2) * (2 if reflection else 1)
    assert result.players[seat].hand == list(reversed(library[-count:])), 'Full printed draw amount must resolve'
    assert result.players[seat].life == life + (2 if name == 'Cloudblazer' else 0), 'Compound life instruction must not be dropped'
    assert snap(result)['players'][str(3-seat)] == other
    assert result.cards[cid].zone == (Zone.STACK if name == KOZILEK else Zone.BATTLEFIELD)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_compiled_payload_retains_full_instruction(seat, name, compilation_trace, tmp_path):
    state, cid, action = position(name, seat)
    state = pending(state, seat, action, name)
    item = item_for(state, cid)
    (tmp_path / 'actual-stack-item.json').write_text(json.dumps({'key': item.effect_key, 'payload': item.payload}, sort_keys=True))
    actual = [row for row in compilation_trace if row.get('source') == cid]
    assert actual and all(row['controller'] == seat for row in actual)
    assert item.effect_key != 'noop', 'Admitted genuine trigger must compile its complete body'
    if name == KOZILEK:
        assert item.effect_key == 'draw_cards' and item.payload['amount'] == 4
    else:
        # Execution verifies both pieces without coupling this audit to one composite IR spelling.
        life, hand = state.players[seat].life, len(state.players[seat].hand)
        result = passes(state)
        assert (result.players[seat].life-life, len(result.players[seat].hand)-hand) == (2, 2)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_valid_paid_admission_controller_private_pending_restore(seat, name, tmp_path):
    state, cid, action = position(name, seat)
    before = snap(state)
    offered = RulesEngine().legal_moves(state, seat)
    assert any(move['type'] == 'cast_spell' and move.get('card_id') == cid for move in offered)
    assert snap(state) == before
    result = pending(state, seat, action, name)
    trigger = item_for(result, cid)
    assert trigger.controller == seat and trigger.source_card_id == cid
    assert not result.players[seat].hand
    view, _ = decision_view(result, 3-seat, RulesEngine().legal_moves(result, 3-seat))
    assert all(is_unknown(view.cards[card]) for card in result.players[seat].library)
    restart(result, tmp_path, 'independent-valid-pending')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
@pytest.mark.parametrize('bad', ['wrong_actor', 'underpaid'])
def test_invalid_actual_cast_root_rng_log_unchanged(seat, name, bad):
    state, _, action = position(name, seat)
    if bad == 'underpaid':
        state.players[seat].mana_pool = {}
    before = snap(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 3-seat if bad == 'wrong_actor' else seat, action)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reflection', [False, True])
def test_independent_canonical_single_draw_etb_replacement_control(seat, reflection, tmp_path):
    state, cid, action = position('Elvish Visionary', seat, reflection)
    library = list(state.players[seat].library)
    state = pending(state, seat, action, 'Elvish Visionary')
    assert item_for(state, cid).effect_key == 'draw_cards'
    state = passes(restart(state, tmp_path, 'visionary-pending'))
    count = 2 if reflection else 1
    assert state.players[seat].hand == list(reversed(library[-count:]))
    assert state.cards[cid].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reflection', [False, True])
def test_compound_life_component_independent_of_draw_assertion(seat, reflection, tmp_path):
    state, _, action = position('Cloudblazer', seat, reflection)
    life = state.players[seat].life
    state = pending(state, seat, action, 'Cloudblazer')
    result = passes(restart(state, tmp_path, 'compound-life-pending'))
    assert result.players[seat].life == life + 2, 'Full compound must include the printed life gain'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_actual_paid_stifle_response_counters_trigger_not_source_spell(seat, name, tmp_path):
    from tests.test_kozilek_graveyard_trigger_audit import FRESH
    state, cid, action = position(name, seat)
    counter = raw_card(state, FRESH['Stifle'], 3-seat, Zone.HAND)
    state.players[3-seat].mana_pool = {'U': 1}
    state = pending(state, seat, action, name)
    target = item_for(state, cid).id
    if state.priority_player != 3-seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    state = act(restart(state, tmp_path, 'before-stifle'), 3-seat,
                {'type': 'cast_spell', 'card_id': counter.id,
                 'targets': {'target_stack_id': target}})
    hand, life = list(state.players[seat].hand), state.players[seat].life
    state = passes(state)
    assert all(item.id != target for item in state.stack)
    assert state.players[seat].hand == hand and state.players[seat].life == life
    assert state.cards[cid].zone == (Zone.STACK if name == KOZILEK else Zone.BATTLEFIELD)
    if name == KOZILEK:
        assert any(item.source_card_id == cid for item in state.stack)
    restart(state, tmp_path, 'countered-trigger')
