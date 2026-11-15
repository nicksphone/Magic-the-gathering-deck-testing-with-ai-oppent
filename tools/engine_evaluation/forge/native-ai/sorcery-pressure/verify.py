#!/usr/bin/env python3
"""Pin and inspect this bounded native test run. Never invokes engine evaluators."""
import hashlib
import json
import re
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


mode, identity_path, shadow_path, output_path = sys.argv[1:]
here = Path(__file__).resolve().parent
identity_path, shadow, output = map(Path, [identity_path, shadow_path, output_path])
identity = json.loads(identity_path.read_text())
expected = json.loads((here/'PREFIX-PIN.json').read_text())
assert expected['content_id'] == 'd36d96612e9b770575dd7de4a40b17fce8bccc23ec8dac66002e557d9e7b3d29'
assert json.loads((shadow.parent/'MANIFEST.json').read_text()) == expected
payloads = expected['identity']['payloads']
assert len(payloads) == 7
assert sorted(str(path.relative_to(shadow)) for path in shadow.rglob('*') if path.is_file()) == sorted(item['path'] for item in payloads)
assert identity['build_id'] == expected['identity']['base_build_id']
for item in payloads:
    assert sha(shadow/item['path']) == item['sha256'], item['path']
plan = json.loads((output/'DECLARATION.json').read_text())
assert plan == json.loads((here/'DECLARATION.json').read_text())
assert plan['seed'] == 2026110617 and len(plan['cases']) == 8
assert sorted((case['seat'], case['scene']) for case in plan['cases']) == [
    (seat, scene) for seat in [0, 1] for scene in ['lethal', 'pressure', 'unfunded-lethal', 'upkeep-lethal']]
if mode == 'preflight':
    pins = {'base_identity_sha256': sha(identity_path), 'prefix_manifest': expected,
            'declaration_sha256': sha(output/'DECLARATION.json'),
            'source_sha256': sha(here/'NativeSorceryPressureControls.java'),
            'scope': 'Test-only fixed eight-case family; current seven-class prefix, not old ff89.'}
    (output/'PREFLIGHT.json').write_text(json.dumps(pins, indent=2)+'\n')
    print('Preflight: current seven-class d36d prefix and fixed eight-case declaration verified')
elif mode == 'closed':
    summary = json.loads((output/'summary.private.json').read_text())
    assert summary['seed'] == plan['seed'] and len(summary['cases']) == 8
    assert summary['natural_games'] == 0 and summary['production_changes'] is False
    assert summary['errors'] == 0, 'Harness errors are not behavioral REDs'
    assert (output/'exit-code.txt').read_text().strip() == ('1' if summary['failures'] else '0')
    for spec, case in zip(plan['cases'], summary['cases']):
        assert case['declaration'] == spec and case['choice_calls'] == 1
        assert case['profile'] == 'Default' and case['native_chain_property'] == 90
        if spec['scene'] != 'pressure':
            assert case['passed'] is True, (spec, case)
        if spec['scene'] == 'lethal':
            assert case['paid_lands'] == 1 and case['enemy_life_after_resolution'] == 0
            assert case['native_game_over'] is True and case['native_actor_won'] is True
    origins = {}
    for line in (output/'class-load.log').read_text().splitlines():
        match = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
        if match:
            origins[match[1]] = match[2].rstrip('/')
    actual_origins, unused = {}, []
    for item in payloads:
        name = item['class_name']
        if name not in origins:
            unused.append(name)
            continue
        assert Path(origins[name]) == shadow, (name, origins[name])
        actual_origins[name] = origins[name]
    assert 'forge.ai.ability.DamageDealAi' in actual_origins
    assert 'forge.ai.ComputerUtilMana' in actual_origins
    assert 'forge.evaluation.ActorBoundary' in actual_origins
    base_ai = Path(identity['forge'])/'forge-ai/target/classes'
    for name in ['forge.ai.AiController', 'forge.ai.ability.DamageAiBase', 'forge.ai.PlayerControllerAi']:
        assert Path(origins[name]) == base_ai
    assert Path(origins['forge.evaluation.PublicNameController']) == Path(identity['runtime_classpath'][0])
    network = (output/'network.private.strace').read_text()
    ip_connects = len(re.findall(r'connect\(.*sa_family=AF_INET6?', network))
    assert ip_connects == 0
    assert not re.search(r'TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired',
                         (output/'stderr.private.log').read_text())
    verified = {'label': summary['label'], 'passed': summary['passed'], 'failures': summary['failures'],
                'errors': summary['errors'], 'loaded_override_origins': actual_origins,
                'pinned_but_not_observed_loaded': unused, 'all_seven_payloads_hash_verified': True,
                'base_ai_origins_verified': True, 'IP_connects': ip_connects,
                'natural_games': 0, 'one_choice_call_per_case': True, 'production_changes': False,
                'pressure_failures': [case['declaration'] for case in summary['cases'] if 'failure' in case]}
    (output/'VERIFIED-CLOSED.json').write_text(json.dumps(verified, indent=2)+'\n')
    print(json.dumps({key: verified[key] for key in ['label', 'passed', 'failures', 'errors', 'natural_games']}, indent=2))
else:
    raise ValueError('Expected preflight or closed mode')
