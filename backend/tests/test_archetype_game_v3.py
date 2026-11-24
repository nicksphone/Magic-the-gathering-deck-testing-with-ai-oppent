"""Real bounded engine transitions; no pilot or statistical matrix execution."""
from copy import deepcopy
import importlib
import importlib.util
import io
from types import SimpleNamespace

import pytest


def subject():
    name = 'scripts.archetype_game_v3'
    assert importlib.util.find_spec(name) is not None, 'V3 game/replay adapter is missing'
    return importlib.import_module(name)


def choose(state, moves, actor):
    land = next((move for move in moves if move['type']=='play_land'), None)
    action = ({'type':'keep_hand'} if state.pregame_pending else
              deepcopy(land) if land is not None else {'type':'pass_priority'})
    return SimpleNamespace(action=action,
                           reasoning='unit deterministic choice', knowledge_usage=None)


def decks():
    from card_data.seed_cards import seed_card_payload
    return [{**seed_card_payload('Island'), 'card_name':'Island', 'quantity':60}]


def make_trace(ticks=4, *, decision=choose):
    from scripts.archetype_trace_v3 import TraceWriter, read_records
    module=subject(); stream=io.BytesIO(); writer=TraceWriter(stream)
    outcome=module.play_game(decks(),decks(),seed=8899,game_id='v3-unit',
        policy={'max_ticks':ticks,'max_turns':100},identity={'cell_id':'unit'},
        emit=writer.emit,choose=decision)
    return list(read_records(io.BytesIO(stream.getvalue()))),outcome,stream.getvalue()


def rechained(rows):
    from scripts.archetype_trace_v3 import CHAIN_KEYS, TraceWriter, read_records
    stream=io.BytesIO();writer=TraceWriter(stream)
    for row in rows:writer.emit({k:v for k,v in row.items()if k not in CHAIN_KEYS})
    return list(read_records(io.BytesIO(stream.getvalue())))


def test_exact_old_full_state_equivalence_and_new_sequential_roundtrip():
    from scripts.archetype_matrix_game import play_game
    from scripts.archetype_matrix_plan import digest
    old=[];new,outcome,_=make_trace()
    expected=play_game(decks(),decks(),seed=8899,game_id='v3-unit',
        policy={'max_ticks':4,'max_turns':100},emit=old.append,choose=choose)
    assert outcome==expected
    assert new[0]['snapshot']==old[0]['snapshot']
    for current,previous in zip(new[1:-1],old[1:-1]):
        assert current['action']==previous['action'] and current['actor']==previous['actor']
        assert current['before_sha256']==digest(previous['before'])
        assert current['after_sha256']==digest(previous['after'])
        assert current['legal_moves_sha256']==digest(previous['legal_moves'])
        assert current['rng_sha256']==digest(previous['after']['rng_state'])
    assert subject().replay_trace(iter(new))=={'matched':True,'actions':4,
        'status':'tick_limit','restart_roundtrips':4,'outcome':outcome}


def test_noncheckpoint_actions_have_only_digests_and_checkpoint64_is_exact():
    rows,outcome,data=make_trace(70)
    actions=rows[1:-1]
    assert outcome['accepted_actions']==70
    assert 'checkpoint' not in actions[62] and 'checkpoint' not in actions[64]
    assert actions[63]['checkpoint_reasons']==['periodic']
    assert set(actions[63]['checkpoint'])=={'before','after','before_cards_order','after_cards_order'}
    assert 'handler' in actions[0]['checkpoint_reasons']
    assert 'pregame' in actions[1]['checkpoint_reasons']
    assert 'final' in actions[-1]['checkpoint_reasons']
    assert all('before' not in r and 'after' not in r and 'legal_moves' not in r for r in actions)
    assert subject().replay_trace(iter(rows))['restart_roundtrips']==70
    from scripts.archetype_trace_v3 import canonical
    assert len(data)<70*len(canonical(rows[0]['snapshot']))//4


@pytest.mark.parametrize('field',['actor','action','legal_moves_sha256','before_sha256',
    'after_sha256','rng_sha256','before_cards_order_sha256','after_cards_order_sha256','progress','log_delta','checkpoint','missing_checkpoint'])
