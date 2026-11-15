# SPDX-License-Identifier: GPL-3.0-or-later
# LABELLED SYNTHETIC protocol receipts, never a game/native-event/winner fixture.
import copy
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from structural_picker import pick, tokens_for

CARDS=[{'card_id':i,'owner_id':0,'face':{'name':'SYNTHETIC ENTITY '+str(i)}}for i in (101,102,103,104)]

def frame(chosen=(),minimum=2,maximum=2,ok=False,revision=10):
    choices=[{'display':copy.deepcopy(c),'token':'SYNTHETIC-'+str(revision)+'-'+str(i)}for i,c in enumerate(CARDS)]
    if ok:choices.append({'display':'button_ok','token':'SYNTHETIC-ENABLED-OK-'+str(revision)})
    selection={'min':minimum,'max':maximum,'chosen':[copy.deepcopy(CARDS[i])for i in chosen],'input':'InputSelectEntitiesFromList','generation':5,'priority_epoch':7,'revision':revision,'actor':0}
    info={'selection':selection,'ok_label':'SYNTHETIC OK','cancel_label':'SYNTHETIC CANCEL','prompt':'SYNTHETIC; MUST NOT PARSE THIS'}
    q={'kind':'input:InputSelectEntitiesFromList','actor_id':0,'min':1,'max':1,'request_id':'SYNTHETIC-REQUEST-'+str(revision),'choices':choices}
    offer={'kind':q['kind'],'actor':0,'min':1,'max':1,'choices':[c['display']for c in choices],'info':copy.deepcopy(info),'turn':1,'phase':'SYNTHETIC'}
    return {'event':'choice','question':q,'info':info,'state':{'actor_id':0,'turn':1,'phase':'SYNTHETIC','players':[{'player_id':0,'zones':{'Hand':{'visible_cards':[]}}}]},'replay_offer':offer}

class SelectionProgress(unittest.TestCase):
    def test_actual_two_of_four_progress_does_not_toggle_first_card(self):
        a=frame();self.assertEqual(pick(a),[a['question']['choices'][0]['token']])
        b=frame(chosen=(0,),revision=11)
        self.assertEqual(pick(b),[b['question']['choices'][1]['token']], 'Second native click must choose B, not toggle already selected A')
        # Native max2 auto-completes after B; no invented third OK or game result.
    def test_minimum_met_uses_only_actually_offered_ok(self):
        f=frame(chosen=(0,1),maximum=4,ok=True)
        self.assertEqual(pick(f),[f['question']['choices'][-1]['token']])
    def test_source_proven_native_ok_overrides_numeric_minimum(self):
        # LABELLED SOURCE-PROVEN protocol case, not a staged native game:
        # chooseCardsToDiscardUnlessType overrides hasEnoughTargets at one card.
        f=frame(chosen=(0,),minimum=3,maximum=3,ok=True)
        self.assertEqual(pick(f),[f['question']['choices'][-1]['token']])
    def test_native_ok_never_bypasses_malformed_current_receipt(self):
        f=frame(chosen=(0,),minimum=3,maximum=3,ok=True)
        f['info']['selection']['chosen']=[{'hidden':True}]
        with self.assertRaises(ValueError):pick(f)
    def test_no_guessed_ok_or_extra_card_after_minimum(self):
        with self.assertRaises(ValueError):pick(frame(chosen=(0,1),maximum=4,ok=False))
    def test_missing_native_metadata_rejected(self):
        f=frame();del f['info']['selection']
        with self.assertRaises(ValueError):pick(f)
    def test_hidden_entity_descriptor_fails_closed(self):
        f=frame();f['question']['choices'][0]['display']={'hidden':True}
        with self.assertRaises(ValueError):pick(f)
    def test_hidden_chosen_descriptor_fails_closed(self):
        f=frame();f['info']['selection']['chosen']=[{'hidden':True}]
        with self.assertRaises(ValueError):pick(f)
    def test_unoffered_chosen_entity_rejected(self):
        f=frame();f['info']['selection']['chosen']=[{'card_id':999}]
        with self.assertRaises(ValueError):pick(f)
    def test_changed_chosen_description_rejected(self):
        f=frame(chosen=(0,));f['info']['selection']['chosen'][0]['owner_id']=1
        with self.assertRaises(ValueError):pick(f)
    def test_duplicate_chosen_rejected(self):
        f=frame(chosen=(0,0))
        with self.assertRaises(ValueError):pick(f)
    def test_ambiguous_offered_identity_rejected(self):
        f=frame();f['question']['choices'][1]['display']=copy.deepcopy(CARDS[0])
        with self.assertRaises(ValueError):pick(f)
    def test_foreign_actor_receipt_rejected(self):
        f=frame();f['info']['selection']['actor']=1
        with self.assertRaises(ValueError):pick(f)
    def test_wrong_current_input_receipt_rejected(self):
        f=frame();f['info']['selection']['input']='InputPassPriority'
        with self.assertRaises(ValueError):pick(f)
    def test_invalid_generation_receipt_rejected(self):
        f=frame();f['info']['selection']['generation']=-1
        with self.assertRaises(ValueError):pick(f)
    def test_outer_bounds_remain_one_click(self):
        f=frame();f['question']['min']=f['question']['max']=2
        with self.assertRaises(ValueError):pick(f)
    def test_native_bounds_invalid_rejected(self):
        f=frame();f['info']['selection']['max']=1
        with self.assertRaises(ValueError):pick(f)
    def test_stale_selection_offer_rejected_by_actual_driver_matcher(self):
        old=frame();new=frame(chosen=(0,),revision=11)
        ticket={'offer':old['replay_offer'],'selected':[CARDS[0]]}
        with self.assertRaisesRegex(ValueError,'OFFER_MISMATCH'):tokens_for(new,ticket)
    def test_current_offer_uses_only_current_one_use_token(self):
        old=frame();new=frame(chosen=(0,),revision=11)
        token=pick(new)[0]
        self.assertIn(token,[v['token']for v in new['question']['choices']])
        self.assertNotIn(token,[v['token']for v in old['question']['choices']])
    def test_non_selection_existing_button_behavior_unchanged(self):
        f=frame(ok=True);f['question']['kind']='input:InputPassPriority';f['info'].pop('selection')
        self.assertEqual(pick(f),[f['question']['choices'][-1]['token']])

if __name__=='__main__':unittest.main()
