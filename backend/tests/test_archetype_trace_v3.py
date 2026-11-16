"""Trace protocol checks on authored records, not measured games."""
from copy import deepcopy
import importlib
import importlib.util
import io
import json

import pytest


def subject():
    name = 'scripts.archetype_trace_v3'
    assert importlib.util.find_spec(name) is not None, 'V3 digest-chain trace is missing'
    return importlib.import_module(name)


def encoded():
    module = subject()
    stream = io.BytesIO()
    writer = module.TraceWriter(stream)
    records = [{'kind': 'initial', 'identity': {'cell_id': 'unit'}, 'snapshot': {'rng': [1, 2]}},
               {'kind': 'action', 'step': 0, 'action': {'type': 'pass_priority'}, 'after_sha256': 'a'*64},
               {'kind': 'final', 'outcome': {'status': 'tick_limit'}}]
    for row in records:
        writer.emit(row)
    return module, stream.getvalue(), records


def test_chain_roundtrip_preserves_exact_json_and_does_not_mutate_records():
    module, data, records = encoded()
    before = deepcopy(records)
    read = list(module.read_records(io.BytesIO(data)))
    assert [{k:v for k,v in row.items() if k not in module.CHAIN_KEYS} for row in read] == records
    assert records == before
    assert [row['sequence'] for row in read] == [0, 1, 2]
    assert read[0]['previous_record_sha256'] is None
    assert read[1]['previous_record_sha256'] == read[0]['record_sha256']


@pytest.mark.parametrize('change', ['action', 'delete', 'reorder', 'truncate', 'extra', 'duplicate_key', 'nan'])
def test_reader_refuses_modified_missing_reordered_or_malformed_records(change):
    module, data, _ = encoded()
    lines = data.splitlines(keepends=True)
    if change == 'action':
        row = json.loads(lines[1]); row['action']['type'] = 'invented'
        lines[1] = json.dumps(row).encode()+b'\n'
    elif change == 'delete': lines.pop(1)
    elif change == 'reorder': lines[0], lines[1] = lines[1], lines[0]
    elif change == 'truncate': lines[-1] = lines[-1][:-1]
    elif change == 'extra': lines.append(lines[-1])
    elif change == 'duplicate_key': lines[0] = lines[0].replace(b'{', b'{"kind":"initial",', 1)
    else: lines[0] = lines[0].replace(b'[1,2]', b'[NaN,2]')
    with pytest.raises(ValueError): list(module.read_records(io.BytesIO(b''.join(lines))))


def test_trace_quota_refuses_the_whole_next_record_before_any_write():
    module, data, records = encoded()
    first = data.splitlines(keepends=True)[0]
    stream = io.BytesIO()
    writer = module.TraceWriter(stream, max_bytes=len(first)-1)
    with pytest.raises(module.TraceLimit): writer.emit(records[0])
    assert stream.getvalue() == b'' and writer.sequence == 0 and writer.last_digest is None
    exact = io.BytesIO(); writer = module.TraceWriter(exact, max_bytes=len(first))
    writer.emit(records[0]); before = exact.getvalue()
    with pytest.raises(module.TraceLimit): writer.emit(records[1])
    assert exact.getvalue() == before and writer.sequence == 1


def test_writer_completes_short_writes_and_refuses_zero_progress():
    module = subject()
    class Short(io.BytesIO):
        def write(self, value): return super().write(value[:7])
    stream = Short(); writer = module.TraceWriter(stream)
    writer.emit({'kind':'initial'}); writer.emit({'kind':'final'})
    assert len(list(module.read_records(io.BytesIO(stream.getvalue())))) == 2
    class Stuck(io.BytesIO):
        def write(self, value): return 0
    with pytest.raises(OSError): module.TraceWriter(Stuck()).emit({'kind':'initial'})


def test_checkpoint_policy_covers_64_handler_decision_and_final_boundaries():
    module = subject()
    state = {'pregame_pending': False, 'pending_mechanic_choice': None,
             'pending_trigger_order': None, 'pending_replacement_choice': None}
    assert module.checkpoint_reasons(state, state, 62) == []
    assert module.checkpoint_reasons(state, state, 63) == ['periodic']
    assert module.checkpoint_reasons(state, state, 64) == []
    assert module.checkpoint_reasons(state, state, 0) == ['handler']
    assert module.checkpoint_reasons(state, state, 100) == ['handler']
    pending = {**state, 'pending_mechanic_choice': {'kind': 'unit'}}
    assert module.checkpoint_reasons(state, pending, 7) == ['choice']
    assert module.checkpoint_reasons(pending, state, 7) == ['choice']
    assert module.checkpoint_reasons({**state, 'pregame_pending': True}, state, 7) == ['pregame']
    assert module.checkpoint_reasons(state, state, 7, final=True) == ['final']


def test_writer_refuses_supplied_chain_fields_and_nonfinite_json():
    module = subject(); stream = io.BytesIO(); writer = module.TraceWriter(stream)
    for row in ({'kind':'initial','sequence':0},{'kind':'initial','value':float('inf')}):
        with pytest.raises(ValueError): writer.emit(row)
    assert stream.getvalue() == b''


def test_partial_progress_binds_an_exact_complete_prefix_not_an_unflushed_tail():
    module,data,_=encoded()
    assert callable(getattr(module,'verify_progress_prefix',None)),'Progress prefix verification is missing'
    rows=list(module.read_records(io.BytesIO(data)));lines=data.splitlines(keepends=True)
    receipt={'identity':{'cell_id':'unit'},'last_sequence':1,'last_record_sha256':rows[1]['record_sha256'],
             'trace_bytes':len(lines[0])+len(lines[1]),'accepted_actions':1}
    result=module.verify_progress_prefix(io.BytesIO(b''.join(lines[:2])+b'{"interrupted'),receipt)
    assert result=={'last_kind':'action','accepted_actions':1,'trace_bytes':receipt['trace_bytes']}
    for key,value in [('last_record_sha256','0'*64),('trace_bytes',receipt['trace_bytes']-1),
                      ('accepted_actions',2),('last_sequence',2)]:
        with pytest.raises(ValueError):module.verify_progress_prefix(io.BytesIO(data),{**receipt,key:value})