def test_rechained_semantic_corruption_fails_at_first_action(field):
    rows,_,_=make_trace();rows=deepcopy(rows);row=rows[1]
    if field=='actor':row['actor']=2
    elif field=='action':row['action']={'type':'invented'}
    elif field=='progress':row['progress']['turn']=900
    elif field=='log_delta':row['log_delta']['append']=['invented']
    elif field=='checkpoint':row['checkpoint']['after']['players']['1']['life']=1
    elif field=='missing_checkpoint':row.pop('checkpoint');row.pop('checkpoint_reasons')
    else:row[field]='0'*64
    with pytest.raises(subject().TraceDivergence) as error:
        subject().replay_trace(iter(rechained(rows)))
    assert error.value.step==0 and error.value.fields


def test_initial_final_and_early_completion_cannot_be_rebound_into_success():
    for where in ('initial','final','early'):
        rows,_,_=make_trace();rows=deepcopy(rows)
        if where=='initial':rows[0]['snapshot']['players']['1']['life']=1
        elif where=='final':rows[-1]['outcome']['accepted_actions']=1
        else:
            rows.pop(-2)
            rows[-1]['outcome']['accepted_actions']=3
        with pytest.raises(subject().TraceDivergence):subject().replay_trace(iter(rechained(rows)))


def test_ai_input_mutation_is_not_hidden_by_the_lighter_trace():
    def bad(state,moves,actor):
        state.players[actor].life=1
        return choose(state,moves,actor)
    with pytest.raises(subject().TraceDivergence) as error:make_trace(decision=bad)
    assert error.value.fields==['AI_input_mutation']


def test_real_master_one_action_and_rejected_action_keep_existing_outcomes():
    module=subject()
    good,outcome,_=make_trace(1,decision=None)
    assert outcome['accepted_actions']==1 and module.replay_trace(iter(good))['matched']
    def bad(state,moves,actor):return SimpleNamespace(action={'type':'play_land','card_id':'missing'},reasoning='unit invalid')
    rows,outcome,_=make_trace(decision=bad)
    assert outcome['status']=='error' and outcome['accepted_actions']==0 and outcome['winner'] is None
    assert module.replay_trace(iter(rows))['status']=='error'


def test_replay_refuses_noncanonical_action_parameters_even_if_engine_ignores_them():
    rows,_,_=make_trace();rows=deepcopy(rows)
    rows[1]['action']['ignored_parameter']=True
    with pytest.raises(subject().TraceDivergence) as error:
        subject().replay_trace(iter(rechained(rows)))
    assert error.value.step==0


def test_verification_exposes_the_full_replayed_outcome_for_parent_binding():
    rows,outcome,_=make_trace()
    replay=subject().replay_trace(iter(rows))
    assert replay.get('outcome')==outcome


@pytest.mark.parametrize('value',[-1,True])
def test_replay_refuses_invalid_timing_types_without_scoring_them(value):
    rows,_,_=make_trace();rows=deepcopy(rows)
    rows[1]['decision_seconds']=value
    with pytest.raises(subject().TraceDivergence) as error:
        subject().replay_trace(iter(rechained(rows)))
    assert error.value.step==0


def test_replay_refuses_self_consistent_actions_after_the_declared_tick_boundary():
    from scripts.archetype_matrix_game import play_game
    rows,_,_=make_trace(5);rows=deepcopy(rows);old=[]
    play_game(decks(),decks(),seed=8899,game_id='v3-unit',policy={'max_ticks':5,'max_turns':100},
              emit=old.append,choose=choose)
    rows[0]['policy']['max_ticks']=4
    rows[4]['checkpoint_reasons']=['final']
    rows[4]['checkpoint']={'before':old[4]['before'],'after':old[4]['after'],
                           'before_cards_order':rows[0]['cards_order'].copy(),
                           'after_cards_order':rows[0]['cards_order'].copy()}
    with pytest.raises(subject().TraceDivergence) as error:
        subject().replay_trace(iter(rechained(rows)))
    assert error.value.step==4


