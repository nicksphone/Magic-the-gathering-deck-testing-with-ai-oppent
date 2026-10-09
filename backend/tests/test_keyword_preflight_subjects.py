"""Compiler-only subject goldens, not fabricated paid card bodies."""
from dataclasses import asdict
import json
import os

import pytest
import test_suncleanser_desired as s
from rules_engine.ability_model import build_ability_spec

facts = s.facts


@pytest.mark.parametrize('case', ['target-unbound', 'orphan-it', 'bound-it', 'self-source'])
def test_complete_keyword_subject_binding_preserves_orphan_boundary(facts, case):
    state = s.g.position(facts, 1)
    source = s.g.add(state, facts, 'Sylvan Safekeeper', 1)
    target = s.g.add(state, facts, 'Monastery Swiftspear', 1)
    body = {'target-unbound': 'Target creature you control gains shroud until end of turn.',
            'orphan-it': 'It gains shroud until end of turn.',
            'bound-it': 'It gains shroud until end of turn.',
            'self-source': 'This creature gains shroud until end of turn.'}[case]
    targets = {'target_card_id': target} if case == 'bound-it' else {}
    proxy = type('CompilerGrammarProxy', (), {'id': source, 'name': state.cards[source].name,
                 'mana_cost': '', 'oracle_text': body})()
    before = s.serialize_match_snapshot(state)
    spec = build_ability_spec(state, proxy, 1, targets, report_unsupported=False)
    assert s.serialize_match_snapshot(state) == before
    phase = os.environ.get('ADMISSION_PHASE')
    if phase:
        with (s.OUT / (phase + '-' + case + '.json')).open('x') as stream:
            json.dump({'compiler_only': True, 'body': body, 'targets': targets,
                       'spec': asdict(spec), 'source': source, 'target': target}, stream, indent=2, sort_keys=True)
    if case == 'orphan-it':
        assert spec.effect.key == 'noop'
        assert spec.used_fallback
    else:
        assert spec.effect.key == 'grant_keyword'
        assert spec.effect.payload['keyword'] == 'shroud'
        assert spec.effect.payload['until_end_of_turn'] is True
        assert spec.effect.payload['target_card_id'] == {
            'target-unbound': None, 'bound-it': target, 'self-source': source}[case]
