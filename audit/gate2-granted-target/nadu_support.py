"""Scripted canonical paid unit witnesses, not a deck benchmark or injected continuation."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from card_data.hydration import hydrate_deck_cards
from game_state.state import MatchFactory, Step, Zone, pregame_actor, object_incarnation
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from ai.action_contract import complete_action

ROOT=Path(__file__).resolve().parent
FACTS=json.loads((ROOT/'nadu-facts.json').read_text())
WITNESSES=json.loads((ROOT/'witnesses.json').read_text())

class CanonicalRecords:
    def get_cached_cards_by_names(self,names):return {}
    def get_card_knowledge_by_names(self,names):
        return {n.casefold():SimpleNamespace(oracle_source='scryfall',name=FACTS[n]['name'],
             scryfall_id=FACTS[n]['id'],profiles_json=json.dumps({'card_data':FACTS[n]})) for n in names}

def snapshot(state):return serialize_match_snapshot(state)
def restored(state):return deserialize_match_snapshot(json.loads(json.dumps(snapshot(state))))
def conservation(state):
    ids=[cid for player in state.players.values() for zone in ['library','hand','battlefield','graveyard','exile']
         for cid in getattr(player,zone)]
    ids += [cid for cid,c in state.cards.items() if c.zone==Zone.STACK]
    assert len(state.cards)==120 and len(ids)==120 and len(set(ids))==120 and set(ids)==set(state.cards)
    assert Counter(c.owner for c in state.cards.values())=={1:60,2:60}

class Position:
    def __init__(self,seat,case,branch='land',nadu=True):
        self.seat,self.case,self.branch=seat,case,branch
        self.trace=[];self.milestones=[];self.actions=0
        self.key=f'{seat}-{branch}'
        self.board=hydrate_deck_cards(CanonicalRecords(),deepcopy(WITNESSES['recipe']))
        self.state=MatchFactory.from_decks(self.board,self.board,seed=WITNESSES['witnesses'][self.key]['seed'])
        assert [self.state.cards[c].name for c in self.state.players[seat].hand]==WITNESSES['witnesses'][self.key]['expected_opening']
        conservation(self.state)
        self.initial_snapshot=snapshot(self.state)
        self.ids={};self.shock_pay=None
        # No fixture state writes: all pregame, land, cast, pass and choice transitions use real engine paths.
        while self.state.pregame_pending:
            self.act(pregame_actor(self.state),{'type':'keep_hand'})
        mine=0;enemy_done=False
        while mine<3:
            self.to_main()
            actor=self.state.active_player
            if actor==seat:
                mine+=1
                lands=[cid for cid in self.state.players[seat].hand if self.state.cards[cid].name in ('Forest','Island')]
                preferred='Forest' if mine==1 else 'Island' if mine==2 else None
                land=next((cid for cid in lands if self.state.cards[cid].name==preferred),lands[0])
                self.act(seat,{'type':'play_land','card_id':land})
                if mine==1:self.ids['shuko']=self.cast_name('Shuko',seat)
                if mine==2:self.ids['elf']=self.cast_name('Elvish Mystic',seat)
                if mine==3 and nadu:self.ids['nadu']=self.cast_name('Nadu, Winged Wisdom',seat)
            elif not enemy_done:
                forest=self.find_hand('Forest',actor)
                self.act(actor,{'type':'play_land','card_id':forest})
                self.ids['enemy_elf']=self.cast_name('Elvish Mystic',actor)
                enemy_done=True
            if mine<3:self.leave_main()
        assert self.state.active_player==seat and self.state.step==Step.PRECOMBAT_MAIN
        assert self.state.cards[self.state.players[seat].library[-1]].name==WITNESSES['witnesses'][self.key]['expected_first_top']
        self.mark('actual_setup_complete')

    def mark(self,name):self.milestones.append(name)
    def act(self,actor,action):
        self.actions+=1;assert self.actions<=900,'bounded scripted action limit'
        before=snapshot(self.state)
        completed=complete_action(action)
        try:self.state=checked_action(self.state,RulesEngine(),actor,completed)
        except ActionRejected as error:
            assert snapshot(self.state)==before
            self.trace.append({'actor':actor,'action':completed,'rejected':str(error),'root_atomic':True})
            raise
        conservation(self.state)
        self.trace.append({'actor':actor,'action':completed,'turn':self.state.turn,'step':self.state.step.value,
            'stack':[{'id':s.id,'source':s.source_card_id,'effect':s.effect_key,'payload':deepcopy(s.payload)} for s in self.state.stack]})

    def tick(self):
        state=self.state
        if state.step==Step.UNTAP and not state.stack and not state.pending_mechanic_choice:
            before=state.step
            assert RulesEngine().advance_no_priority_step(state)
            self.trace.append({'engine_no_priority_transition':before.value,'to':state.step.value});return
        pending=state.pending_mechanic_choice
        actor=int(pending['player_id']) if pending else state.priority_player
        moves=RulesEngine().legal_moves(state,actor)
        if pending:
            move=deepcopy(next(m for m in moves if m['type']=='choose_mechanic'))
            if pending['kind']=='cleanup_discard':
                protect={'Nadu, Winged Wisdom','Shuko','Reanimate','Lightning Bolt','Elvish Mystic','Swamp','Mountain'}
                options=sorted(pending['options'],key=lambda cid:self.state.cards[cid].name in protect)
                move['card_ids']=options[:pending['count']]
            elif pending['kind']=='land_entry':
                if self.shock_pay is None:raise AssertionError('undeclared real land-entry choice')
                move['choice_id']='pay_two_life' if self.shock_pay else 'tapped'
            else:raise AssertionError('unhandled REAL producer choice: '+pending['kind'])
            self.act(actor,move)
        elif state.pending_trigger_order or state.pending_replacement_choice:
            # Only fully offered actions; never construct pending state or infer new IDs.
            self.act(actor,moves[0])
        else:self.act(actor,{'type':'pass_priority'})

    def settle(self):
        for _ in range(80):
            if not self.state.stack and not self.state.pending_mechanic_choice and not self.state.pending_trigger_order and not self.state.pending_replacement_choice:return
            self.tick()
        raise AssertionError('real stack failed bounded settling')

    def to_main(self):
        for _ in range(160):
            if self.state.step==Step.PRECOMBAT_MAIN and not self.state.stack and not self.state.pending_mechanic_choice:return
            self.tick()
        raise AssertionError('main phase liveness bound')

    def leave_main(self):
        oldturn=self.state.turn
        for _ in range(160):
            self.tick()
            if self.state.turn!=oldturn and self.state.step==Step.PRECOMBAT_MAIN:return
        raise AssertionError('next turn liveness bound')

    def find_hand(self,name,seat):
        return next(cid for cid in self.state.players[seat].hand if self.state.cards[cid].name==name)

    def cast_name(self,name,seat,targets=None):
        cid=self.find_hand(name,seat)
        untapped={i for i in self.state.players[seat].battlefield if not self.state.cards[i].tapped}
        self.act(seat,{'type':'cast_spell','card_id':cid,'targets':targets or {}})
        assert self.state.cards[cid].zone==Zone.STACK
        assert any(item.source_card_id==cid and item.payload.get('__announced_stack_kind')=='spell' for item in self.state.stack)
        tapped=sorted(i for i in untapped if self.state.cards[i].tapped)
        paid={'Shuko':1,'Elvish Mystic':1,'Nadu, Winged Wisdom':3,'Lightning Bolt':1,'Reanimate':1}.get(name)
        assert len(tapped)==paid,(name,tapped,paid)
        self.trace.append({'paid_cast':name,'card_id':cid,'newly_tapped_one_mana_sources':tapped,'full_raw_body':self.state.cards[cid].oracle_text})
        self.state=restored(self.state)
        self.settle();self.mark('paid_'+name)
        return cid

    def equip(self,target,expected_trigger=True):
        top=self.state.players[self.seat].library[-1]
        before_hand=set(self.state.players[self.seat].hand)
        tapped={cid for cid,c in self.state.cards.items() if c.tapped}
        self.act(self.seat,{'type':'equip','card_id':self.ids['shuko'],'target_card_id':target})
        assert tapped=={cid for cid,c in self.state.cards.items() if c.tapped},'zero equip must not pay invented mana'
        equipment=[i for i in self.state.stack if i.effect_key=='equip_attachment']
        assert len(equipment)==1
        triggers=[i for i in self.state.stack if i.id!=equipment[0].id]
        self.trace.append({'actual_equip_receipt':True,'target':target,'library_top':top,'top_name':self.state.cards[top].name,
                           'expected_granted_trigger':expected_trigger,'actual_additional_stack_items':len(triggers),
                           'target_incarnation':object_incarnation(self.state.cards[target])})
        self.state=restored(self.state)
        assert len(triggers)==int(expected_trigger),'canonical granted targeting-trigger count mismatch'
        self.mark('real_target_trigger_published' if expected_trigger else 'real_limit_suppressed_trigger')
        self.settle()
        assert self.state.cards[self.ids['shuko']].attached_to==target
        if expected_trigger:
            assert top not in self.state.players[self.seat].library
            if 'Land' in self.state.cards[top].types:assert top in self.state.players[self.seat].battlefield
            else:assert top in self.state.players[self.seat].hand and top not in before_hand
        else:assert self.state.players[self.seat].library[-1]==top
        self.mark('real_equip_and_top_conversion_resolved')
        return top

    def next_own_main(self):
        self.leave_main()
        while self.state.active_player!=self.seat:self.leave_main()

    def save(self,error=None):
        E=Path(os.environ['NADU_EVIDENCE'])
        data={'case':self.case,'seat':self.seat,'seed_key':self.key,'seed':WITNESSES['witnesses'][self.key]['seed'],
              'milestones':self.milestones,'actions':self.actions,'trace':self.trace,'error':str(error) if error else None,
              'initial_snapshot':self.initial_snapshot,'final_snapshot':snapshot(self.state),
              'no_fixture_state_injection':True,'no_fabricated_stack_or_pending':True}
        output=json.dumps(data,separators=(',',':')).encode()
        assert sum(p.stat().st_size for p in E.rglob('*') if p.is_file())+len(output)+1024**2<=16*1024**2
        (E/f'{self.case}-{self.seat}.json').write_bytes(output)
