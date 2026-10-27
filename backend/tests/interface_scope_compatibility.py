"""Finite byte-exact undo of identified public deltas, preserving old witnesses."""
import ast
import hashlib
import json
from pathlib import Path

PATH = Path(__file__).parent / 'fixtures/interface_scope_compatibility/approved_public_deltas.json'
raw = PATH.read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'bc0cde4e6e52f6ce2b76c64f68688c3a649271e415b24bd581ce431a4e7c08f3'
CONTRACT = json.loads(raw)
assert CONTRACT['approved_public_commit'] == '2fd7b7bb1e3ea3f353770744b113b92df2fd32e4'

DELTA_PATH = PATH.with_name('accepted_1ca_deltas.json')
delta_raw = DELTA_PATH.read_bytes()
assert hashlib.sha256(delta_raw).hexdigest() == '5ec2d971a754c734fd4a378368398461664be3b48138150092e74dce9fb8bc40'
ACCEPTED_DELTAS = json.loads(delta_raw)
assert ACCEPTED_DELTAS['accepted_public_commit'] == '1ca5005d7840a569f35f3797d03e3c852386816e'
ACCEPTED_MAIN_DELTA = ACCEPTED_DELTAS['accepted_main_delta']

CURRENT_MAIN_PATH = PATH.with_name('accepted_9b_main_delta.json')
current_main_raw = CURRENT_MAIN_PATH.read_bytes()
assert hashlib.sha256(current_main_raw).hexdigest() == '484d19fd477c449a1be50b671e84fd8faa5ea4469368931ba7ff044d1380bed8'
CURRENT_MAIN = json.loads(current_main_raw)
assert CURRENT_MAIN['accepted_public_commit'] == '9b82651ab9e97a87924447ced572b3ea5d7ff212'
assert CURRENT_MAIN['previous_accepted_public_commit'] == ACCEPTED_DELTAS['accepted_public_commit']
assert CURRENT_MAIN['source'] == 'main.py'
CURRENT_MAIN_DELTA = CURRENT_MAIN['accepted_main_delta']
assert CURRENT_MAIN_DELTA['old_sha256'] == ACCEPTED_MAIN_DELTA['new_sha256']

REPOSITORY_DELTA_PATH = PATH.with_name('accepted_phase1_repository_delta.json')
repository_raw = REPOSITORY_DELTA_PATH.read_bytes()
assert hashlib.sha256(repository_raw).hexdigest() == '7617e4b9dbf6f1512bfd7bba51dc5a5e2506ade3163c28dca035e90c53b0e144'
REPOSITORY_DELTAS = json.loads(repository_raw)
assert REPOSITORY_DELTAS['source'] == 'persistence/repository.py'
assert REPOSITORY_DELTAS['accepted_public_commits'] == [
    'cd271b9edac81018e68a64cafd35ec9ca1b71530', '357680de093b0048b96f1f8596defae0f19f5b9d']
ACCEPTED_REPOSITORY_DELTA = REPOSITORY_DELTAS['accepted_repository_delta']

SPECTACLE_COST_PATH = PATH.with_name('accepted_spectacle_cost_delta.json')
spectacle_cost_raw = SPECTACLE_COST_PATH.read_bytes()
assert hashlib.sha256(spectacle_cost_raw).hexdigest() == 'aa8eed59662da52702084af7d166fb1facd554bbfad8ae098266c4ea5f11ddaf'
SPECTACLE_COST = json.loads(spectacle_cost_raw)
assert SPECTACLE_COST['accepted_public_commit'] == '3d691056ba34b9f578f6d038b871c233a41fe869'
assert SPECTACLE_COST['source'] == 'rules_engine/costs.py'
ACCEPTED_SPECTACLE_COST_DELTA = SPECTACLE_COST['accepted_delta']

FINITE_PATH = PATH.with_name('accepted_76_source_inverses.json')
finite_raw = FINITE_PATH.read_bytes()
assert hashlib.sha256(finite_raw).hexdigest() == '268baa65862fe5eab759629e5b8370a8943f4d3dcae8077009515f2e0494324d'
FINITE = json.loads(finite_raw)
assert FINITE['function_delta_predecessor'] == '091e7e4eed2b0be6dd1b7f9fe38068dc42833a79'
expected_raw = PATH.parents[1].joinpath('rules_printed_facts_e4/UNCHANGED_FUNCTION_SHA256.json').read_bytes()
assert hashlib.sha256(expected_raw).hexdigest() == '94a314f7a95f8a1f538f06c181c274324b2afef2d97414f8d1c8ce29dd7e3559'
EXPECTED_FUNCTIONS = json.loads(expected_raw)
assert len(FINITE['functions']) == 14
assert all(recipe['old_sha256'] == EXPECTED_FUNCTIONS[identity]
           for identity, recipe in FINITE['functions'].items())

fixture_inverse_raw = PATH.with_name('reviewed_task13_fixture_inverses.json').read_bytes()
assert hashlib.sha256(fixture_inverse_raw).hexdigest() == 'f4e505e4cc13a7004cea39aca02e820de72c17675dc9232be9616c23d44c98bc'
FIXTURE_INVERSES = json.loads(fixture_inverse_raw)['functions']
assert len(FIXTURE_INVERSES) == 3
assert not (FIXTURE_INVERSES.keys() & FINITE['functions'].keys())
assert all(recipe['old_sha256'] == EXPECTED_FUNCTIONS[identity]
           for identity, recipe in FIXTURE_INVERSES.items())


