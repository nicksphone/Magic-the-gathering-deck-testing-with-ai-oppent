"""PREP ONLY: 77 NEW desired diagnostics; do not collect before scoped grant.
Synthetic altered copies are grammar controls, never canonical/paid claims.
"""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from rules_engine.coverage import known_unsupported_mechanics
from rules_engine.continuous import conditional_static_clause_coverage
from rules_engine.counter_placement import unsupported_counter_prohibitions

ROOT = Path(__file__).resolve().parents[1]
CARDS = json.loads((ROOT/'gap6/canonical-six.json').read_bytes())['cards']
LABELS = {
    'Archangel of Wrath': {'kicker'}, 'Springheart Nantuko': {'bestow'},
    'Suncleanser': {'unsupported conditional static instruction', 'unsupported conditional static predicate', 'unsupported counter prohibition'},
    'The Wandering Emperor': {'unsupported conditional static instruction', 'unsupported conditional static predicate'},
    'Veil of Summer': {'keyword counter variant fidelity'},
    'Volatile Stormdrake': {'keyword counter variant fidelity'},
}
TAILS = ['\nThen perform an unspecified operation.', ' Then perform an unspecified operation.',
         ' (Then perform an unspecified operation.)', '\nWhenever an unspecified event occurs, perform an unspecified operation.',
         '\nAs long as an unspecified condition holds, perform an unspecified operation.']

def diagnostic(raw, faces=None, context=True):
    return set(known_unsupported_mechanics(raw['oracle_text'], faces, card_name=raw['name'],
                                           canonical_context=raw if context else None))

@pytest.mark.parametrize('name', sorted(CARDS))
def test_desired_closed_canonical_label_parity(name):
    raw = deepcopy(CARDS[name]['canonical'])
    assert not diagnostic(raw).intersection(LABELS[name])

@pytest.mark.parametrize('name', sorted(CARDS))
def test_generic_renamed_full_grammar_not_name_allowlist(name):
    raw = deepcopy(CARDS[name]['canonical'])
    raw['name']='Declared Grammar Variant'
    raw['oracle_text']=raw['oracle_text'].replace(name,raw['name'])
    assert not diagnostic(raw).intersection(LABELS[name])

@pytest.mark.parametrize('name', sorted(CARDS))
@pytest.mark.parametrize('tail', TAILS)
def test_unknown_complete_suffix_keeps_original_label(name, tail):
    raw = deepcopy(CARDS[name]['canonical']);raw['oracle_text']+=tail
    assert LABELS[name].issubset(diagnostic(raw))

@pytest.mark.parametrize('name', sorted(CARDS))
def test_mixed_unknown_face_never_inherits_root_clear(name):
    raw = deepcopy(CARDS[name]['canonical'])
    face={'name':name,'oracle_text':raw['oracle_text']+TAILS[0]}
    raw['card_faces']=[face]
    assert LABELS[name].issubset(diagnostic(raw,[face]))

@pytest.mark.parametrize('name', ['Archangel of Wrath','Springheart Nantuko','Veil of Summer','Volatile Stormdrake'])
@pytest.mark.parametrize('variant', ['missing-context','wrong-type'])
def test_typed_family_unknown_metadata_retains_label(name, variant):
    raw=deepcopy(CARDS[name]['canonical'])
    if variant=='wrong-type':raw['type_line']='Land'
    assert LABELS[name].issubset(diagnostic(raw,context=variant!='missing-context'))

@pytest.mark.parametrize('name', ['Suncleanser','The Wandering Emperor'])
@pytest.mark.parametrize('case', ['canonical',0,1,2,3,4,'empty'])
def test_conditional_static_owner_delegation_exact_body(name, case):
    raw=CARDS[name]['canonical'];text=raw['oracle_text']
    if case=='empty':text=''
    elif isinstance(case,int):text+=TAILS[case]
    result=conditional_static_clause_coverage(text,name)
    assert bool(result)==isinstance(case,int)

@pytest.mark.parametrize('case', ['canonical',0,1,2,3,4,'empty'])
def test_modal_counter_prohibition_owner_delegation_exact_body(case):
    text=CARDS['Suncleanser']['canonical']['oracle_text']
    if case=='empty':text=''
    elif isinstance(case,int):text+=TAILS[case]
    assert unsupported_counter_prohibitions(text) is isinstance(case,int)
