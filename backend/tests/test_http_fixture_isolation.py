"""Owned-fixture isolation, import configuration and lifetime regression checks."""
import pytest

import main as shared_main
from persistence.capacity import CapacityAdmissionClosed, owner_for_engine
from tests import test_browser_origin_http as browser
from tests.test_browser_origin_http import supported_match
from tests.test_temporary_characteristics_http import file_api
from tests.temporary_characteristics_http_fixture import source_lease


SHARED_ORIGINS = shared_main.TRUSTED_BROWSER_ORIGINS


def test_explicit_browser_app_does_not_broaden_shared_app(supported_match):
    assert browser.main is not shared_main
    assert browser.main.app is not shared_main.app
    assert shared_main.TRUSTED_BROWSER_ORIGINS == SHARED_ORIGINS
    assert browser.main.TRUSTED_BROWSER_ORIGINS == (
        browser.PRODUCTION, browser.DEVELOPMENT, browser.LOOPBACK)


def test_owned_file_has_native_owner_and_closes_before_reuse(file_api):
    owner = owner_for_engine(file_api.engine)
    assert owner.path == file_api.path and owner.ready and owner.admissions_open
    assert owner.engine.pool is owner.pool
    file_api.close()
    assert owner.fd is None and not owner.producers
    with pytest.raises(CapacityAdmissionClosed):
        owner_for_engine(file_api.engine)


def test_source_lease_rejects_an_unapproved_source(monkeypatch, tmp_path):
    monkeypatch.setenv('MTG_ISOLATED_TEST_ROOT', str(tmp_path))
    with pytest.raises(AssertionError):
        source_lease()
