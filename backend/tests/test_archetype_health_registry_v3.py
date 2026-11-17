"""Role-specific charges and real temp-file locking, never a live registry."""
import json
import pytest
from scripts.archetype_registry_v3 import claim_run


def claim(root,kind,name):
    return claim_run(root,kind=kind,run_id=f'archetype-{kind}-20261116-v3-{name}',
                     plan_sha256='a'*64,revision='b'*40,runtime_sha256='c'*64,output=str(root.parent/name))


def test_health_keeps_prior_pilot_charges_and_carries_its_own_role_total(tmp_path):
    root=tmp_path/'state'
    with claim(root,'pilot','pilot')as c:c.finish(charged_worker_seconds=17310.,report_sha256=None)
    with claim(root,'health','health')as c:
        assert c.prior_charged_seconds==17310 and c.prior_health_charged_seconds==0
        with pytest.raises(ValueError):
            with claim(root,'pilot','concurrent'):pass
        row=c.finish(charged_worker_seconds=100.,report_sha256='d'*64)
    assert row['kind']=='health' and row['charged_campaign_worker_seconds']==17410
    assert row['charged_health_worker_seconds']==100 and row['remaining_health_worker_seconds']==107900
    assert row['remaining_campaign_worker_seconds']==172800-17410
    with claim(root,'health','next')as c:
        assert c.prior_health_charged_seconds==100
        c.finish(charged_worker_seconds=25.,report_sha256=None)
    with pytest.raises(FileExistsError):
        with claim(root,'health','health'):pass
    assert json.loads((root/'active.json').read_text())['charged_health_worker_seconds']==125


def test_legacy_closed_pilot_record_remains_compatible_without_resetting_charges(tmp_path):
    root=tmp_path/'state'
    # Existing pilot API, no kind parameter supplied.
    with claim_run(root,run_id='archetype-pilot-20261116-v3-previous',plan_sha256='a'*64,
                   revision='b'*40,runtime_sha256='c'*64,output=str(tmp_path/'old'))as c:
        c.finish(charged_worker_seconds=10.,report_sha256=None)
    path=root/'active.json';old=json.loads(path.read_text())
    for k in ('kind','charged_health_worker_seconds','remaining_health_worker_seconds','health_budget_exceeded'):
        old.pop(k,None)
    path.write_text(json.dumps(old))
    with claim(root,'health','new')as c:
        assert c.prior_charged_seconds==10 and c.prior_health_charged_seconds==0
        c.finish(charged_worker_seconds=20.,report_sha256=None)


@pytest.mark.parametrize('bad',['health_charge_missing','health_charge_bool','health_exceeds_campaign'])
def test_invalid_prior_health_accounting_cannot_reset_role_cap(tmp_path,bad):
    root=tmp_path/'state'
    with claim(root,'health','first')as c:c.finish(charged_worker_seconds=10.,report_sha256=None)
    path=root/'active.json';row=json.loads(path.read_text())
    if bad=='health_charge_missing':row.pop('charged_health_worker_seconds')
    elif bad=='health_charge_bool':row['charged_health_worker_seconds']=False
    else:row['charged_health_worker_seconds']=11.
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError):
        with claim(root,'health','second'):pass
    assert not(root/'runs/archetype-health-20261116-v3-second.json').exists()


def test_health_unproven_closure_blocks_both_roles_and_never_removes_lock(tmp_path):
    root=tmp_path/'state'
    with claim(root,'health','lost'):pass
    for kind in ('health','pilot'):
        with pytest.raises(ValueError):
            with claim(root,kind,'later'):pass
    assert (root/'controller.lock').exists()


@pytest.mark.parametrize('kind,name',[('health','archetype-pilot-20261116-v3-test'),
                                      ('pilot','archetype-health-20261116-v3-test'),
                                      ('matrix','archetype-matrix-20261116-v3-test')])
def test_role_and_id_cannot_be_substituted_before_registry_creation(tmp_path,kind,name):
    with pytest.raises(ValueError):
        with claim_run(tmp_path/'state',kind=kind,run_id=name,plan_sha256='a'*64,
                       revision='b'*40,runtime_sha256='c'*64,output=str(tmp_path/'out')):pass
    assert not(tmp_path/'state').exists()