def simultaneous_combat_fixture(monkeypatch):
    """Declared combat birth, then real attack/block/damage-choice transitions."""
    import json
    from pathlib import Path
    from game_state.state import Step, Zone
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    from scripts import archetype_matrix_game as previous
    original = previous.initial_state
    root = Path(__file__).parent/'fixtures'
    raw_a = json.loads((root/'library_canonical_88/grizzly-bears-scryfall-raw.json').read_text())
    raw_b = json.loads((root/'ai_decisions_canonical_cdba/runeclaw-bear-scryfall-raw.json').read_text())
    a = [{**raw_a, 'card_name':raw_a['name'], 'quantity':60}]
    b = [{**raw_b, 'card_name':raw_b['name'], 'quantity':60}]

    def born(deck_a, deck_b, seed, game_id):
        state = original(deck_a, deck_b, seed, game_id)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.turn = 3
        state.active_player = state.priority_player = 1
        state.step = Step.DECLARE_ATTACKERS
        ids = []
        for pid in (1, 2, 2):
            cid = next(cid for cid, card in state.cards.items() if card.owner == pid and card.zone != Zone.BATTLEFIELD)
            card = state.cards[cid]
            getattr(state.players[pid], card.zone.value).remove(cid)
            card.move_to_zone(Zone.BATTLEFIELD)
            state.players[pid].battlefield.append(cid)
            card.summoning_sick = False
            ids.append(cid)
        # Dictionary order is an engine-observable representation, not a rules edit.
        state.cards = dict(reversed(list(state.cards.items())))
        rules = RulesEngine()
        state = checked_action(state, rules, 1, {'type':'attack', 'attackers':[ids[0]]})
        for _ in range(12):
            if state.step == Step.DECLARE_BLOCKERS:
                break
            state = checked_action(state, rules, state.priority_player, {'type':'pass_priority'})
        assert state.step == Step.DECLARE_BLOCKERS
        state = checked_action(state, rules, 2, {'type':'block', 'blocks':{ids[0]:ids[1:]}})
        assert state.step == Step.DECLARE_BLOCKERS and state.blocks
        return state

    monkeypatch.setattr(previous, 'initial_state', born)
    monkeypatch.setattr(subject(), 'initial_state', born)
    return a, b


def combat_choice(state, moves, actor):
    move = next((m for m in moves if m['type']=='choose_mechanic' and m.get('kind')=='combat_damage'), None)
    action = ({'type':'choose_mechanic','damage_assignment':{
        target:move['count'] if index == 0 else 0 for index,target in enumerate(move['options'])}}
              if move else {'type':'pass_priority'})
    return SimpleNamespace(action=action, reasoning='declared combat unit', knowledge_usage=None)


def test_real_simultaneous_sba_deaths_replay_keeps_native_card_order_and_v2_digests(monkeypatch):
    from scripts import archetype_matrix_game as previous
    from scripts.archetype_trace_v3 import TraceWriter, read_records, digest
    a, b = simultaneous_combat_fixture(monkeypatch)
    stream = io.BytesIO(); writer = TraceWriter(stream)
    policy = {'max_ticks':4,'max_turns':100}
    old = []
    expected = previous.play_game(a,b,seed=221,game_id='ordered-combat-unit',policy=policy,
                                 emit=old.append,choose=combat_choice)
    outcome = subject().play_game(a,b,seed=221,game_id='ordered-combat-unit',policy=policy,
                                 identity={'cell_id':'ordered-unit'},emit=writer.emit,choose=combat_choice)
    rows = list(read_records(io.BytesIO(stream.getvalue())))
    assert outcome == expected and outcome['accepted_actions'] == 4 and outcome['status'] == 'tick_limit'
    assert any(sum('State-based action:' in line for line in row['after']['log']) >= 2 for row in old[1:-1])
    for current, before in zip(rows[1:-1], old[1:-1]):
        assert current['before_sha256'] == digest(before['before'])
        assert current['after_sha256'] == digest(before['after'])
    assert subject().replay_trace(iter(rows))['matched'] is True


def test_capture_preserves_native_order_separately_from_v2_snapshot_digest():
    from scripts.archetype_trace_v3 import CpuAccounting, digest
    from scripts.archetype_matrix_game import initial_state, snapshot
    from game_state.serializers import deserialize_match_snapshot
    state = initial_state(decks(), decks(), 998, 'order-capture-unit')
    state.cards = dict(reversed(list(state.cards.items())))
    captured = subject().capture(state, CpuAccounting())
    assert captured.sha256 == digest(snapshot(state))
    assert captured.value == snapshot(state)
    assert captured.cards_order == list(state.cards)
    assert captured.cards_order_sha256 == digest(list(state.cards))
    restored = deserialize_match_snapshot(subject().ordered_snapshot(captured.value, captured.cards_order))
    assert list(restored.cards) == list(state.cards)
    assert digest(snapshot(restored)) == captured.sha256
    assert list(state.cards) != list(captured.value['cards'])


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'extra', 'nonstring', 'notlist'])
def test_ordered_snapshot_refuses_incomplete_or_ambiguous_card_coverage(bad):
    from scripts.archetype_trace_v3 import CpuAccounting
    from scripts.archetype_matrix_game import initial_state
    captured = subject().capture(initial_state(decks(), decks(), 998, 'bad-order-unit'), CpuAccounting())
    order = captured.cards_order.copy()
    if bad == 'missing': order.pop()
    elif bad == 'duplicate': order[-1] = order[0]
    elif bad == 'extra': order.append('not-a-card')
    elif bad == 'nonstring': order[0] = None
    else: order = tuple(order)
    before = deepcopy(captured.value)
    with pytest.raises(ValueError): subject().ordered_snapshot(captured.value, order)
    assert captured.value == before


