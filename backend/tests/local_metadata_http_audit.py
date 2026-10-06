"""Real offline production HTTP metadata contract; sequential fresh processes."""
from collections import Counter
from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.parse import quote, urlencode

backend = Path(__file__).resolve().parents[1]
assert backend.parent.name.startswith('mtg-catalog-')
evidence = Path(os.environ['CATALOG_HTTP_EVIDENCE']); evidence.mkdir(parents=True, exist_ok=True)
database = backend / 'mtg_lab.db'
assert not database.exists() and not (backend / 'card_data/image_cache').exists()
sys.path.insert(0, str(backend))
source_before = {str(p.relative_to(backend.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in backend.parent.rglob('*') if p.is_file() and 'graphify-out' not in p.parts}
(evidence / 'source-before.json').write_text(json.dumps(source_before, indent=2, sort_keys=True))
requests = []
processes = []
ports = set()
def guard(event, args):
    if event == 'socket.getaddrinfo': assert args[0] in ('127.0.0.1', '::1', None)
    if event == 'socket.connect': assert args[1][0] == '127.0.0.1' and args[1][1] in ports
    if event == 'socket.bind': assert args[1] == ('127.0.0.1', 0)
sys.addaudithook(guard)

def request(port, method, path, data=None, status=200):
    assert len(requests) < 60, 'Predeclared HTTP request cap'
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
    try:
        connection.request(method, path, json.dumps(data) if data is not None else None,
                           headers={'Content-Type': 'application/json'})
        response = connection.getresponse();body = response.read()
        requests.append({'method': method, 'path': path, 'status': response.status})
        assert response.status == status, (path, response.status, body)
        return json.loads(body)
    finally: connection.close()

def start(label):
    listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(128)
    port = listener.getsockname()[1]; assert port not in (9999, 5173); ports.add(port)
    log = (evidence / (label + '-server.log')).open('w')
    process = subprocess.Popen([sys.executable, str(backend / 'tests/local_metadata_http_server.py'),
                                str(listener.fileno()), str(evidence / (label + '-network.json'))],
             cwd=backend, env={**os.environ, 'PYTHONPATH': str(backend), 'PYTHONDONTWRITEBYTECODE': '1'},
             pass_fds=(listener.fileno(),), stdout=log, stderr=subprocess.STDOUT)
    listener.close();processes.append((process, log, port, label))
    for _ in range(25):
        assert process.poll() is None
        try:
            if request(port, 'GET', '/health')['ok']: return process, port
        except (ConnectionError, OSError): time.sleep(.2)
    raise AssertionError('Bounded server startup failed')

def stop(process):
    process.send_signal(signal.SIGTERM);process.wait(timeout=20)
    assert process.returncode == 0

def sql():
    with sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True) as connection:
        return list(connection.iterdump())

def completeness(port, names):
    return request(port, 'GET', '/cards/completeness?' + urlencode([('names', n) for n in names]))

def start_match(port, a, b, status=200):
    return request(port, 'POST', '/matches/start', {'deck_a': a, 'deck_b': b,
        'controller_a': 'human', 'controller_b': 'human', 'mode': 'human_vs_human', 'seed': 8128}, status)

result = {'baseline_commit':'fc225406d56c1a2f177ccfa8fb0b6008448772f2','families':{},'cases':[]}
try:
    process, port = start('cold')
    assert request(port,'GET','/cards') == []
    initial = request(port,'GET','/decks')
    for name, style, expected_curve, expected_colors in [
        ('Burn','Burn',{'lands':24,'1':16,'2':16,'3':4},{'W':4,'U':0,'B':0,'R':36,'G':0}),
        ('Dimir Control','Control',{'lands':28,'1':8,'2':15,'4':7,'5+':2},{'W':0,'U':18,'B':18,'R':0,'G':0})]:
        text=request(port,'GET','/decks/builtin/'+quote(name))['deck_text']
        imported=request(port,'POST','/decks/import',{'name':'Read-only metadata '+name,'source':'user:metadata-audit','deck_text':text})
        assert not imported['errors'] and imported['archetype_guess']==style
        assert all(v==expected_curve.get(k,0) for k,v in imported['mana_curve'].items())
        assert imported['color_profile']==expected_colors
        assert all(c['card_metadata'] and c['card_metadata']['match_ready'] and
                   c['card_metadata']['card_data_sources']==['offline_seed'] and
                   'id' not in c['card_metadata'] for c in imported['resolved_mainboard_cards'])
        assert request(port,'GET','/cards')==[]
        before=sql()
        report=completeness(port,[c['card_name'] for c in imported['mainboard']])
        assert all(c['match_ready'] and c['oracle_source']=='fallback' and not c['cached'] for c in report['cards'])
        assert report['complete']==0 and sql()==before
        match=start_match(port,imported['mainboard'],imported['mainboard'])
        before=sql()
        assert request(port,'GET','/matches/'+match['id'])==match and sql()==before
        result['families'][name]={'import':imported,'completeness':report,'match':match}
    assert {d['id']:d for d in request(port,'GET','/decks') if d['id'] in {d['id'] for d in initial}}=={d['id']:d for d in initial}
    board=[{'card_name':'Island','quantity':59},{'card_name':'Time Warp','quantity':1}]
    before=sql()
    assert start_match(port,board,board,422)['detail']['code']=='card_data_unavailable'
    assert sql()==before
    stop(process)
    process,port=start('restart')
    before=sql()
    for family in result['families'].values():
        assert request(port,'GET','/matches/'+family['match']['id'])==family['match']
    assert sql()==before
    stop(process)
    from sqlmodel import Session
    from persistence.db import engine
    from persistence.repository import Repository
    fixture=backend/'tests/fixtures/queued_sequence/canonical.json'
    pin=json.loads(fixture.with_name('provenance.json').read_text())
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==pin['canonical_sha256']
    raw=json.loads(fixture.read_text())['Time Warp']
    profile={'schema_version':1,'card_data':raw,'rulings_verified':False,'rulings':[]}
    with Session(engine) as session:
        repo=Repository(session)
        repo.upsert_card_knowledge({'name':raw['name'],'scryfall_id':raw['id'],'oracle_source':'manual','profiles':profile})
        repo.upsert_card({'name':raw['name'],'scryfall_id':raw['id'],'type_line':raw['type_line'],
            'mana_cost':raw['mana_cost'],'oracle_text':'','colors':','.join(raw['colors'])})
    process,port=start('partial')
    before=sql()
    assert not completeness(port,['Time Warp'])['cards'][0]['match_ready']
    assert start_match(port,board,board,422)['detail']['code']=='card_data_unavailable'
    assert sql()==before
    imported=request(port,'POST','/decks/import',{'name':'Partial metadata','source':'user:metadata-audit','deck_text':'59 Island\n1 Time Warp'})
    meta=imported['resolved_mainboard_cards'][1]['card_metadata']
    assert meta['card_data_sources']==['cache'] and not meta['match_ready'] and isinstance(meta['id'],int)
    assert imported['classification_status']=='unknown'
    assert request(port,'GET','/cards')[0]['oracle_text']==''
    stop(process)
    with Session(engine) as session:
        repo=Repository(session)
        # Synthetic setup only, while the server is stopped: remove our partial cache row.
        row=repo.get_cached_card_by_name('Time Warp');session.delete(row);session.commit()
        repo.upsert_card_knowledge({'name':raw['name'],'scryfall_id':raw['id'],'oracle_source':'scryfall','profiles':profile})
    process,port=start('knowledge')
    before=sql()
    knowledge=completeness(port,['Time Warp'])['cards'][0]
    assert knowledge['match_ready'] and knowledge['oracle_source']=='knowledge' and not knowledge['cached']
    assert sql()==before
    for index in range(2):
        imported=request(port,'POST','/decks/import',{'name':'Canonical metadata','source':'user:metadata-audit','deck_text':'59 Island\n1 Time Warp'})
        meta=imported['resolved_mainboard_cards'][1]['card_metadata']
        assert meta['match_ready'] and meta['card_data_sources']==['local_knowledge'] and 'id' not in meta
        assert meta['scryfall_id']==raw['id'] and meta['oracle_text']==raw['oracle_text']
        assert imported['mana_curve']['5+']==1 and imported['mana_curve']['lands']==59
        assert imported['color_profile']=={'W':0,'U':1,'B':0,'R':0,'G':0}
        assert request(port,'GET','/cards')==[]
    match=start_match(port,board,board)
    stop(process)
    process,port=start('knowledge-restart')
    before=sql()
    assert request(port,'GET','/matches/'+match['id'])==match and sql()==before
    assert request(port,'GET','/cards')==[]
    stop(process)
    result.update(ok=True, typed_absent_partial_rejections=True, repeated_knowledge_import_no_cache_rows=True)
finally:
    for process,log,port,label in processes:
        if process.poll() is None: stop(process)
        log.close()
        ledger=json.loads((evidence/(label+'-network.json')).read_text())
        assert ledger['blocked_external_attempts']==[] and ledger['allowed_loopback_outgoing']==[]
    assert all(hashlib.sha256((backend.parent/p).read_bytes()).hexdigest()==h for p,h in source_before.items())
    result.update(requests=requests,processes=[{'pid':p.pid,'port':port,'label':label,'returncode':p.returncode}
                  for p,_,port,label in processes],source_unchanged=True)
    (evidence/'RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True))
print(json.dumps({'ok':result['ok'],'requests':len(requests),'processes':len(processes)}))
