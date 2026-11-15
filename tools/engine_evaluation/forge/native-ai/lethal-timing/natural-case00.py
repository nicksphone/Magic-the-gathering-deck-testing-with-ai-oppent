#!/usr/bin/env python3
"""One fresh, uninstrumented original case00 series, with an optional one-class shadow."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


case, run = (Path(value).resolve() for value in sys.argv[1:3])
shadow = Path(sys.argv[3]).resolve() if len(sys.argv) == 4 else None
assert len(sys.argv) in (3, 4) and case.is_dir() and not run.exists()
assert json.loads((case/'RESULT.json').read_text())['qualified_completed_series'] is True
spec = json.loads((case/'SPEC.json').read_text())
assert spec['seed'] == 2026110602 and spec['flat_monte_carlo'] is False
assert spec['open_decklists'] is True and spec['use_public_name_controller'] is True
cohort = json.loads((case.parent/'COHORT.json').read_text())
assert cohort['native_content_id'] == 'ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398'
original = json.loads((case/'LAUNCH.json').read_text())['argv']
assert original[:4] == ['timeout', '-k', '10s', '300']
assert original[-2:] == ['forge.evaluation.NativeNameMatchProbe', str(case)]
classpath = ':'.join(cohort['CP'])
assert original[original.index('-cp')+1] == classpath
assert '-Xmx1500m' in original and '-XX:ActiveProcessorCount=1' in original
assert '--clearenv' in original and '--unshare-net' in original
assert not subprocess.check_output(['findmnt', '-T', str(run.parent), '-n', '-o', 'FSTYPE'], text=True).strip().startswith(('nfs', 'cifs'))
run.mkdir(mode=0o700)
for name in ['home', 'tmp', 'decks']:
    (run/name).mkdir(mode=0o700)
shutil.copyfile(case/'SPEC.json', run/'SPEC.json')
for name in ['seat0.dck', 'seat1.dck']:
    shutil.copyfile(case/'decks'/name, run/'decks'/name)
pins = {str(case/name): sha(case/name) for name in ['SPEC.json', 'LAUNCH.json', 'RESULT.json',
        'decks/seat0.dck', 'decks/seat1.dck', 'game-logs.private.jsonl', 'actor-observations.private.jsonl']}
pins.update({str(path): sha(path) for path in (case.parent/'classes/forge/evaluation').glob('NativeNameMatchProbe*.class')})
argv = [arg.replace(str(case)+'/', str(run)+'/') for arg in original]
argv[-1] = str(run)
binds = [i for i, value in enumerate(argv) if value == '--bind']
assert len(binds) == 1 and argv[binds[0]+1:binds[0]+3] == [str(case.parent)]*2
argv[binds[0]] = '--ro-bind'
extra = ['--bind', str(run), str(run)]
if shadow is not None:
    payloads = sorted(str(path.relative_to(shadow)) for path in shadow.rglob('*') if path.is_file())
    assert payloads == ['forge/ai/ability/DamageDealAi.class']
    extra += ['--ro-bind', str(shadow), str(shadow)]
    argv[argv.index('-cp')+1] = str(shadow)+':'+classpath
    pins[str(shadow/payloads[0])] = sha(shadow/payloads[0])
at = argv.index('--proc')
argv[at:at] = extra
save(run/'INPUT-PINS.json', pins)
started = time.monotonic()
with (run/'stdout.private.log').open('wb') as out, (run/'stderr.private.log').open('wb') as err:
    process = subprocess.Popen(argv, stdout=out, stderr=err, cwd=run, start_new_session=True)
    save(run/'LAUNCH.json', {'pid': process.pid, 'argv': argv, 'instrumentation': False})
    code = process.wait()
events = []
prefix = '@@MTG_PROBE_JSON '
for line in (run/'stdout.private.log').read_text(errors='replace').splitlines():
    if line.startswith(prefix):
        events.append(json.loads(line[len(prefix):]))
games = [event for event in events if event.get('kind') == 'native_game_complete']
matches = [event for event in events if event.get('kind') == 'native_match_complete']
errors = [event for event in events if event.get('kind') == 'probe_error']
unchanged = all(sha(Path(path)) == digest for path, digest in pins.items())
completed = code == 0 and bool(games) and len(matches) == 1 and not errors and unchanged
save(run/'RESULT.json', {'exit': code, 'seconds': time.monotonic()-started,
     'qualified_completed_series': completed, 'scope': 'Single declared case00 replay, not broad quality or app qualification',
     'instrumentation': False, 'original_inputs_unchanged': unchanged,
     'games': games, 'match': matches, 'errors': errors,
     'search': [event for event in events if event.get('kind') == 'native_search_stats']})
print(json.dumps({'run': str(run), 'exit': code, 'qualified_completed_series': completed,
      'games': [{'turns': event['turns'], 'outcomes': event['outcomes']} for event in games]}), flush=True)
raise SystemExit(0 if completed else 1)
