"""Real operator prepare/inventory seam, explicit file fixtures only; no SQL/listeners."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[1]
assert len(sys.argv) <= 2
candidate=Path(sys.argv[1]) if len(sys.argv)==2 else HERE/'run.py'
spec=importlib.util.spec_from_file_location('operator_under_test',candidate);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='mtg-operator-inventory-') as td:
 root=Path(td);source=root/'source';backend=source/'backend';backend.mkdir(parents=True)
 shutil.copy2(SOURCE/'backend/browser_origin.py',backend/'browser_origin.py')
 shutil.copy2(SOURCE/'backend/tests/fixtures/mana_executor_choices.json',backend/'fixture.json')
 m.SOURCE=source
 runtime=root/'runtime';cfg={'runtime':runtime}
 m.prepare(cfg).close();real=runtime/'backend'
 artifact_names=['mtg_lab.db.capacity-owner.lock','mtg_lab.db.before-capacity-'+uuid.uuid4().hex+'.db']
 for name in artifact_names:(real/name).write_bytes(b'Explicit inventory artifact fixture; not a SQLite execution.\n')
 # This genuine shared prepare call must accept precisely these runtime artifacts.
 m.prepare(cfg).close()
 print('PASS actual prepare restart with exact owner lock/UUID-hex backup')
 def denied(label,change,undo):
  change()
  try:m.prepare(cfg).close()
  except (ValueError,OSError):print('PASS reject',label)
  else:raise AssertionError('Unexpected restart acceptance: '+label)
  finally:undo()
 for name in ['unknown.db','mtg_lab.db.before-capacity-nothex.db','mtg_lab.db.before-capacity-'+uuid.uuid4().hex+'.db.extra','nested/mtg_lab.db.capacity-owner.lock']:
  p=real/name;p.parent.mkdir(exist_ok=True)
  denied(name,lambda:p.write_bytes(b'unknown'),lambda:p.unlink())
  if p.parent!=real:p.parent.rmdir()
 p=real/'fixture.json';original=p.read_bytes()
 denied('modified nonpy fixture',lambda:p.write_bytes(b'modified'),lambda:p.write_bytes(original))
 p=real/'browser_origin.py';original=p.read_bytes()
 denied('modified backend code',lambda:p.write_bytes(b'modified'),lambda:p.write_bytes(original))
 for name in artifact_names:
  p=real/name;original=p.read_bytes();p.unlink()
  denied('artifact symlink '+name,lambda:p.symlink_to(real/'fixture.json'),lambda:p.unlink())
  denied('artifact hardlink '+name,lambda:os.link(real/'fixture.json',p),lambda:p.unlink())
  p.write_bytes(original)
 before=m.inventory(backend)
 for name in artifact_names:(backend/name).write_bytes(b'source artifact is tracked, never ignored')
 assert m.inventory(backend)!=before,'Source inventory was relaxed'
 print('PASS source artifact inventory remains tracked')
print('PASS 12 restart/inventory cases; no native SQL or server proof')
