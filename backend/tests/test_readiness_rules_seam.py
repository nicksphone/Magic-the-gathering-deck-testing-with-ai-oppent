"""Green audit witnesses, not a mechanics certification or bugfix release gate."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import pickle
import sqlite3

import pytest
from card_data import hydration
from decks.builtin_decks import BUILTIN_DECKS
from decks.service import DeckService
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step, Zone
from rules_engine.ability_model import build_spell_spec
from rules_engine.cast_choice import build_cast_hints
from rules_engine.action_validation import ActionRejected
from rules_engine.continuous import effective_power, effective_toughness, effective_keywords
from rules_engine.coverage import deck_pair_coverage, static_coverage_details
from rules_engine.combat_constraints import combat_clause_coverage, combat_rule_view
from rules_engine.events import flush_staged_triggers
from rules_engine.engine import RulesEngine
from rules_engine.zone_actions import sacrifice_selected
from scripts import knowledge_engine_coverage as corpus_report
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import (
    FIXTURE, RAW, FAMILIES, add, canonical, cast, normalize, observation,
    position, resolve, resume, seed_cache,
)

TRACE = []


def sql_dump(repo):
    return list(repo.session.connection().connection.driver_connection.iterdump())


def test_fixture_hashes_and_real_builtin_membership():
    provenance = json.loads((FIXTURE/'provenance.json').read_text())
    assert provenance['canonical_sha256'] == hashlib.sha256((FIXTURE/'canonical.json').read_bytes()).hexdigest()
    assert provenance['facts_modified'] is False and provenance['http_requests'] == 0
    for family, names in FAMILIES.items():
        for name in names:
            raw = RAW[name]
            assert name.split(' // ')[0] in BUILTIN_DECKS[family]
            proof = provenance['rows'][name]
            assert proof['id'] == raw['id'] and proof['oracle_id'] == raw['oracle_id']
            assert proof['raw_sha256'] == hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            assert raw['object'] == 'card' and proof['source'] == raw['uri']


@pytest.mark.parametrize('name,expected', [
    ('Counterspell',False),('Fatal Push',False),('Clarion Spirit',True),
    ('Intangible Virtue',True),('Wedding Announcement // Wedding Festivity',True),
])
def test_missing_oracle_metadata_is_not_an_absence_of_printed_abilities(name,expected):
    complete = canonical(name)
    assert hydration.ready_for_match(complete)
    partial = deepcopy(complete)
    partial.pop('oracle_text',None)
    for face in partial.get('card_faces',[]):
        face.pop('oracle_text',None)
    assert hydration.ready_for_match(partial) is expected
    assert canonical(name)==complete  # Damaged-input control, never modified canonical Oracle.
    TRACE.append({'kind':'deliberately-missing-oracle-metadata','name':name,
                  'damaged_fields':'oracle_text removed from root and every face',
                  'metadata_ready':expected,'full_engine_certification':False,
                  'printed_ability_absence_inferred':False})


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('name', sum(FAMILIES.values(), []))
def test_metadata_compiler_and_known_gaps_are_separate_nonmutating_observations(seat,name):
    state = position(seat)
    source = add(state,name,seat,Zone.HAND)
    before = pickle.dumps(state)
    result = observation(state,source)
    assert pickle.dumps(state) == before
    assert result['metadata_ready'] is True and result['known_gaps'] == []
    assert result['execution_certified'] is False
    expected = {'Counterspell':'counter_spell','Fatal Push':'conditional_instruction',
                'Go for the Throat':'destroy_permanent','Drown in the Loch':'counter_spell',
                'Raise the Alarm':'create_token','Intangible Virtue':'noop',
                'Clarion Spirit':'create_token','Wedding Announcement // Wedding Festivity':'effect_sequence'}
    assert result['ability']['effect']['key'] == expected[name]
    assert result['ability']['used_fallback'] is False
    if name in FAMILIES['Tokens'] and name != 'Raise the Alarm':
        assert result['spell']['effect']['key'] == 'noop'
    if name == 'Drown in the Loch':
        assert len(result['ability']['modes']) == 2  # Default counter is not the chosen execution branch.
    TRACE.append({'kind':'compiler-vs-readiness', **result})


@pytest.mark.parametrize('seat', [1,2])
def test_counterspell_actual_checked_cast_and_snapshot_resolution(seat):
    state = position(3-seat)
    bear = add(state,'Grizzly Bears',3-seat,Zone.HAND)
    state = cast(state,bear)
    target = state.stack[-1].id
    state.priority_player = seat
    answer = add(state,'Counterspell',seat,Zone.HAND)
    state = resolve(resume(cast(state,answer,target_stack_id=target)))
    assert state.cards[bear.id].zone == state.cards[answer.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('departure', ['none','own','opponent'])
def test_fatal_push_full_revolt_clause_not_first_destroy_only(seat,departure):
    state = position(seat)
    target = add(state,'Brazen Borrower // Petty Theft',3-seat)
    if departure != 'none':
        resource = add(state,'Island',seat if departure=='own' else 3-seat)
        assert sacrifice_selected(state,resource.controller,[resource.id])
    source = add(state,'Fatal Push',seat,Zone.HAND)
    state = resolve(resume(cast(state,source,target_card_id=target.id)))
    assert state.cards[target.id].zone == (Zone.GRAVEYARD if departure=='own' else Zone.BATTLEFIELD)
    assert state.cards[source.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('mode', ['counter','destroy'])
@pytest.mark.parametrize('graveyard_count', [0,2])
def test_drown_selected_printed_mode_and_public_graveyard_criterion(seat,mode,graveyard_count):
    state = position(3-seat if mode=='counter' else seat)
    target = add(state,'Grizzly Bears',3-seat,Zone.HAND if mode=='counter' else Zone.BATTLEFIELD)
    if mode=='counter':
        state = cast(state,target)
        target_stack = state.stack[-1].id
        state.priority_player = seat
    for _ in range(graveyard_count):
        add(state,'Island',3-seat,Zone.GRAVEYARD)
    source = add(state,'Drown in the Loch',seat,Zone.HAND)
    lines = RAW[source.name]['oracle_text'].splitlines()[1:]
    index = 0 if mode=='counter' else 1
    text = build_cast_hints(state,source,seat)['modes'][index]
    assert text+'.' == lines[index].removeprefix(chr(8226)+' ')
    targets = {'mode_text':text, **({'target_stack_id':target_stack} if mode=='counter' else {'target_card_id':target.id})}
    before = pickle.dumps(state)
    if graveyard_count == 0:
        with pytest.raises(ActionRejected):
            cast(state,source,**targets)
        assert pickle.dumps(state) == before
    else:
        state = resolve(resume(cast(state,source,**targets)))
        assert state.cards[target.id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize('seat', [1,2])
def test_real_raise_and_static_virtue_not_noop_means_missing_static(seat):
    state = position(seat)
    virtue = add(state,'Intangible Virtue',seat,Zone.HAND)
    state = resolve(resume(cast(state,virtue)))
    source = add(state,'Raise the Alarm',seat,Zone.HAND)
    state = resolve(resume(cast(state,source)))
    tokens = [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(tokens) == 2
    assert all(c.name=='Soldier' and c.colors==['W'] for c in tokens)
    assert all(effective_power(state,c.id)==effective_toughness(state,c.id)==2 for c in tokens)
    assert all('vigilance' in effective_keywords(state,c.id) for c in tokens)


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('attackers', [0,2])
@pytest.mark.parametrize('prior_counters', [0,2])
def test_wedding_actual_end_step_continuation_vs_incomplete_generic_compiler(seat,attackers,prior_counters):
    state = position(seat)
    source = add(state,'Wedding Announcement // Wedding Festivity',seat)
    source.counters['invitation'] = prior_counters
    state.declared_attackers_this_turn[seat] = attackers
    generic = observation(state,source)['ability']['effect']
    assert [e['effect_key'] for e in generic['payload']['effects']] == ['draw_cards','create_token']
    # The real event compiler retains all printed continuation instructions.
    state.step = Step.POSTCOMBAT_MAIN
    before_hand = len(state.players[seat].hand)
    RulesEngine().next_step(state)
    flush_staged_triggers(state)
    assert len(state.stack)==1
    actual = deepcopy(state.stack[-1].payload)
    assert [e['effect_key'] for e in actual['effects']] == ['add_counters','attack_count_reward','transform_if_counters']
    state = resolve(resume(state))
    restored = state.cards[source.id]
    assert restored.counters['invitation'] == prior_counters+1
    assert len(state.players[seat].hand)-before_hand == (1 if attackers==2 else 0)
    tokens = [state.cards[cid] for cid in state.players[seat].battlefield if state.cards[cid].is_token]
    assert len(tokens) == (0 if attackers==2 else 1)
    assert restored.selected_face_index == (1 if prior_counters==2 else None)
    if prior_counters==2:
        assert restored.name=='Wedding Festivity'
    TRACE.append({'kind':'wedding-specialized-complete','seat':seat,'attackers':attackers,
                  'prior_counters':prior_counters,'generic_effect':generic,'actual_trigger':actual,
                  'local_golden_observed':True,'full_engine_certification':False})


@pytest.mark.parametrize('seat', [1,2])
def test_clarion_second_spell_bounded_runtime_regression(seat):
    state = position(seat)
    source = add(state,'Clarion Spirit',seat)
    diagnostics = observation(state,source)
    counts,stacks = [],[]
    for expected_cast_count in [1,2,3]:
        spell = add(state,'Intangible Virtue',seat,Zone.HAND)
        state = cast(state,spell)
        assert state.spells_cast_this_turn[seat] == expected_cast_count
        stacks.append([item.effect_key for item in state.stack])
        assert sum(item.source_card_id==source.id for item in state.stack) == (1 if expected_cast_count==2 else 0)
        state = resolve(resume(state))
        counts.append(sum(state.cards[cid].is_token for cid in state.players[seat].battlefield))
    assert counts == [0,1,1]
    assert diagnostics['metadata_ready'] and diagnostics['known_gaps']==[]
    assert diagnostics['ability']['effect']['key']=='create_token' and not diagnostics['ability']['used_fallback']
    assert not any('unsupported' in line.lower() or 'not inferred' in line.lower() for line in state.log)
    TRACE.append({'kind':'clarion-bounded-execution','full_engine_certification':False,'seat':seat,'printed_trigger':RAW['Clarion Spirit']['oracle_text'],
                  'actual_cast_counts':[1,2,3],'actual_token_counts':counts,'printed_expected_token_counts':[0,1,1],
                  'actual_stack_keys':stacks,'diagnostics':diagnostics,'snapshot_resumed_each_cast':True})


@pytest.mark.parametrize('seat', [1,2])
@pytest.mark.parametrize('family', list(FAMILIES))
def test_actual_http_admission_preflight_and_public_root_diagnostics_parity(repo,client,seat,family):
    import main
    seed_cache(repo)
    p = DeckService(repo).parser.parse(BUILTIN_DECKS[family])
    canonical_board = hydration.hydrate_deck_cards(repo,p.mainboard)
    assert all(hydration.ready_for_match(c) for c in canonical_board)
    receipt = client.post('/decks/import',json={'name':family,'deck_text':BUILTIN_DECKS[family]})
    assert receipt.status_code==200 and receipt.json()['classification_status']=='resolved'
    boards = {'deck_a':p.mainboard,'deck_b':p.mainboard}
    before_db = sql_dump(repo)
    preflight = client.post('/simulate/batch/preflight',json=boards)
    assert preflight.status_code==200 and preflight.json()==deck_pair_coverage(canonical_board,canonical_board)
    assert preflight.json()['status']=='exploratory' and sql_dump(repo)==before_db
    started = client.post('/matches/start',json={**boards,'controller_a':'human','controller_b':'human','seed':6214})
    assert started.status_code==200,started.text
    controller = main.ACTIVE_MATCHES[started.json()['id']]
    state = position(seat); state.id = controller.state.id
    for name in FAMILIES[family]:
        add(state,name,seat,Zone.HAND if family=='Dimir Control' else Zone.BATTLEFIELD)
    controller.state = state
    main._persist_active_match(repo,controller)
    before = pickle.dumps(state),deepcopy(main._controller_snapshot(controller)),sql_dump(repo)
    response = client.get('/matches/'+state.id+'/rules-diagnostics')
    assert response.status_code==200,response.text
    for item in response.json()['cards']:
        card = state.cards[item['card_id']]
        view = combat_rule_view(state,card.id)
        assert item['active_combat_constraints']==view['active'] and item['unresolved_combat_constraints']==view['unsupported']
        assert item['printed_static_coverage_gaps']==static_coverage_details(card.oracle_text,card_name=card.name)
        assert item['printed_combat_coverage_gaps']==combat_clause_coverage(card.oracle_text,card.name)
    public = client.get('/matches/'+state.id).json()
    assert all('library' not in player for player in public['players'].values())
    assert client.get('/matches/'+state.id+'/debug/ai-hands').status_code==403
    assert (pickle.dumps(state),deepcopy(main._controller_snapshot(controller)),sql_dump(repo))==before
    TRACE.append({'kind':'http-readiness-parity','seat':seat,'family':family,
                  'import_admission':receipt.json()['classification_status'],
                  'actual_analysis':receipt.json()['analysis'],
                  'classification_provenance':receipt.json()['classification_provenance'],
                  'preflight':preflight.json(),
                  'rules_diagnostics':response.json(),'root_rng_database_receipts_unchanged':True})


def test_canonical_corpus_report_remains_unknown_not_engine_certificate(tmp_path):
    path = tmp_path/'seam-report.sqlite'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE cardknowledge (id INTEGER PRIMARY KEY,name TEXT,scryfall_id TEXT,oracle_source TEXT,profiles_json TEXT)')
        for names in FAMILIES.values():
            for name in names:
                raw = RAW[name]
                conn.execute('INSERT INTO cardknowledge(name,scryfall_id,oracle_source,profiles_json) VALUES (?,?,?,?)',
                    (name,raw['id'],'scryfall',json.dumps({'oracle_id':raw['oracle_id'],'card_data':raw})))
    before = path.read_bytes()
    with corpus_report.closing(corpus_report.corpus.readonly(path)) as conn:
        result = corpus_report.coverage_report(conn,examples=1)
    assert path.read_bytes()==before
    assert result['totals']['canonical_identity_cards']==8
    assert result['totals']['no_known_gap_not_certified_cards']==8
    assert result['rules_support_certified'] is False and result['mechanics']['supported']['cards'] is None
    assert result['trained_competence']=='unknown' and result['database_writes']==0
    TRACE.append({'kind':'canonical-corpus-report', 'report':result})


@pytest.mark.parametrize('seat', [1,2])
def test_actual_http_second_spell_bounded_execution_matches_settled_helper(repo,client,seat):
    import main
    seed_cache(repo)
    deck = [{'card_name':'Island','quantity':8}]
    response = client.post('/matches/start',json={'deck_a':deck,'deck_b':deck,'sandbox':True,
        'controller_a':'human','controller_b':'human','seed':6214})
    assert response.status_code==200,response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state = position(seat); state.id = controller.state.id
    spirit = add(state,'Clarion Spirit',seat)
    spells = [add(state,'Intangible Virtue',seat,Zone.HAND) for _ in range(2)]
    controller.state = state
    main._persist_active_match(repo,controller)
    counts = []
    statuses = []
    for index,spell in enumerate(spells,start=1):
        response = client.post('/matches/'+state.id+'/action',json={'player_id':seat,
            'action':{'type':'cast_spell','card_id':spell.id,'targets':{}}})
        statuses.append(response.status_code)
        assert response.status_code==200,response.text
        state = controller.state
        assert state.spells_cast_this_turn[seat]==index
        assert sum(item.source_card_id==spirit.id for item in state.stack) == (1 if index==2 else 0)
        # Resolve only an independent snapshot for helper/API settled-result parity.
        original = pickle.dumps(state)
        predicted = resolve(resume(state))
        assert pickle.dumps(state)==original
        for _ in range(10):
            if not controller.state.stack:
                break
            response = client.post('/matches/'+state.id+'/action',json={
                'player_id':controller.state.priority_player,'action':{'type':'pass_priority'}})
            assert response.status_code==200,response.text
        else:
            pytest.fail('Bounded actual HTTP stack did not settle')
        state = controller.state
        actual = sum(state.cards[cid].is_token for cid in state.players[seat].battlefield)
        expected_helper = sum(predicted.cards[cid].is_token for cid in predicted.players[seat].battlefield)
        assert actual==expected_helper==(1 if index==2 else 0)
        counts.append(actual)
    original = pickle.dumps(state),deepcopy(main._controller_snapshot(controller)),sql_dump(repo)
    diagnostics = client.get('/matches/'+state.id+'/rules-diagnostics')
    assert diagnostics.status_code==200
    row = next(row for row in diagnostics.json()['cards'] if row['card_id']==spirit.id)
    assert row['printed_static_coverage_gaps']==row['printed_combat_coverage_gaps']==[]
    assert (pickle.dumps(state),deepcopy(main._controller_snapshot(controller)),sql_dump(repo))==original
    assert counts==[0,1]
    TRACE.append({'kind':'actual-http-clarion-bounded-execution','full_engine_certification':False,'seat':seat,'cast_statuses':statuses,
                  'actual_token_counts':counts,'printed_expected_token_counts':[0,1],
                  'helper_settled_parity':True,'public_diagnostic_row':row,
                  'root_rng_database_receipts_unchanged_by_diagnostics':True})


def teardown_module():
    path = os.environ.get('MTG_READINESS_SEAM_TRACE')
    if path:
        Path(path).write_text(json.dumps(TRACE,indent=2,sort_keys=True)+'\n')
