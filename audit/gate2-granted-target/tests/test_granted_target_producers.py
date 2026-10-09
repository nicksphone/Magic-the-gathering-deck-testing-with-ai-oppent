"""Actual canonical cast/copy/target producers on explicit retained resource boards.

Not natural Factory/deck proof: fixture mana/board resources are declared, and
no-choice invokes the real copy handler rather than paying a copying card.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch
from game_state.state import Zone, assign_static_order_on_battlefield_entry
from game_state.serializers import serialize_match_snapshot as snap, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.ward import mark_stack_targets
from rules_engine.stack_engine import resolve_top_of_stack
from effects.handlers import copy_spell
from rules_engine import events
from tests.test_announced_target_reference_product import setup, raw_card, ROWS, EXTRA, cast, act
from tests.test_announced_target_reference_copy_seams import paid_copy
from tests.test_ordered_creature_modifiers import position as ordered_position
from tests.test_linked_damage_targets import position as linked_position
from tests.test_permanent_spell_context import DATA as PERMANENT_FACTS
from test_granted_target_publication import FACTS

CASES=['no_choice','scalar_keep','ordered_keep','linked_keep','modal_keep','divided_keep','trigger_target','apnap_target']


def grant(state, seat):
    source=raw_card(state, FACTS['Nadu, Winged Wisdom'], seat, Zone.BATTLEFIELD)
    assign_static_order_on_battlefield_entry(state,source.id)
    return source


def observe_before_staging(state,event,specs,original,rows):
    for spec in specs:
        if spec.get('effect_key')!='reveal_top_conditional':continue
        receipt=spec['payload']['__granted_target_receipt'];sid,revision=receipt['targeting_occurrence']
        item=next(i for i in state.stack if i.id==sid)
        assert item.payload['__granted_target_revision']==revision
        capture=item.payload['__granted_target_published_capture']
        assert capture['status']=='captured'
        frozen=next(r for r in capture['receipts'] if r['recipient_ref']==receipt['recipient_ref'])
        assert receipt['recipient_source_lki']==frozen['recipient_source_lki']
        assert receipt is not frozen and receipt['recipient_source_lki'] is not frozen['recipient_source_lki']
        key=lambda r:(r['card_id'],r['incarnation'],r['zone_change_sequence'])
        prefix='granted-target:'+json.dumps([state.turn,[key(receipt['recipient_ref']),key(receipt['grant_source_ref']),receipt['clause_instance']]],separators=(',',':'))
        assert any(k.startswith(prefix+':') for k in state.trigger_once_seen_this_turn)
        # Staged waves traverse _push_triggers twice; each traversal must see committed slots.
        existing=next((r for r in rows if r['occurrence']==receipt['targeting_occurrence']
                       and r['recipient']==receipt['recipient_ref']),None)
        if existing:
            existing['callback_deliveries']+=1
        else:
            rows.append({'occurrence':deepcopy(receipt['targeting_occurrence']),'recipient':deepcopy(receipt['recipient_ref']),
                         'pre_lki':deepcopy(receipt['recipient_source_lki']),'quota_before_callback':True,'callback_deliveries':1})
    return original(state,event,specs)


@pytest.mark.parametrize('seat',[1,2])
@pytest.mark.parametrize('case',CASES)
def test_actual_final_producer_publishes_frozen_receipts_once(case,seat):
    rows=[]; original=events._push_triggers
    with patch.object(events,'_push_triggers',lambda s,e,t:observe_before_staging(s,e,t,original,rows)):
        if case in {'trigger_target','apnap_target'}:
            state,_=setup(seat)
            target=raw_card(state,EXTRA['ornithopter'],3-seat,Zone.BATTLEFIELD)
            grant(state,3-seat)
            state.trigger_order_choice_required=True
            state.trigger_order_choice_players={1,2}
            if case=='apnap_target':
                raw_card(state,PERMANENT_FACTS['Soul Warden'],seat,Zone.BATTLEFIELD)
                raw_card(state,PERMANENT_FACTS['Soul Warden'],3-seat,Zone.BATTLEFIELD)
            sage=raw_card(state,EXTRA['reclamation-sage'],seat,Zone.HAND)
            state=cast(state,seat,sage.id,{})
            assert resolve_top_of_stack(state)
            for _ in range(8):
                pending=state.pending_trigger_order
                assert pending is not None
                owner=int(pending.get('player_id',seat))
                moves=RulesEngine().legal_moves(state,owner)
                if not moves:
                    owner=3-owner;moves=RulesEngine().legal_moves(state,owner)
                target_move=next((m for m in moves if m['type']=='choose_trigger_target' and m.get('target_card_id')==target.id),None)
                if target_move:
                    state=deserialize_match_snapshot(snap(state))
                    state=checked_action(state,RulesEngine(),owner,target_move)
                    break
                order=next(m for m in moves if m['type']=='choose_trigger_order')
                state=checked_action(state,RulesEngine(),owner,order)
            else:raise AssertionError('actual target offer not reached')
            assert len(rows)==1 and rows[0]['recipient']['card_id']==target.id
            assert len([i for i in state.stack if i.effect_key=='reveal_top_conditional'])==1
            item=next(i for i in state.stack if i.id==rows[0]['occurrence'][0])
        else:
            if case=='ordered_keep':
                state,spell,first,second=ordered_position(seat)
                state.players[seat].mana_pool['U']+=2
                targets={'target_card_ids':[first,second]}
            elif case=='linked_keep':
                state,card,first,_,targets=linked_position(seat)
                spell=card.id;state.players[seat].mana_pool['U']=2
            else:
                state,first=setup(seat)
                raw=EXTRA['kolaghans-command'] if case=='modal_keep' else EXTRA['pyrotechnics'] if case=='divided_keep' else ROWS['Lightning Bolt']
                card=raw_card(state,raw,seat,Zone.HAND);spell=card.id
                if case=='modal_keep':
                    first=raw_card(state,EXTRA['ornithopter'],3-seat,Zone.BATTLEFIELD).id
                    targets={'mode_texts':['Destroy target artifact',"Kolaghan's Command deals 2 damage to any target"],'target_card_id':first}
                elif case=='divided_keep':targets={'target_distribution':{first:4}}
                else:targets={'target_card_id':first}
            grant(state,3-seat)
            state=cast(state,seat,spell,targets)
            original_id=next(i.id for i in state.stack if i.source_card_id==spell)
            first_rows=deepcopy(rows)
            assert first_rows
            original_item=next(i for i in state.stack if i.id==original_id)
            expected_receipts=deepcopy(original_item.payload['__granted_target_published_capture']['receipts'])
            expected_recipients={first,second} if case=='ordered_keep' else {
                first.id if case=='linked_keep' else first}
            assert len(expected_receipts)==len(expected_recipients)
            assert {r['recipient_ref']['card_id'] for r in expected_receipts}==expected_recipients
            def quota_prefix(receipt):
                ref=lambda r:[r['card_id'],r['incarnation'],r['zone_change_sequence']]
                return 'granted-target:'+json.dumps([state.turn,[ref(receipt['recipient_ref']),
                    ref(receipt['grant_source_ref']),receipt['clause_instance']]],separators=(',',':'))
            prefixes={quota_prefix(r) for r in expected_receipts}
            assert len(prefixes)==len(expected_receipts)
            quota_before=set(state.trigger_once_seen_this_turn)
            assert all(r['trigger_limit']==2 for r in expected_receipts)
            assert all({k for k in quota_before if k.startswith(prefix+':')}=={prefix+':0'}
                       for prefix in prefixes)
            if case=='no_choice':
                copy_spell(state,seat,{'target_stack_id':original_id,'may_choose_new_targets':False})
                copied=next(i for i in state.stack if i.payload.get('__copied_from_stack_id')==original_id)
                assert state.pending_mechanic_choice is None
                state=checked_action(state,RulesEngine(),state.priority_player,{'type':'pass_priority'})
                copied_id=copied.id
            else:
                state,copied_id=paid_copy(state,seat,original_id)
                assert state.pending_mechanic_choice['kind']=='copy_target'
                assert not [r for r in rows if r['occurrence'][0]==copied_id]
                for _ in range(8):
                    pending=state.pending_mechanic_choice
                    if not pending:break
                    assert pending['stack_id']==copied_id and 'keep' in pending['options']
                    state=deserialize_match_snapshot(snap(state))
                    state=checked_action(state,RulesEngine(),pending['player_id'],{'type':'choose_mechanic','card_ids':['keep']})
                else:raise AssertionError('final actual copy choice did not close')
                assert state.pending_mechanic_choice is None
            item=next(i for i in state.stack if i.id==copied_id)
            own=[r for r in rows if r['occurrence'][0]==copied_id]
            assert own and all(r['occurrence'][0]!=original_id for r in own)
            assert {r['recipient']['card_id'] for r in own}=={r['recipient']['card_id'] for r in first_rows}
            assert item.payload['__granted_target_revision']==0
            # Count real stack objects, not deduplicated staging callbacks.
            occurrence=[copied_id,0]
            actual=[i for i in state.stack if i.effect_key=='reveal_top_conditional'
                    and i.payload['__granted_target_receipt']['targeting_occurrence']==occurrence]
            assert len(actual)==len(expected_receipts)
            expected_bound=[{**r,'targeting_occurrence':occurrence} for r in expected_receipts]
            assert sorted((i.payload['__granted_target_receipt'] for i in actual),
                          key=lambda r:json.dumps(r,sort_keys=True))==sorted(expected_bound,
                          key=lambda r:json.dumps(r,sort_keys=True))
            assert all(i.source_card_id==i.payload['__granted_target_receipt']['recipient_ref']['card_id']
                       and i.controller==i.payload['__granted_target_receipt']['trigger_controller']
                       for i in actual)
            quota_after=set(state.trigger_once_seen_this_turn)
            expected_delta={prefix+':1' for prefix in prefixes}
            assert quota_after-quota_before==expected_delta
            assert quota_before-quota_after==set()
            assert all({k for k in quota_after if k.startswith(prefix+':')}
                       =={prefix+':0',prefix+':1'} for prefix in prefixes)
            trace={'case':case,'seat':seat,'copied_occurrence':occurrence,
                   'expected_recipients':sorted(expected_recipients),
                   'actual_stack_ids':[i.id for i in actual],'actual_receipts':expected_bound,
                   'quota_before':sorted(quota_before),'quota_after':sorted(quota_after),
                   'exact_delta':sorted(expected_delta),'before_repeat_mark_and_final_restore':True}
            (Path(os.environ['NADU_EVIDENCE'])/f'copy-stack-quota-{case}-seat{seat}.json').write_text(
                json.dumps(trace,indent=2,sort_keys=True)+'\n')
        before=snap(state); before_rows=deepcopy(rows)
        mark_stack_targets(state,item)
        assert snap(state)==before and rows==before_rows
        restored=deserialize_match_snapshot(snap(state))
        restored_item=next(i for i in restored.stack if i.id==item.id)
        before=snap(restored)
        mark_stack_targets(restored,restored_item)
        assert snap(restored)==before and rows==before_rows
