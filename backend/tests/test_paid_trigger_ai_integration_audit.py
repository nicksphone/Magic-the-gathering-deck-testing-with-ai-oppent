"""Actual frozen agent choices in constructed canonical tactical positions."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from training.environment import TrainingEnvironment, decode_action
from tests.test_death_cycle_ordering_audit import add, cards, restart, tokens
from tests.test_death_cycle_ordering_http_audit import act, frozen, install, offline_client, restore
from tests.test_paid_optional_triggers import fresh_readonly_restore, offered, require_pending


DIRECTORY = Path(__file__).parent / 'fixtures/paid_trigger_ai_audit'
RAW = {r['name']: r for r in map(json.loads, (DIRECTORY / 'canonical.jsonl').read_text().splitlines())}
cards.ROWS.update(RAW)
CASES = ['draw_lethal', 'draw_benefit', 'draw_unfunded',
         'token_counter', 'token_benefit', 'token_unfunded']
RULES = RulesEngine()


@pytest.fixture(autouse=True, scope='module')
def isolated_root():
    root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve()
    assert root == Path(__file__).resolve().parents[2]
    assert not str(root).startswith('/mnt/') and root != Path('/home/nick/mtg-deck-testing-lab')


def record(request, **data):
    directory = Path(os.environ['MTG_PAID_AI_EVIDENCE'])
    with (directory / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + '.json')).open('x') as f:
        json.dump({'node': request.node.nodeid, **data}, f, sort_keys=True, indent=2)
        f.write('\n')


def step(state, seat, action):
    with cards.unchanged_root(state):
        return checked_action(state, RULES, seat, action)


def advance(state, stop):
    for _ in range(12):
        if stop(state) or state.winner is not None:
            return state
        state = step(state, state.priority_player, {'type': 'pass_priority'})
    raise AssertionError('Exact constructed stack protocol did not reach its boundary')


def position(seat, case):
    state = cards.position(seat)
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {seat}
    secret = add(state, 'Swamp', 3-seat, Zone.HAND)
    add(state, 'Swamp', 3-seat, Zone.LIBRARY)
    source = add(state, 'Lunar Mystic' if case.startswith('draw') else 'Drake Haven', seat)
    source.owner = 3-seat
    counter = None
    if case.startswith('draw'):
        if case != 'draw_lethal':
            add(state, 'Island', seat, Zone.LIBRARY)
        state.players[3-seat].life = 3 if case == 'draw_lethal' else 20
        bolt = add(state, 'Lightning Bolt', seat, Zone.HAND)
        state.players[seat].mana_pool = {'R': 1, 'C': int(case != 'draw_unfunded')}
        state = step(state, seat, cards.cast(bolt, targets={'target_player': 3-seat}))
    else:
        sandbar = add(state, 'Lonely Sandbar', seat, Zone.HAND)
        for _ in range(2):
            add(state, 'Island', seat, Zone.LIBRARY)
        state.players[seat].mana_pool = {'U': 1, 'C': int(case == 'token_benefit')}
        if case == 'token_counter':
            state.players[seat].life = 3
            counter = add(state, 'Counterspell', seat, Zone.HAND)
            add(state, 'Island', seat)
            add(state, 'Island', seat)
            bolt = add(state, 'Lightning Bolt', 3-seat, Zone.HAND)
            state.active_player = state.priority_player = 3-seat
            state.players[3-seat].mana_pool = {'R': 1}
            state = step(state, 3-seat, cards.cast(bolt, targets={'target_player': seat}))
            state = step(state, 3-seat, {'type': 'pass_priority'})
        state = step(state, seat, {'type': 'cycle_card', 'card_id': sandbar.id})
    state = advance(state, lambda s: bool(s.pending_trigger_order))
    require_pending(state, source)
    assert state.stack[-1].payload['__optional_payment_cost'] == '{1}'
    return restart(state), source, secret, counter


PRIVATE_FIELDS = {'name', 'oracle_text', 'mana_cost', 'types', 'type_line', 'colors',
                  'keywords', 'power', 'toughness', 'card_faces', 'mechanic_metadata'}


class ForbiddenPrivateRead(CardInstance):
    def __getattribute__(self, name):
        if name in PRIVATE_FIELDS:
            raise AssertionError('Agent read an authoritative hidden card fact: ' + name)
        return super().__getattribute__(name)


@contextmanager
def hidden_read_guard(state, seat):
    hidden = state.players[3-seat].hand + state.players[3-seat].library + state.players[seat].library
    originals = [(state.cards[cid], type(state.cards[cid])) for cid in hidden]
    try:
        for card, _ in originals:
            card.__class__ = ForbiddenPrivateRead
        yield
    finally:
        for card, cls in originals:
            card.__class__ = cls


def actual_choice(state, seat, monkeypatch):
    moves = RULES.legal_moves(state, seat)
    assert moves and all(set(m) == {'type', 'stack_id', 'accept'} for m in moves)
    agent = AIAgent(difficulty='master', archetype='Control')
    real = agent._choose_action
    seen = []

    def observe(view, legal, player):
        assert view is not state
        for cid in state.players[3-seat].hand + state.players[3-seat].library + state.players[seat].library:
            card = view.cards[cid]
            assert card.ai_unknown and not card.name and not card.oracle_text and not card.types
            assert card is not state.cards[cid]
        seen.append(True)
        return real(view, legal, player)

    before = serialize_match_snapshot(state)
    with monkeypatch.context() as patch:
        patch.setattr(agent, '_choose_action', observe)
        with hidden_read_guard(state, seat):
            result = agent.choose_action(state, moves, seat)
    assert seen == [True] and serialize_match_snapshot(state) == before
    assert result.action in moves and set(result.action) == {'type', 'stack_id', 'accept'}
    return result


def branch(state, seat, accept):
    return step(state, seat, offered(state.pending_trigger_order, accept))


def verify_branches(state, seat, case, counter):
    no = branch(state, seat, False)
    assert not no.pending_trigger_order and not tokens(no, seat)
    if case.endswith('unfunded'):
        with cards.unchanged_root(state), pytest.raises(ActionRejected):
            branch(state, seat, True)
        return {'decline': serialize_match_snapshot(no), 'accept_atomically_unavailable': True}
    yes = branch(state, seat, True)
    if case == 'draw_lethal':
        assert yes.winner == 3-seat and yes.stack
        safe = advance(no, lambda s: not s.stack)
        assert safe.winner == seat and safe.players[3-seat].life <= 0
    elif case == 'token_counter':
        bolt_id = next(i.id for i in state.stack if i.source_card_id and state.cards[i.source_card_id].name == 'Lightning Bolt')
        safe = advance(no, lambda s: len(s.stack) == 1 and s.stack[0].id == bolt_id)
        if safe.priority_player != seat:
            safe = step(safe, safe.priority_player, {'type': 'pass_priority'})
        target = cards.cast(counter, targets={'target_stack_id': bolt_id})
        assert any(m.get('card_id') == counter.id for m in RULES.legal_moves(safe, seat))
        safe = step(safe, seat, target)
        safe = advance(safe, lambda s: not s.stack)
        assert safe.winner is None and safe.players[seat].life == 3
        doomed = advance(yes, lambda s: len(s.stack) == 1 and s.stack[0].id == bolt_id)
        if doomed.priority_player != seat:
            doomed = step(doomed, doomed.priority_player, {'type': 'pass_priority'})
        with cards.unchanged_root(doomed), pytest.raises(ActionRejected):
            step(doomed, seat, target)
        doomed = advance(doomed, lambda s: not s.stack)
        assert doomed.winner == 3-seat
        return {'decline_counter_survives': serialize_match_snapshot(safe),
                'accept_cannot_counter_loses': serialize_match_snapshot(doomed)}
    elif case == 'draw_benefit':
        assert len(yes.players[seat].hand) == len(no.players[seat].hand) + 1
        assert sum(yes.players[seat].mana_pool.values()) == 0
    else:
        generated = tokens(yes, seat)
        assert len(generated) == 1 and generated[0].power == generated[0].toughness == 2
        assert 'Flying' in generated[0].keywords and generated[0].colors == ['U']
        assert sum(yes.players[seat].mana_pool.values()) == 0
    return {'accept': serialize_match_snapshot(yes), 'decline': serialize_match_snapshot(no)}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', CASES)
def test_actual_agent_paid_choice_and_checked_outcome(request, monkeypatch, seat, case):
    state, _, _, counter = position(seat, case)
    decision = actual_choice(state, seat, monkeypatch)
    branches = verify_branches(state, seat, case, counter)
    result = branch(state, seat, decision.action['accept'])
    record(request, case=case, seat=seat, pending=serialize_match_snapshot(state),
           decision=decision.action, reasoning=decision.reasoning,
           actual_immediate=serialize_match_snapshot(result), authoritative_branches=branches,
           root_unchanged=True, hidden_reads_forbidden=True, constructed_not_natural=True)
    expected = case in {'draw_benefit', 'token_benefit'}
    assert decision.action['accept'] is expected, 'Actual optional policy disagrees with the proved tactical boundary'


def test_full_raw_rows_and_source_are_pinned():
    provenance = json.loads((DIRECTORY / 'provenance.json').read_text())
    assert hashlib.sha256((DIRECTORY / 'canonical.jsonl').read_bytes()).hexdigest() == provenance['canonical_jsonl_sha256']
    assert not provenance['facts_modified'] and provenance['http_requests'] == 0
    for name, row in RAW.items():
        assert hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() == provenance['rows'][name]['raw_sha256']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', CASES)
def test_whole_training_and_actual_api_optional_views(request, offline_client, monkeypatch, seat, case):
    state, _, secret, _ = position(seat, case)
    env = TrainingEnvironment()
    env.reset('Mono Red Aggro', 'Mono Red Aggro', seed=37)
    state.id, state.starting_decks = env._state.id, env._state.starting_decks
    env._state = restart(state)
    before = env.snapshot()
    view = env.observe(seat)
    assert secret.id not in json.dumps(view)
    for prompt in view['pending_choice']['prompts']:
        action = prompt['hint']
        assert set(action) == {'type', 'stack_id', 'accept'}
        assert decode_action(env.lookup_intent(action, seat)['id']) == action
        for invalid in [prompt, {**action, 'required_choices': prompt['required_choices']},
                        {**action, 'cost_text': '{1}'}, {**action, 'affordable': True}]:
            with pytest.raises(ActionRejected):
                env.lookup_intent(invalid, seat)
            assert env.snapshot() == before
    assert env.snapshot() == before
    match = install(restart(state), request, seat, private=True)
    before_api = frozen(match)
    response = offline_client.get('/matches/' + match.state.id + '/legal-moves', params={'player_id': seat})
    assert response.status_code == 200, response.text
    data = response.json()
    moves = data['moves']
    assert moves and all(set(m) == {'type', 'stack_id', 'accept'} for m in moves)
    assert secret.id not in json.dumps(data)
    for move in moves:
        assert decode_action(env.lookup_intent(move, seat)['id']) == move
    assert frozen(match) == before_api
    recovery = fresh_readonly_restore(match)
    decision = actual_choice(match.state, seat, monkeypatch)
    expected = branch(match.state, seat, decision.action['accept'])
    response = act(offline_client, match, seat, decision.action)
    assert response.status_code == 200, response.text
    match = restore(match.state.id)
    assert serialize_match_snapshot(match.state) == serialize_match_snapshot(expected)
    paid_recovery = fresh_readonly_restore(match)
    after_api = frozen(match)
    assert act(offline_client, match, seat, decision.action).status_code == 422
    assert frozen(match) == after_api
    expected_training = branch(env._state, seat, decision.action['accept'])
    env.step(decision.action, seat)
    assert serialize_match_snapshot(env._state) == serialize_match_snapshot(expected_training)
    record(request, case=case, seat=seat, training=view, api=data,
           root_sql_unchanged_on_view_and_rejection=True, recovery=recovery,
           paid_recovery=paid_recovery, actual_decision=decision.action,
           actual_http_equals_checked=True, actual_training_equals_checked=True)
