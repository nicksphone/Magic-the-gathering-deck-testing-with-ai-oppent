# SPDX-License-Identifier: GPL-3.0-or-later
# LABELLED SYNTHETIC protocol rows, not native events/game/winner fixtures.
import copy,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from structural_picker import pick,tokens_for
SOURCE={'card_id':9,'face':{'name':'SYNTHETIC PUBLIC SOURCE'}}
STACK=[{'stack_id':501,'source':copy.deepcopy(SOURCE)},{'stack_id':502,'source':copy.deepcopy(SOURCE)}]
def frame(chosen=(),ok=False,rev=1):
 opts=[{'display':copy.deepcopy(x),'token':'SYNTHETIC-'+str(rev)+'-'+str(i)}for i,x in enumerate(STACK)]
 if ok:opts.append({'display':'button_ok','token':'SYNTHETIC-OK-'+str(rev)})
 info={'stack_selection':{'chosen':[copy.deepcopy(STACK[i])for i in chosen],'input':'InputSelectStackItems','generation':7,'priority_epoch':9,'revision':rev,'actor':0}}
 q={'kind':'input:InputSelectStackItems','actor_id':0,'min':1,'max':1,'request_id':'SYNTHETIC-'+str(rev),'choices':opts}
 return {'question':q,'info':info,'state':{'actor_id':0,'players':[{'player_id':0,'zones':{'Hand':{'visible_cards':[]}}}]},'replay_offer':{'kind':q['kind'],'actor':0,'min':1,'max':1,'choices':[x['display']for x in opts],'info':copy.deepcopy(info)}}
class StackProgress(unittest.TestCase):
 def test_same_physical_source_distinct_stack_instances_progress(self):
  a=frame();b=frame((0,),rev=2)
  self.assertEqual(pick(a),[a['question']['choices'][0]['token']])
  self.assertEqual(pick(b),[b['question']['choices'][1]['token']])
 def test_native_ok_authoritative_without_invented_bounds(self):
  f=frame((0,),ok=True);self.assertEqual(pick(f),[f['question']['choices'][-1]['token']])
 def test_source_hidden_descriptor_remains_selectable_by_stack_identity(self):
  f=frame();f['question']['choices'][0]['display']['source']={'hidden':True}
  self.assertEqual(pick(f),[f['question']['choices'][0]['token']])
 def test_missing_current_stack_context_rejected(self):
  f=frame();del f['info']['stack_selection']
  with self.assertRaises(ValueError):pick(f)
 def test_same_id_alias_descriptors_rejected(self):
  f=frame();f['question']['choices'][1]['display']=copy.deepcopy(STACK[0])
  with self.assertRaises(ValueError):pick(f)
 def test_foreign_chosen_stack_identity_rejected(self):
  f=frame();f['info']['stack_selection']['chosen']=[{'stack_id':999,'source':SOURCE}]
  with self.assertRaises(ValueError):pick(f)
 def test_wrong_current_input_rejected(self):
  f=frame();f['info']['stack_selection']['input']='InputSelectTargets'
  with self.assertRaises(ValueError):pick(f)
 def test_no_guessed_commit_or_source_card(self):
  f=frame((0,1))
  with self.assertRaises(ValueError):pick(f)
 def test_stale_offer_cannot_match_current_tokens(self):
  a=frame();b=frame((0,),rev=2)
  with self.assertRaisesRegex(ValueError,'OFFER_MISMATCH'):tokens_for(b,{'offer':a['replay_offer'],'selected':[STACK[0]]})
if __name__=='__main__':unittest.main()
