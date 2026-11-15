"""Snapshot compatibility need not initialize storage or executable effect handlers."""
import builtins
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from tests.stage_metadata import mark as _stage_metadata


def _fresh_public_module(monkeypatch, name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _mark_import_boundary(request, stage):
    _stage_metadata(stage)


def test_snapshot_compatibility_imports_defer_unused_storage_and_effect_owners(monkeypatch, request):
    backend = Path(__file__).resolve().parents[1]
    imported = set()
    original_import = builtins.__import__

    def observe_import(name, *args, **kwargs):
        if name in {'knowledge.models', 'effects.registry'}:
            imported.add(name)
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as observed:
        observed.setattr(builtins, '__import__', observe_import)
        package = _fresh_public_module(monkeypatch, '_snapshot_knowledge_package',
                                       backend / 'knowledge/__init__.py')
        profiles = _fresh_public_module(monkeypatch, '_snapshot_knowledge_profiles',
                                        backend / 'knowledge/profiles.py')
    _mark_import_boundary(request, 'KnowledgeSnapshotImportsMustDeferUnusedOwners')
    assert not imported, 'KnowledgeSnapshotImportsMustDeferUnusedOwners'

    _mark_import_boundary(request, 'KnowledgeSnapshotImportsDeferredOwnersReached')
    from knowledge.models import CardKnowledge
    assert package.__all__ == ['CardKnowledge']
    assert 'CardKnowledge' in dir(package)
    assert package.CardKnowledge is CardKnowledge
    assert package.CardKnowledge is package.CardKnowledge
    with pytest.raises(AttributeError):
        getattr(package, 'missing_knowledge_export')

    # Route derivation still uses the real registry and the full archived printing.
    printing = Path(__file__).parent / 'fixtures/battle_cast_full_printing/natures-spiral-dom-175.json'
    raw = json.loads(printing.read_text())
    derived = profiles.derive_profile(raw)
    assert derived.answer_routes == (profiles.AnswerRoute('counter_spell', 'stack', True, (
        'actual_effect_target_domain_and_current_rules_must_be_checked', 'object_is_genuine_spell')),)
