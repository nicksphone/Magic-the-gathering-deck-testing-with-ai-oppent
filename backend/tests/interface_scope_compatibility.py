"""Finite byte-exact undo of identified public deltas, preserving old witnesses."""
import hashlib
import json
from pathlib import Path

PATH = Path(__file__).parent / 'fixtures/interface_scope_compatibility/approved_public_deltas.json'
raw = PATH.read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'bc0cde4e6e52f6ce2b76c64f68688c3a649271e415b24bd581ce431a4e7c08f3'
CONTRACT = json.loads(raw)
assert CONTRACT['approved_public_commit'] == '2fd7b7bb1e3ea3f353770744b113b92df2fd32e4'


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
    if hashlib.sha256(current).hexdigest() == historical:
        return historical
    _restore(current.decode(), recipe)
    return recipe['new_sha256']


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
