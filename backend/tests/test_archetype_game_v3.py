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
    assert set(actions[63]['checkpoint'])=={'before','after'}
    assert 'handler' in actions[0]['checkpoint_reasons']
    assert 'pregame' in actions[1]['checkpoint_reasons']
    assert 'final' in actions[-1]['checkpoint_reasons']
    assert all('before' not in r and 'after' not in r and 'legal_moves' not in r for r in actions)
    assert subject().replay_trace(iter(rows))['restart_roundtrips']==70
    from scripts.archetype_trace_v3 import canonical
    assert len(data)<70*len(canonical(rows[0]['snapshot']))//4


@pytest.mark.parametrize('field',['actor','action','legal_moves_sha256','before_sha256',
    'after_sha256','rng_sha256','progress','log_delta','checkpoint','missing_checkpoint'])
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
    rows[4]['checkpoint']={'before':old[4]['before'],'after':old[4]['after']}
    with pytest.raises(subject().TraceDivergence) as error:
        subject().replay_trace(iter(rechained(rows)))
    assert error.value.step==4
