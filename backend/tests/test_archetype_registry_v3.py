"""Host-local run consumption and controller exclusion in private temp dirs."""
import importlib
import importlib.util
import json

import pytest


def subject():
    name='scripts.archetype_registry_v3'
    assert importlib.util.find_spec(name) is not None,'Persistent v3 run consumption is missing'
    return importlib.import_module(name)


def claim(root,name='first'):
    return subject().claim_run(root,run_id=f'archetype-pilot-20261116-v3-{name}',
        plan_sha256='a'*64,revision='b'*40,runtime_sha256='c'*64,output=str(root.parent/name))


def test_consumed_run_id_cannot_be_reused_after_success_in_another_output(tmp_path):
    root=tmp_path/'state'
    with claim(root)as attempt:
        with pytest.raises(ValueError):claim(root,'concurrent').__enter__()
        record=attempt.finish(charged_worker_seconds=100.,report_sha256='d'*64)
        assert record['charged_worker_seconds']==100 and record['remaining_campaign_worker_seconds']==48*3600-100
        assert record['reserved_health_worker_seconds']==30*3600
    assert root.stat().st_mode&0o777==0o700
    with pytest.raises(FileExistsError):
        with claim(root):pass
    with claim(root,'fresh')as attempt:
        carried=attempt.finish(charged_worker_seconds=0.,report_sha256=None)
        assert carried['remaining_campaign_worker_seconds']==48*3600-100
        assert carried['charged_campaign_worker_seconds']==100
    assert (root/'controller.lock').exists(),'Never unlink a live-lock inode to reset state'


def test_interrupted_controller_remains_unproven_and_blocks_new_controller(tmp_path):
    root=tmp_path/'state'
    with claim(root)as attempt:
        pass  # no finish: no claim that owned children have been reaped
    with pytest.raises(ValueError):
        with claim(root,'new-after-crash'):pass
    active=json.loads((root/'active.json').read_text())
    assert active['state']=='running'


def test_ledger_is_private_and_bound_to_plan_runtime_and_report(tmp_path):
    root=tmp_path/'state'
    with claim(root)as attempt:
        row=attempt.finish(charged_worker_seconds=12.5,report_sha256='d'*64)
        assert row['plan_sha256']=='a'*64 and row['runtime_sha256']=='c'*64
        assert row['report_sha256']=='d'*64 and row['state']=='closed'
    for file in [root/'active.json',root/'controller.lock',*list((root/'runs').iterdir())]:
        assert file.stat().st_mode&0o777==0o600 and file.stat().st_nlink==1


def test_registry_refuses_symlink_alias_and_shared_leaf_directory(tmp_path):
    root=tmp_path/'state';root.mkdir(mode=0o755)
    with pytest.raises(ValueError):
        with claim(root):pass
    target=tmp_path/'private';target.mkdir(mode=0o700)
    alias=tmp_path/'alias';alias.symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError):
        with claim(alias):pass
