"""Focused protocol + real canonical checked choices; no model or game run."""
import ast
from contextlib import ExitStack
from copy import deepcopy
from inspect import signature
from pathlib import Path
import pickle
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai import agent as a, pending_effects as p, heuristics
from rules_engine.action_validation import ActionRejected


class BatchProtocol(unittest.TestCase):
    def batch(self, *, native=False, kinds=('compare', 'compare', 'compare'), unknown=False,
              baseline_winner=None, repeat=1, poison_memo=False):
        events=[]
        ids=['f'+str(i) for i in range(len(kinds))]
        state=SimpleNamespace(branch='reference', winner=None, score=0,
            delayed_triggers=[], staged_triggers=[], emblems=[],
            players={1:SimpleNamespace(battlefield=ids, library=['l1'], hand=[]),
                     2:SimpleNamespace(battlefield=[], library=['l2'], hand=[])},
            cards={cid:SimpleNamespace(controller=1) for cid in ids})
        card=SimpleNamespace(oracle_text='Destroy target creature.', types=['Instant'])
        action={'type':'cast_spell','card_id':'removal'}
        def policy(projected, moves, pid):
            events.append(('policy', projected.branch));return {'type':'pass_priority'}
        def paid(projected, rules, pid, move):
            cid=move['targets']['target_card_id'];events.append(('paid',cid));kind=kinds[ids.index(cid)]
            if kind=='rejected':raise ActionRejected('same rejection')
            if kind=='uncertain':raise p.UncertainSimulation('same uncertainty')
            projected.branch=cid;projected.score=2
            if kind=='terminal':projected.winner=pid
            if kind=='library':projected.players[2].library.append('changed')
            if kind=='hand':projected.players[2].hand.append('changed')
            return projected
        def settle(projected, *, player_id=None, own_choice_action=None, **kwargs):
            events.append(('settle',projected.branch))
            if own_choice_action is not None:own_choice_action(projected, [], player_id)
            if projected.branch=='reference':
                events.append(('baseline',None));projected.winner=baseline_winner
                return not unknown
            return kinds[ids.index(projected.branch)]!='unsettled'
        with ExitStack() as stack:
            for name,value in dict(effective_types=lambda *_:{'Instant'},
                    infer_effect_from_oracle=lambda *_ ,**__ :('destroy_permanent',{}),
                    has_keyword=lambda *_:False, _projection_copy=deepcopy,
                    simulation_checked_action=paid, _settle_announced_stack=settle,
                    RulesEngine=lambda:object()).items():stack.enter_context(patch.object(p,name,value))
            stack.enter_context(patch.object(heuristics,'evaluate_board',lambda s,pid:s.score))
            if poison_memo:stack.enter_context(patch.object(p,'_choice_free_projection',side_effect=AssertionError('native branch must bypass result memo')))
            values=[]
            with p.decision_projection_scope(state,1):
                for _ in range(repeat):
                    kw={'_native_shared_baseline':True} if native else {}
                    values.append(p.unproductive_destroy_targets(state,card,1,{},action=action,own_choice_action=policy,**kw))
        return events,values

    def test_native_baseline_once_and_every_candidate_paid_settled_with_callback(self):
        events,values=self.batch(native=True,poison_memo=True)
        self.assertEqual(events.count(('baseline',None)),1)
        for cid in ('f0','f1','f2'):
            self.assertEqual(events.count(('paid',cid)),1)
            self.assertEqual(events.count(('settle',cid)),1)
            self.assertEqual(events.count(('policy',cid)),1)
        self.assertEqual(values,[set()])

    def test_generic_callback_side_effects_stay_uncached(self):
        events,_=self.batch(repeat=2)
        self.assertEqual(events.count(('baseline',None)),6)
        self.assertEqual(events.count(('policy','reference')),6)
        self.assertEqual(sum(k=='paid' for k,v in events),6)

    def test_instrumented_public_helper_retains_generic_side_effects(self):
        calls=[]
        def custom(state,pid,action,**kwargs):
            calls.append(action['targets']['target_card_id']);return False
        with patch.object(p,'friendly_destruction_profit',side_effect=custom):
            events,values=self.batch(native=True)
        self.assertEqual(calls,['f0','f1','f2'])
        self.assertFalse(any(k=='baseline' for k,v in events))
        self.assertEqual(values,[{'f0','f1','f2'}])

    def test_reference_is_lazy_after_first_candidate_needing_comparison(self):
        events,_=self.batch(native=True,kinds=('rejected','uncertain','terminal','library','hand','unsettled','compare'))
        self.assertEqual(events.count(('baseline',None)),1)
        self.assertGreater(events.index(('baseline',None)),events.index(('settle','f6')))

    def test_no_reference_for_rejected_unknown_terminal_or_changed_zone_cases(self):
        events,_=self.batch(native=True,kinds=('rejected','uncertain','terminal','library','hand','unsettled'))
        self.assertFalse(any(k=='baseline' for k,v in events))

    def test_unknown_reference_stays_unknown_but_candidates_still_run(self):
        events,values=self.batch(native=True,unknown=True)
        self.assertEqual(events.count(('baseline',None)),1)
        self.assertEqual(sum(k=='paid' for k,v in events),3)
        self.assertEqual(values,[set()])

    def test_reference_not_shared_between_batches(self):
        events,_=self.batch(native=True,repeat=2)
        self.assertEqual(events.count(('baseline',None)),2)

    def test_known_reference_winner_uses_existing_comparison_rule(self):
        _,values=self.batch(native=True,baseline_winner=1)
        self.assertEqual(values,[{'f0','f1','f2'}])

    def test_default_off_uses_standard_public_helper(self):
        self.assertIs(signature(p.unproductive_destroy_targets).parameters['_native_shared_baseline'].default, False)
        with patch.object(p, 'friendly_destruction_profit', wraps=p.friendly_destruction_profit) as public:
            events, values = self.batch()
        self.assertEqual([call.args[2]['targets']['target_card_id'] for call in public.call_args_list],
                         ['f0', 'f1', 'f2'])
        self.assertEqual(events.count(('baseline', None)), 3)
        self.assertEqual(values, [set()])


