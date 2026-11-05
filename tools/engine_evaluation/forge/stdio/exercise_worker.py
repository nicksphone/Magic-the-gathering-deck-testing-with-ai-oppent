# SPDX-License-Identifier: GPL-3.0-or-later
# Original scripted process client for the Forge Team/Card-Forge native engine.
# https://github.com/Card-Forge/forge, revision 61e9442c433711a82258daca3236f936a1d6f70e.
# Retain upstream notices and the accompanying Forge GPL license.
# This is a bounded integration-test client, NOT an expert gameplay policy.
import collections,json,os,pathlib,queue,subprocess,sys,threading,time,uuid

def drain_frames(frames,first):
    batch=[first]
    while not frames.empty():
        more=frames.get_nowait()
        if more is None:
            frames.put(None)
            break
        batch.append(more)
    return batch

if sys.argv[1:]==['--self-test']:
    frames=queue.Queue(); frames.put({'event':'aborted'}); frames.put(None)
    assert drain_frames(frames,{'event':'view'})==[{'event':'view'},{'event':'aborted'}]
    assert not frames.empty(), 'EOF must survive batched frames'
    assert frames.get_nowait() is None
    frames.put({'event':'choice'})
    assert drain_frames(frames,{'event':'view'})==[{'event':'view'},{'event':'choice'}]
    assert frames.empty()
    print('Batched frame/EOF checks passed')
    raise SystemExit(0)

command_path,case=map(pathlib.Path,sys.argv[1:3])
disconnect=len(sys.argv)==4 and sys.argv[3]=='disconnect'
# Operator-owned argv only. Never accept a browser's command or filesystem path.
command=json.loads(command_path.read_text())
assert isinstance(command,list) and command and all(isinstance(x,str) for x in command)
(case/'command.json').write_text(json.dumps(command,indent=2)+'\n')
frames=queue.Queue(); pending_error=[]
err=(case/'native.stderr.private.log').open('w')
p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
wire=(case/'wire.private.jsonl').open('w'); decisions=(case/'client.private.jsonl').open('w')
def read():
    try:
        for line in p.stdout:
            wire.write(line); wire.flush()
            frames.put(json.loads(line))
    except BaseException as e: pending_error.append(str(e))
    finally: frames.put(None)
t=threading.Thread(target=read,daemon=True); t.start()
counts=collections.Counter(); completed=None; injected=False; answered=0; max_turn=0; errors=[]; answered_ids=set(); checked_views=0
disconnect_requested=False
kinds=collections.Counter()
tried=collections.defaultdict(set)

def send(value):
    p.stdin.write(json.dumps(value)+'\n'); p.stdin.flush()
    decisions.write(json.dumps(value)+'\n'); decisions.flush()

def pick(frame):
    q=frame['question']; options=q['choices']; kind=q['kind']; actor=q['actor_id']; info=frame['info']
    hand={c['card_id'] for p in frame['state']['players'] if p['player_id']==actor for c in p['zones']['Hand']['visible_cards']}
    def find(test): return next((x for x in options if test(x['display'])),None)
    ok=find(lambda d:d=='button_ok'); cancel=find(lambda d:d=='button_cancel')
    if kind.startswith('input:'):
        subtype=kind[6:]
        if subtype=='InputAttack':
            attacker=find(lambda x:isinstance(x,dict) and 'card_id' in x)
            if attacker and cancel and 'alpha' in info.get('cancel_label','').lower(): return [cancel['token']]
            return [ok['token']] if ok else [options[0]['token']]
        if subtype=='InputPassPriority':
            window=(frame['state']['turn'],frame['state']['phase'])
            def available(x): return isinstance(x,dict) and x.get('card_id') in hand and x['card_id'] not in tried[window]
            card=find(lambda x:available(x) and 'Land' in x.get('face',{}).get('type',''))
            if card is None: card=find(lambda x:available(x) and 'Creature' in x.get('face',{}).get('type',''))
            if card is None: card=find(available)
            if card:
                tried[window].add(card['display']['card_id'])
                return [card['token']]
        if subtype.startswith('InputPayMana'):
            if ok: return [ok['token']]
            if cancel: return [cancel['token']]
        if subtype=='InputSelectTargets':
            target=find(lambda x:isinstance(x,dict) and 'player_id' in x and x['player_id']!=actor)
            if target is None: target=find(lambda x:isinstance(x,dict) and 'card_id' in x and x.get('controller_id')!=actor)
            if target: return [target['token']]
        if ok: return [ok['token']]
        card=find(lambda x:isinstance(x,dict) and 'card_id' in x)
        return [(card or cancel or options[0])['token']]
    n=q['min']
    if kind=='getChoices': n=max(n,min(q['max'],1))
    if kind=='chooseSingleEntityForEffect': n=1 if options else 0
    return [x['token'] for x in options[:n]]

try:
    deadline=time.monotonic()+260
    while time.monotonic()<deadline:
        f=frames.get(timeout=30)
        if f is None: break
        # New native selection messages can supersede older queued button frames.
        time.sleep(.003)
        batch=drain_frames(frames,f)
        candidate=None
        for f in batch:
            counts[f['event']]+=1
            if f['event']=='choice': kinds[f['question']['kind']]+=1
            if f['event']=='game_complete': completed=f
            if f['event']=='error': errors.append(f)
            if 'state' in f:
                state=f['state']; actor=state['actor_id']; checked_views+=1; max_turn=max(max_turn,state['turn'])
                for player in state['players']:
                    # This matchup has real Goblin Guide reveals; permitted top cards
                    # are allowed, but never a whole unknown library or opposing hand.
                    library=player['zones']['Library']
                    assert len(library['visible_cards']) <= 1
                    if player['player_id']!=actor: assert not player['zones']['Hand']['visible_cards']
            if f['event']=='choice': candidate=f
        if completed or errors: break
        if candidate is None: continue
        if disconnect_requested: continue
        if disconnect:
            p.stdin.close(); disconnect_requested=True
            continue
        q=candidate['question']; rid=q['request_id']
        if rid in answered_ids: continue
        if not injected:
            send({'request_id':rid,'tokens':[],'actor_id':q['actor_id']})
            send({'request_id':rid,'tokens':[str(uuid.uuid4())]})
            injected=True
        value={'request_id':rid,'tokens':pick(candidate)}
        send(value); answered_ids.add(rid); answered+=1
        if answered==1: send(value)
    if completed is None and p.poll() is None: p.stdin.close()
    p.wait(timeout=20); t.join(timeout=2)
    result={'pid':p.pid,'exit':p.returncode,'counts':dict(counts),'kinds':dict(kinds),'answers':answered,'views_checked':checked_views,'max_turn':max_turn,'game_complete':completed,'errors':errors,'reader_errors':pending_error,'scripted_test_client_not_expert':True,'expected_disconnect':disconnect}
    (case/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    valid=(p.returncode==2 and counts['aborted']==1 and completed is None) if disconnect else (p.returncode==0 and completed is not None)
    if not valid or errors or pending_error: raise SystemExit(1)
finally:
    if p.poll() is None:
        p.terminate()
        try:p.wait(timeout=15)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    wire.close(); decisions.close(); err.close()
