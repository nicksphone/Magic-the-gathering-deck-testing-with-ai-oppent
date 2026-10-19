import os,sys,json,hashlib
from pathlib import Path
root=Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve()
assert not root.is_symlink() and (root/'.private').read_text()==str(root)
assert not (root/'.git').exists() and not (root/'backend/mtg_lab.db').exists()
import sqlite3,sqlite3.dbapi2,socket,_sqlite3,_socket
checks=[]
def deny(*args,**kwargs):raise PermissionError('SQLite/network forbidden in pure self-return qualification')
def audit(event,args):
 if event in {'sqlite3.connect','socket.connect','socket.__new__'}:deny()
sys.addaudithook(audit)
sqlite3.connect=deny;sqlite3.dbapi2.connect=deny
for name,call in [('sqlite3.connect',lambda:sqlite3.connect(':memory:')),('sqlite3.dbapi2.connect',lambda:sqlite3.dbapi2.connect(':memory:')),('_sqlite3.connect',lambda:_sqlite3.connect(':memory:')),('_socket.socket',_socket.socket),('socket.socket',socket.socket)]:
 try:call()
 except PermissionError:checks.append(name)
 else:raise AssertionError('Guard failed '+name)
sys.path.insert(0,str(root/'backend'))
receipt=Path(os.environ['MTG_GY_GATE_RUNTIME'])
import pytest
class Proof:
 def pytest_sessionfinish(self,session,exitstatus):
  modules={}
  for name,mod in sys.modules.items():
   if not name.startswith('test_') and name.split('.')[0] not in {'game_state','rules_engine','effects','ai','tests','knowledge','persistence','card_data'}:continue
   filename=getattr(mod,'__file__',None)
   if not filename:continue
   p=Path(filename).resolve();assert (p.is_relative_to(root/'backend') or p.is_relative_to(Path(__file__).parent/'tests')),(name,str(p))
   modules[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  assert not (root/'backend/mtg_lab.db').exists()
  with receipt.open('x') as f:json.dump({'root':str(root),'pid':os.getpid(),'exit':int(exitstatus),'interpreter':sys.executable,'before_collection_guard_tests':checks,'import_pins':modules,'default_db_absent':True},f,indent=2,sort_keys=True)
raise SystemExit(pytest.main(sys.argv[1:],plugins=[Proof()]))