@pytest.mark.parametrize('where', ['initial', 'checkpoint', 'final', 'old_schema'])
def test_rechained_order_evidence_and_old_schema_cannot_be_silently_accepted(where):
    from scripts.archetype_trace_v3 import digest
    rows, _, _ = make_trace()
    if where == 'initial':
        rows[0]['cards_order'].reverse()
        rows[0]['cards_order_sha256'] = digest(rows[0]['cards_order'])
    elif where == 'checkpoint': rows[1]['checkpoint']['after_cards_order'].reverse()
    elif where == 'final':
        rows[-1]['cards_order'].reverse()
        rows[-1]['cards_order_sha256'] = digest(rows[-1]['cards_order'])
    else: rows[0]['schema'] = 3
    with pytest.raises(subject().TraceDivergence): subject().replay_trace(iter(rechained(rows)))


def test_ai_cannot_reorder_cards_without_triggering_input_mutation_guard():
    def bad(state, moves, actor):
        state.cards = dict(reversed(list(state.cards.items())))
        return choose(state, moves, actor)
    with pytest.raises(subject().TraceDivergence) as error: make_trace(decision=bad)
    assert error.value.fields == ['AI_input_mutation']


def test_selected_handler_boundary_receives_native_ordered_snapshots(monkeypatch):
    from scripts.archetype_trace_v3 import TraceWriter, read_records, digest
    from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
    from rules_engine.action_validation import checked_action
    from rules_engine.engine import RulesEngine
    a, b = simultaneous_combat_fixture(monkeypatch)
    stream = io.BytesIO(); writer = TraceWriter(stream)
    subject().play_game(a,b,seed=221,game_id='ordered-boundary-unit',policy={'max_ticks':4,'max_turns':100},
        identity={'cell_id':'ordered-boundary-unit'},emit=writer.emit,choose=combat_choice)
    rows = list(read_records(io.BytesIO(stream.getvalue()))); observed = []
    def boundary(first, row):
        assert digest(list(row['before']['cards'])) == row['before_cards_order_sha256']
        assert digest(list(row['after']['cards'])) == row['after_cards_order_sha256']
        state = deserialize_match_snapshot(deepcopy(row['before']))
        after = checked_action(state, RulesEngine(), row['actor'], row['action'])
        assert digest(serialize_match_snapshot(after)) == row['after_sha256']
        assert digest(list(after.cards)) == row['after_cards_order_sha256']
        observed.append(row['step'])
    assert subject().replay_trace(iter(rows), boundary=boundary)['matched']
    assert observed == [0, 1, 2, 3]


def test_real_handler_sqlite_check_matches_the_simultaneous_death_boundary(monkeypatch, tmp_path):
    from pathlib import Path
    from scripts.archetype_trace_v3 import TraceWriter, read_records
    from scripts.archetype_handler_v3 import HandlerChecks
    a, b = simultaneous_combat_fixture(monkeypatch)
    stream = io.BytesIO(); writer = TraceWriter(stream)
    subject().play_game(a,b,seed=221,game_id='ordered-sqlite-unit',policy={'max_ticks':4,'max_turns':100},
        identity={'cell_id':'ordered-sqlite-unit'},emit=writer.emit,choose=combat_choice)
    rows = list(read_records(io.BytesIO(stream.getvalue())))
    source_db = Path(__file__).resolve().parents[1]/'mtg_lab.db'
    original = source_db.lstat() if source_db.exists() else None
    checks = []
    with HandlerChecks(tmp_path/'ordered-parity.sqlite3') as handler:
        def boundary(first, row):
            if row['step'] == 2:
                checks.append(handler(first,row))
        assert subject().replay_trace(iter(rows),boundary=boundary)['matched']
    assert len(checks) == 1 and checks[0]['transition_equal'] and checks[0]['sqlite_roundtrip']
    assert all(checks[0][key] is True for key in ('cards_order_transition_equal','cards_order_sqlite_roundtrip','cards_order_restored'))
    assert (source_db.lstat() if source_db.exists() else None) == original


