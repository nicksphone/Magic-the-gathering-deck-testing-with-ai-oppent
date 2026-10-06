"""Actual fresh-process HTTP restore of a pending canonical second-spell trigger."""
from copy import deepcopy
import json
from pathlib import Path
import pickle
import sys
from urllib.parse import unquote,urlsplit

def run(phase,seat,root):
    import persistence.db as db
    from sqlmodel import create_engine,Session
    db.DATABASE_PATH=root/'owned.sqlite'
    db.DATABASE_URL='sqlite:///'+str(db.DATABASE_PATH)
    db.engine=create_engine(db.DATABASE_URL,connect_args={'check_same_thread':False})
    def audit(event,args):
        if event=='sqlite3.connect' and str(args[0])!=':memory:':
            value=str(args[0]);value=unquote(urlsplit(value).path) if value.startswith('file:') else value
            assert Path(value).resolve().is_relative_to(root.resolve()),value
        if event in {'socket.connect','socket.bind'}:raise AssertionError('No network/listeners')
    sys.addaudithook(audit)
    from card_data.sync import ScryfallSyncService
    def forbidden(*a,**k):raise AssertionError('No remote sync')
    ScryfallSyncService.sync_card_by_name=forbidden
    from fastapi.testclient import TestClient
    from game_state.serializers import serialize_match_snapshot
    from game_state.state import Zone
    from persistence.repository import Repository
    from tests.nth_spell_trigger_support import add
    from tests.readiness_rules_seam_support import position,seed_cache
    import main
    def wire(x):return json.loads(json.dumps(x))
    evidence={'phase':phase,'seat':seat,'pid':__import__('os').getpid()}
    with TestClient(main.app) as client:
        if phase=='seed':
            with Session(db.engine) as session:seed_cache(Repository(session))
            deck=[{'card_name':'Island','quantity':8}]
            pair={'deck_a':deck,'deck_b':deck,'sandbox':True,'controller_a':'human','controller_b':'human','seed':6214}
            response=client.post('/matches/start',json=pair,headers={'Idempotency-Key':'nth-start'})
            assert response.status_code==200,response.text
            c=main.ACTIVE_MATCHES[response.json()['id']]
            state=position(seat);state.id=c.state.id
            source=add(state,'Clarion Spirit',seat)
            spells=[add(state,'Intangible Virtue',seat,Zone.HAND) for _ in range(3)]
            c.state=state
            with Session(db.engine) as session:main._persist_active_match(Repository(session),c)
            for index,spell in enumerate(spells[:2]):
                response=client.post('/matches/'+state.id+'/action',json={'player_id':seat,'action':{'type':'cast_spell','card_id':spell.id,'targets':{}}},
                    headers={'Idempotency-Key':'nth-cast-'+str(index),'X-Match-Revision':str(c.revision)})
                assert response.status_code==200,response.text
                if index==0:
                    for _ in range(8):
                        if not c.state.stack:break
                        response=client.post('/matches/'+state.id+'/action',json={'player_id':c.state.priority_player,'action':{'type':'pass_priority'}})
                        assert response.status_code==200,response.text
            assert c.state.spells_cast_this_turn[seat]==2
            assert sum(s.source_card_id==source.id for s in c.state.stack)==1
            saved={'mid':state.id,'source':source.id,'third_spell':spells[2].id,
                   'snapshot':wire(serialize_match_snapshot(c.state)), 'config':wire(main._controller_snapshot(c))}
            (root/'expected.json').write_text(json.dumps(saved,sort_keys=True))
            evidence.update(pending_trigger_survives=True,count=2)
        else:
            saved=json.loads((root/'expected.json').read_text())
            listed=client.get('/matches')
            assert listed.status_code==200,listed.text
            assert saved['mid'] in {item['id'] for item in listed.json()}
            restored=client.get('/matches/'+saved['mid'])
            assert restored.status_code==200,restored.text
            c=main.ACTIVE_MATCHES[saved['mid']]
            assert wire(serialize_match_snapshot(c.state))==saved['snapshot']
            assert wire(main._controller_snapshot(c))==saved['config']
            before=pickle.dumps(c.state),deepcopy(main._controller_snapshot(c))
            assert client.get('/matches/'+saved['mid']+'/rules-diagnostics').status_code==200
            assert (pickle.dumps(c.state),deepcopy(main._controller_snapshot(c)))==before
            for _ in range(12):
                if not c.state.stack:break
                r=client.post('/matches/'+saved['mid']+'/action',json={'player_id':c.state.priority_player,'action':{'type':'pass_priority'}})
                assert r.status_code==200,r.text
            tokens=[c.state.cards[cid] for cid in c.state.players[seat].battlefield if c.state.cards[cid].is_token]
            assert len(tokens)==1 and tokens[0].colors==['W'] and tokens[0].keywords==['flying']
            r=client.post('/matches/'+saved['mid']+'/action',json={'player_id':seat,'action':{'type':'cast_spell','card_id':saved['third_spell'],'targets':{}}})
            assert r.status_code==200,r.text
            assert c.state.spells_cast_this_turn[seat]==3
            assert not any(s.source_card_id==saved['source'] for s in c.state.stack)
            evidence.update(restored_snapshot_config_receipts_exact=True,actual_token_count=1,third_cast_count=3)
    db.engine.dispose()
    (root/(phase+'-evidence.json')).write_text(json.dumps(evidence,sort_keys=True))

if __name__=='__main__':run(sys.argv[1],int(sys.argv[2]),Path(sys.argv[3]))