class NativeOptIn(unittest.TestCase):
    def guard(self, owner):
        tree=ast.parse(Path(a.__file__).read_bytes())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='unproductive_destroy_targets']
        values=[k.value for n in calls for k in n.keywords if k.arg=='_native_shared_baseline']
        self.assertEqual(len(values),1)
        return eval(compile(ast.Expression(values[0]),a.__file__,'eval'),
                    dict(native_planner=a._native_planner_snapshot(owner)))

    def test_exact_native_choose_only(self):
        owner=a.AIAgent('master')
        self.assertTrue(self.guard(owner))
        owner.choose_action=lambda *_:None
        self.assertFalse(self.guard(owner))
        del owner.choose_action
        with patch.object(a.AIAgent,'choose_action',lambda *_:None):self.assertFalse(self.guard(owner))
        class Child(a.AIAgent):pass
        self.assertFalse(self.guard(Child('master')))


class CanonicalChoices(unittest.TestCase):
    def test_real_canonical_native_choices_in_both_seats(self):
        from tests.test_ai_friendly_destruction_continuations import position, native_result
        for seat in (1,2):
            state,murder,own_myr,bear,artist,enemy_myr=position(seat)
            owner=a.AIAgent('master','Aristocrats')
            legal=owner.engine.legal_moves(state,seat)
            move=next(x for x in legal if x.get('type')=='cast_spell' and x.get('card_id')==murder)
            before=pickle.dumps(state,protocol=5)
            chosen=owner._materialize_action(state,deepcopy(move),seat)
            self.assertIn(chosen['targets']['target_card_id'],{bear,artist})
            result,_=native_result(state,seat,chosen)
            self.assertEqual(result.winner,seat)
            self.assertEqual(pickle.dumps(state,protocol=5),before)


if __name__=='__main__':unittest.main(verbosity=2)
