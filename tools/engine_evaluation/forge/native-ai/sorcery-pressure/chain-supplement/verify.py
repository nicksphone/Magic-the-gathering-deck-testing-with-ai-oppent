#!/usr/bin/env python3
"""Verify only this supplement's closed evidence and preservation of the frozen eight."""
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
assert len(payloads) == 7 and identity['build_id'] == expected['identity']['base_build_id']
assert sorted(str(path.relative_to(shadow)) for path in shadow.rglob('*') if path.is_file()) == sorted(item['path'] for item in payloads)
for item in payloads:
    assert sha(shadow/item['path']) == item['sha256']
old = json.loads((here/'FROZEN8-PIN.json').read_text())
assert len(old) == 18
for path, digest in old.items():
    assert sha(Path(path)) == digest, 'Frozen original eight changed: '+path
plan = json.loads((output/'DECLARATION.json').read_text())
assert plan == json.loads((here/'DECLARATION.json').read_text())
assert plan['seed'] == 2026110617 and plan['cases'] == [{'seat': 0}, {'seat': 1}]
assert plan['expected']['enemy_life_after_each'] == [17, 14, 11]
if mode == 'preflight':
    (output/'PREFLIGHT.json').write_text(json.dumps({
        'base_identity_sha256': sha(identity_path), 'prefix_manifest': expected,
        'declaration_sha256': sha(output/'DECLARATION.json'),
        'test_source_sha256': sha(here/'NativeSorceryChainControls.java'),
        'original_eight_source_class_archive_pins': old,
        'scope': 'Two new single-game three-choice scenes only; no original test rerun or production change.'}, indent=2)+'\n')
    print('Preflight: current seven-class prefix, two new chain scenes and frozen-eight bytes verified')
elif mode == 'closed':
    result = json.loads((output/'summary.private.json').read_text())
    assert result['seed'] == 2026110617 and result['constructed_games'] == 2
    assert len(result['cases']) == 2 and result['errors'] == 0
    assert result['natural_games'] == 0 and result['production_changes'] is False
    assert (output/'exit-code.txt').read_text().strip() == ('1' if result['failures'] else '0')
    for seat, case in enumerate(result['cases']):
        assert case['seat'] == seat and len(set(case['original_source_ids'])) == 3
        assert case['profile'] == 'Default' and case['native_chain_property'] == 90
        assert 1 <= len(case['steps']) <= 3
        for number, step in enumerate(case['steps'], 1):
            assert step['step'] == number and step['before'] == step['after_choice']
            assert step['before']['phase'] == 'MAIN2'
            if 'after_resolution' in step:
                state = step['after_resolution']
                assert state['enemy_life'] == [17, 14, 11][number-1] and state['actor_life'] == 20
                assert len(state['hand']) == 3-number and len(state['graveyard']) == number
                assert sum(card['tapped'] for card in state['battlefield']) == number
                assert state['mana_pool'] == 0 and state['game_terminal'] is False
        if case.get('passed') is True:
            assert len(case['steps']) == 3
            final = case['steps'][-1]['after_resolution']
            assert sorted(card['id'] for card in final['graveyard']) == sorted(case['original_source_ids'])
            assert final['hand'] == [] and final['enemy_life'] == 11
        else:
            assert case['declined_at_step'] == len(case['steps']) and case['steps'][-1]['chosen'] == []
    origins = {}
    for line in (output/'class-load.log').read_text().splitlines():
        found = re.search(r'\] (forge\.[\w.$]+) source: file:(.*)$', line)
        if found:
            origins[found[1]] = found[2].rstrip('/')
    loaded, unused = {}, []
    for item in payloads:
        name = item['class_name']
        if name not in origins:
            unused.append(name)
        else:
            assert Path(origins[name]) == shadow
            loaded[name] = origins[name]
    assert 'forge.ai.ability.DamageDealAi' in loaded and 'forge.ai.ComputerUtilMana' in loaded
    assert Path(origins['forge.ai.ability.DamageAiBase']) == Path(identity['forge'])/'forge-ai/target/classes'
    assert Path(origins['forge.evaluation.PublicNameController']) == Path(identity['runtime_classpath'][0])
    assert 'forge.evaluation.NativeSorceryPressureControls' not in origins
    network = (output/'network.private.strace').read_text()
    ip_connects = len(re.findall(r'connect\(.*sa_family=AF_INET6?', network))
    assert ip_connects == 0
    assert not re.search(r'TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired',
                         (output/'stderr.private.log').read_text())
    verified = {'label': result['label'], 'passed': result['passed'], 'failures': result['failures'],
                'errors': result['errors'], 'constructed_games': 2, 'natural_games': 0,
                'declined_steps': [case.get('declined_at_step') for case in result['cases']],
                'all_seven_payload_hashes_verified': True, 'observed_override_origins': loaded,
                'pinned_but_not_observed_loaded': unused, 'IP_connects': ip_connects,
                'all18_original_source_class_archive_pins_unchanged': True,
                'original_eight_class_not_loaded': True, 'production_changes': False}
    (output/'VERIFIED-CLOSED.json').write_text(json.dumps(verified, indent=2)+'\n')
    print(json.dumps({key: verified[key] for key in ['label', 'passed', 'failures', 'errors', 'declined_steps']}, indent=2))
else:
    raise ValueError('Expected preflight or closed mode')