SMOTHERING_IDENTITY = 'test_events_apnap.py:test_sacrifice_emits_sacrifice_trigger_for_creature'
# Source-hash normalization ONLY. The obsolete constructor stays inert text.
SMOTHERING_INVERSE = {
    'old_sha256': 'df7f2d08b8579ed6fe545a1582ba388d9cebb3afbbb337a619a113b83412cfe9',
    'new_sha256': '7969f39952949ec76c0010735c8f2ae41a7b25639e33ad2b479e36d1a63b4b29',
    'hunks': [{
        'start': 7, 'end': 13,
        'new': ('    state.cards["p1"] = smothering_card(\n'
                '        id="p1",\n'
                '        owner=1,\n'
                '        controller=1,\n'
                '        zone=Zone.BATTLEFIELD,\n'
                '    )\n'),
        'old': ('    state.cards["p1"] = CardInstance(\n'
                '        id="p1",\n'
                '        name="Blood Artist",\n'
                '        owner=1,\n'
                '        controller=1,\n'
                '        zone=Zone.BATTLEFIELD,\n'
                '        types=["Creature"],\n'
                '        oracle_text="Whenever another creature you control is sacrificed, draw a card.",\n'
                '    )\n'),
    }],
}
assert SMOTHERING_INVERSE['old_sha256'] == EXPECTED_FUNCTIONS[SMOTHERING_IDENTITY]


def _restore(text, recipe):
    if hashlib.sha256(text.encode()).hexdigest() == recipe['old_sha256']:
        return text
    lines = text.splitlines(keepends=True)
    for hunk in reversed(recipe['hunks']):
        assert ''.join(lines[hunk['start']:hunk['end']]) == hunk['new'], 'Approved hunk changed'
        lines[hunk['start']:hunk['end']] = hunk['old'].splitlines(keepends=True)
    result = ''.join(lines)
    assert hashlib.sha256(result.encode()).hexdigest() == recipe['old_sha256'], 'Outside approved hunks changed'
    return result


def compatible_product_hash(name, current, historical):
    assert name in {'main.py', 'persistence/repository.py'}
    recipe = CONTRACT['production'][name]
    assert historical == recipe['old_sha256']
    measured = hashlib.sha256(current).hexdigest()
    if measured == historical:
        return historical
    reviewed = current
    if measured != recipe['new_sha256']:
        reviewed = restore_reviewed_source(name, current, recipe['new_sha256'])
    _restore(reviewed.decode(), recipe)
    return measured


def restore_reviewed_source(name, current, historical):
    recipes = {'main.py': ACCEPTED_MAIN_DELTA,
               'persistence/repository.py': ACCEPTED_REPOSITORY_DELTA,
               'rules_engine/costs.py': ACCEPTED_SPECTACLE_COST_DELTA,
               'tests/private_choice_boundary_fixture_server.py': ACCEPTED_DELTAS['accepted_private_fixture_delta']}
    assert name in recipes, 'No approved current delta for this source'
    recipe = recipes[name]
    assert historical == recipe['old_sha256'], 'Historical operand changed'
    if name == 'main.py' and hashlib.sha256(current).hexdigest() not in {
            recipe['old_sha256'], recipe['new_sha256']}:
        current = _restore(current.decode(), CURRENT_MAIN_DELTA).encode()
    return _restore(current.decode(), recipe).encode()


def restore_worker_platform(name, text):
    if name != 'import_identity_fix_worker.py':
        return text
    hunk = CONTRACT['worker_platform']
    assert text.count(hunk['new']) == 1, 'Only the identified GitHub branch may be undone'
    return text.replace(hunk['new'], hunk['old'], 1)


def restore_keyword_edges(text):
    prefix = '    events = [{"card_id": cid, "controller": player_id} for cid in ids]\n'
    suffix = '    emit_event_batch(state, "sacrifice", events)\n'
    assert text.count(prefix) == text.count(suffix) == 1
    before, remaining = text.split(prefix)
    middle, after = remaining.split(suffix)
    if hashlib.sha256(before.encode()).hexdigest() not in {
            CONTRACT['keyword_prefix']['old_sha256'], CONTRACT['keyword_prefix']['new_sha256']}:
        before = _restore(before, FINITE['keyword']['prefix'])
    return (_restore(before, CONTRACT['keyword_prefix']) + prefix + middle + suffix
            + _restore(after, CONTRACT['keyword_suffix']))


def restore_printed_protocol_source(module, text):
    assert module in {identity.split(':')[0] for identity in EXPECTED_FUNCTIONS}, 'Unknown protected module'
    nodes = ast.parse(text).body
    recipes = {**FINITE['functions'], **FIXTURE_INVERSES,
               SMOTHERING_IDENTITY: SMOTHERING_INVERSE}
    for identity, recipe in recipes.items():
        filename, name = identity.split(':')
        if filename != module:
            continue
        matches = [node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, 'Protected function missing or duplicated'
        segment = ast.get_source_segment(text, matches[0])
        assert text.count(segment) == 1, 'Protected function source is ambiguous'
        restored = _restore(segment, recipe)
        text = text.replace(segment, restored, 1)
        nodes = ast.parse(text).body
    return text
