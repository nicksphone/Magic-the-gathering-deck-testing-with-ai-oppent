"""Parent-side replay drift must stop admission, independently of health entry."""
import os
import threading

from test_archetype_pilot_v3 import authored_phase_controller, plan


def test_parent_detected_outcome_divergence_sets_stop_before_another_cell(tmp_path,monkeypatch):
    core,requests,source=authored_phase_controller(monkeypatch,bad='winner')
    p=plan();stop=threading.Event()
    row=core.run_cell(p,p['cells'][0],tmp_path/'cell',cpu=min(os.sched_getaffinity(0)),
                      source=source,runtime={'unit_runtime':True},stop=stop)
    assert [r['mode']for r in requests]==['game','verify']
    assert row['status']=='replay_divergence' and row['winner'] is None
    assert stop.is_set(),'Parent-detected replay drift must stop admission too'
