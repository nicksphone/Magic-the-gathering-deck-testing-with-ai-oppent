"""Inert harness checks; authored outcomes are not evaluation evidence."""
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.archetype_matrix_plan import SEEDS, build_plan, first_divergence, paired_interval, summarize

@pytest.fixture
def plan():
    return build_plan('a'*40, (Path(__file__).parents[1]/'decks/builtin_decks.py').read_text())

def outcomes(plan):
    return [dict(cell_id=c['cell_id'], revision=plan['revision'], status='resolved', winner=c['deck_a_seat'], termination='life', trace_sha256='b'*64) for c in plan['cells']]

def test_schedule(plan):
    assert len(plan['decks']) == 11 and len(plan['cells']) == 2200
    assert len({c['cell_id'] for c in plan['cells']}) == 2200
    assert all(sum(c['seed']==s for c in plan['cells'])==110 for s in SEEDS)
    assert plan['execution_implemented'] is False and plan['policy']['resume'] is False

def test_all_win_and_isolation(plan):
    rows=outcomes(plan); original=deepcopy([plan,rows]); result=summarize(plan,rows)
    assert len(result['pairs']) == 55
    assert all(p['paired_score_ci95']==[1,1] and p['complete_seed_pairs']==20 for p in result['pairs'])
    assert [plan,rows] == original and result['strength_claim'] is False

@pytest.mark.parametrize('mutation',['missing','duplicate','foreign','revision','bool_winner','timeout_win','budget'])
def test_refusals(plan,mutation):
    rows=outcomes(plan)
    if mutation=='missing': rows.pop()
    elif mutation=='duplicate': rows[-1]=deepcopy(rows[0])
    elif mutation=='foreign': rows[-1]['cell_id']='c'*64
    elif mutation=='revision': rows[-1]['revision']='c'*40
    elif mutation=='bool_winner': rows[-1]['winner']=True
    elif mutation=='timeout_win': rows[-1]['status']='timeout'
    else: plan['policy']['max_turns']=1000
    with pytest.raises(ValueError): summarize(plan,rows)

def test_timeout_bounds(plan):
    rows=outcomes(plan)
    for r in rows:r.update(status='timeout',winner=None,termination='wall_limit')
    assert all(p['paired_score_ci95'] is None and p['score_identification_bounds']==[0,1] and p['outcomes']=={'timeout':40} for p in summarize(plan,rows)['pairs'])

def test_draw_and_deckout(plan):
    rows=outcomes(plan)
    for r in rows:r.update(status='draw',winner=None,termination='engine_draw')
    assert all(p['paired_score_ci95']==[0.5,0.5] for p in summarize(plan,rows)['pairs'])
    for r in rows:r.update(status='resolved',winner=1,termination='deck_out')
    assert all(p['score_identification_bounds']==[0.5,0.5] for p in summarize(plan,rows)['pairs'])

def test_bootstrap():
    assert paired_interval([0.5]*20,1)==[0.5,0.5]
    assert paired_interval([0]*10+[1]*10,2)==paired_interval([0]*10+[1]*10,2)

@pytest.mark.parametrize('left,right,expected',[
    ([{'a':1}],[{'a':2}],{'step':0,'fields':['a']}),
    ([{}],[{},{}],{'step':1,'fields':['trace_length']}),
    ([{'optional':None}],[{}],{'step':0,'fields':['optional']}),
    ([{'flag':True}],[{'flag':1}],{'step':0,'fields':['flag']}),
    ([{'a':1}],[{'a':1}],None),
])
def test_first_difference(left,right,expected):
    assert first_divergence(left,right)==expected
