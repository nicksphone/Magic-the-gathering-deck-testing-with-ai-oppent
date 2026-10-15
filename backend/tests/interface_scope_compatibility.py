"""Finite byte-exact undo of identified public deltas, preserving old witnesses."""
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

REPOSITORY_DELTA_PATH = PATH.with_name('accepted_phase1_repository_delta.json')
repository_raw = REPOSITORY_DELTA_PATH.read_bytes()
assert hashlib.sha256(repository_raw).hexdigest() == '7617e4b9dbf6f1512bfd7bba51dc5a5e2506ade3163c28dca035e90c53b0e144'
REPOSITORY_DELTAS = json.loads(repository_raw)
assert REPOSITORY_DELTAS['source'] == 'persistence/repository.py'
assert REPOSITORY_DELTAS['accepted_public_commits'] == [
    'cd271b9edac81018e68a64cafd35ec9ca1b71530', '357680de093b0048b96f1f8596defae0f19f5b9d']
ACCEPTED_REPOSITORY_DELTA = REPOSITORY_DELTAS['accepted_repository_delta']


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
               'tests/private_choice_boundary_fixture_server.py': ACCEPTED_DELTAS['accepted_private_fixture_delta']}
    assert name in recipes, 'No approved current delta for this source'
    recipe = recipes[name]
    assert historical == recipe['old_sha256'], 'Historical operand changed'
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
    return (_restore(before, CONTRACT['keyword_prefix']) + prefix + middle + suffix
            + _restore(after, CONTRACT['keyword_suffix']))