@pytest.mark.parametrize('loss', ['transition', 'sqlite', 'restore'])
def test_order_only_handler_mutations_fail_without_weakening_v2_snapshot_checks(monkeypatch, tmp_path, loss):
    import json
    from scripts.archetype_trace_v3 import TraceWriter, read_records, digest
    from scripts.archetype_handler_v3 import HandlerChecks
    from persistence.repository import Repository
    from game_state.serializers import serialize_match_snapshot
    a, b = simultaneous_combat_fixture(monkeypatch)
    stream = io.BytesIO(); writer = TraceWriter(stream)
    subject().play_game(a,b,seed=221,game_id='ordered-handler-negative',policy={'max_ticks':4,'max_turns':100},
        identity={'cell_id':'ordered-handler-negative'},emit=writer.emit,choose=combat_choice)
    rows = list(read_records(io.BytesIO(stream.getvalue())))
    altered = []
    with HandlerChecks(tmp_path/'negative.sqlite3') as handler:
        if loss == 'transition':
            original = handler.main.checked_action
            def unordered(*args, **kwargs):
                state = original(*args, **kwargs)
                before = digest(serialize_match_snapshot(state))
                state.cards = dict(sorted(state.cards.items()))
                assert digest(serialize_match_snapshot(state)) == before
                altered.append(True)
                return state
            monkeypatch.setattr(handler.main, 'checked_action', unordered)
        elif loss == 'sqlite':
            original = Repository.save_active_match
            saves = []
            def unordered(self, match_id, state_json, controller_json):
                saves.append(True)
                if len(saves) == 1:
                    return original(self, match_id, state_json, controller_json)
                state = json.loads(state_json)
                before = digest(state)
                state['cards'] = dict(sorted(state['cards'].items()))
                assert digest(state) == before
                altered.append(True)
                return original(self, match_id, json.dumps(state), controller_json)
            monkeypatch.setattr(Repository, 'save_active_match', unordered)
        else:
            original = handler.main._restore_active_matches
            def unordered(*args, **kwargs):
                result = original(*args, **kwargs)
                for match in handler.main.ACTIVE_MATCHES.values():
                    before = digest(serialize_match_snapshot(match.state))
                    match.state.cards = dict(sorted(match.state.cards.items()))
                    assert digest(serialize_match_snapshot(match.state)) == before
                altered.append(True)
                return result
            monkeypatch.setattr(handler.main, '_restore_active_matches', unordered)
        def boundary(first, row):
            if row['step'] == 2:
                return handler(first, row)
        with pytest.raises(subject().TraceDivergence) as error:
            subject().replay_trace(iter(rows), boundary=boundary)
        expected = {'transition':'handler_transition_cards_order',
                    'sqlite':'handler_sqlite_cards_order','restore':'handler_restored_cards_order'}
        assert altered and error.value.fields == [expected[loss]]



def test_replay_timing_bound_uses_the_admitted_wall_policy():
    rows, _, _ = make_trace()
    rows[1]['decision_seconds'] = 1600
    with pytest.raises(subject().TraceDivergence, match='timing'):
        subject().replay_trace(rechained(rows))
    rows[0]['policy']['max_seconds'] = 3000
    assert subject().replay_trace(rechained(rows))['matched'] is True
    rows[1]['decision_seconds'] = 3000.01
    with pytest.raises(subject().TraceDivergence, match='timing'):
        subject().replay_trace(rechained(rows))


def test_mutation_check_uses_the_same_snapshot_bytes_without_decoding(monkeypatch):
    import json

    module = subject()
    decoded = []
    original = json.loads

    def observe(data):
        value = original(data)
        if type(value) is dict and 'cards' in value and 'rng_state' in value:
            decoded.append(value)
        return value

    monkeypatch.setattr(module, 'json', SimpleNamespace(loads=observe))
    rows, outcome, _ = make_trace(ticks=1)
    assert outcome['accepted_actions'] == 1
    assert len(decoded) == 4  # initial, before, after, final
    assert module.replay_trace(iter(rows))['matched']


def test_roundtrip_redecodes_the_exact_payload_for_an_independent_restore(monkeypatch):
    module = subject()
    rows, _, _ = make_trace()

    def copy_small(value):
        assert not (type(value) is dict and 'cards' in value and 'rng_state' in value)
        return deepcopy(value)

    def mutate_observation(_initial, row):
        row['after']['players']['1']['life'] = -1
        row['after']['log'].append('observer-only text')

    monkeypatch.setattr(module, 'deepcopy', copy_small)
    assert module.replay_trace(iter(rows), boundary=mutate_observation)['restart_roundtrips'] == 4
