"""Source-only scope pins and original RED-boundary inventory; no app imports."""
import ast
import collections
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / 'evidence'
SCOPES = {
    'game_state/state.py': ['MatchState'],
    'game_state/serializers.py': ['serialize_match_snapshot', 'deserialize_match_snapshot'],
    'rules_engine/events.py': ['_trigger_from_oracle', '_append_trigger_groups', '_targeted_trigger_clause', 'trigger_target_options'],
    'rules_engine/counter_placement.py': ['counter_placement_forbidden'],
    'rules_engine/keyword_actions.py': ['finish_mechanic_choice'],
    'rules_engine/action_validation.py': ['validate_action'],
    'rules_engine/move_generator.py': ['legal_moves'],
    'rules_engine/optional_reveal.py': ['public_choice'],
    'effects/registry.py': [],
}
READ_ONLY = ['rules_engine/engine.py', 'rules_engine/stack_engine.py', 'rules_engine/oracle_effects.py',
             'rules_engine/costs.py', 'rules_engine/continuous.py', 'rules_engine/targeting.py',
             'rules_engine/coverage.py', 'api_contracts.py']

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

pins = {}
for relative in list(SCOPES) + READ_ONLY:
    path = ROOT / 'backend' / relative
    raw = path.read_bytes()
    tree = ast.parse(raw)
    lines = raw.splitlines(keepends=True)
    entries = {}
    for name in SCOPES.get(relative, []):
        node = next(n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        block = b''.join(lines[start-1:node.end_lineno])
        entries[name] = {'line': start, 'end_line': node.end_lineno, 'preimage_sha256': digest(block),
                         'ast_sha256': digest(ast.dump(node, include_attributes=False).encode())}
    pins[relative] = {'file_sha256': digest(raw), 'requested_functions': entries,
                      'status': 'proposal-only' if relative in SCOPES else 'read-only'}
writer_rows = []
for path in sorted((ROOT / 'backend').rglob('*.py')):
    raw = path.read_bytes()
    for node in ast.walk(ast.parse(raw)):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            text = ast.unparse(target)
            if '.counters' in text or text.endswith(('.poison', '.loyalty', '.counter_timestamps')):
                writer_rows.append({'path': str(path.relative_to(ROOT)), 'line': node.lineno,
                                    'assignment': ast.unparse(node), 'file_sha256': digest(raw)})
cases = ET.parse(OUT / 'sunc-dadd-current32.xml').findall('.//testcase')
counts = collections.Counter()
failures = []
for case in cases:
    failure = case.find('failure')
    if failure is None:
        counts['pass'] += 1
        continue
    trace = failure.text or ''
    upstream = 'test_desired_complete_paid_suncleanser_family[protected-atomic-creature-' in case.attrib['name']
    boundary = 'upstream_safekeeper_action_admission' if upstream else 'desired_public_mode_witness'
    if upstream:
        assert "card_id=protector, ability_index=0" in trace and 'ActionRejected' in trace
    else:
        assert 'Desired explicit modal ETB public witness' in trace or 'Desired lawful alternative mode public witness' in trace
    counts[boundary] += 1
    failures.append({'node_name': case.attrib['name'], 'boundary': boundary,
                     'trace_sha256': digest(trace.encode())})
receipt = json.loads((OUT / 'sunc-dadd-current32-runtime.json').read_text())
assert counts == {'pass': 12, 'desired_public_mode_witness': 18, 'upstream_safekeeper_action_admission': 2}
assert receipt['default_database_absent'] and receipt['exit'] == 1
assert set(receipt['precollection_denials']) == {'sqlite3.connect', 'socket.__new__', 'subprocess.Popen', 'os.system', 'os.fork'}
for pin in receipt['import_pins'].values():
    assert digest((ROOT / pin['path']).read_bytes()) == pin['sha256']
report = {'base_commit': 'dadd3388e1ae2228b898ad830d996a18373f4b3a',
          'qualification': 'source-only proposal; current32 original assertions remain RED',
          'proposed_scope': pins, 'physical_storage_assignment_inventory': writer_rows,
          'inventory_limit': 'AST assignments, not complete call/dynamic-write coverage or runtime certificate',
          'current32': {'cases': len(cases), 'counts': dict(counts), 'failures': failures,
                        'native_receipt_sha256': digest((OUT / 'sunc-dadd-current32-runtime.json').read_bytes())}}
with (OUT / 'sunc-dadd-abi-scope-pins.json').open('x') as stream:
    json.dump(report, stream, sort_keys=True, indent=2)
print(json.dumps({'cases': len(cases), 'counts': dict(counts), 'assignment_rows': len(writer_rows), 'files_pinned': len(pins)}))
