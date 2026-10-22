import json,pathlib,runpy,sys
report=pathlib.Path(sys.argv[1]);args=sys.argv[2:];denied=[]
def guard(event,args):
 if event.startswith(('socket.','sqlite3.')):
  denied.append(event);raise PermissionError('OFFLINE_INSTALL_IO_DENIED')
sys.addaudithook(guard);sys.argv=['pip',*args]
try:runpy.run_module('pip',run_name='__main__')
finally:report.write_text(json.dumps({'denied_events':denied,'pip_argv':args})+'\n')
