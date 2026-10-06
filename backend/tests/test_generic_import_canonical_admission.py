"""Desired canonical admission; frozen current-behavior audit stays unchanged."""
from copy import deepcopy
import hashlib
import json
import os
import pickle
from pathlib import Path

import pytest
from ai.action_contract import complete_action
from ai.agent import AIAgent
from ai.deck_analysis import analyze_deck
from ai.information import decision_view, is_unknown
from card_data import hydration
from decks import service as service_module
from decks.service import DeckService
from decks.builtin_decks import BUILTIN_DECKS
from decks.expansion_top_decks import EXPANSION_TOP_DECKS
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from tests.test_builtin_metadata_refresh import repo, rows, seed_cache
from tests.generic_import_fixtures import client, parsed, card_rows, observed_admission, FAMILIES

TRACE = []


def assert_classification(result, canonical):
    observation = observed_admission(canonical)
    assert result['analysis'] == observation['actual_analysis']
    expected = result['analysis']['primary_archetype'] if observation['canonical_complete'] else 'unknown'
    assert result['archetype_guess'] == expected
    assert result['classification_status'] == ('resolved' if observation['canonical_complete'] else 'unknown')
    provenance = result['classification_provenance']
    assert provenance['method'] == 'ai.deck_analysis.analyze_deck'
    assert provenance['facts_method'] == 'card_data.hydration.hydrate_deck_cards'
    assert provenance['admission'] == 'complete-local-canonical-v1'
    assert provenance['sources'] == observation['sources']
    assert provenance['resolved_board_sha256'] == hashlib.sha256(json.dumps(canonical,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()
    assert provenance['cards'] == [{'card_name':c['card_name'],'sources':c['card_data_sources'],
        'ready_for_match':bool(hydration.ready_for_match(c))} for c in canonical]
    return observation


@pytest.mark.parametrize('name,expected', FAMILIES)
@pytest.mark.parametrize('mode', ['offline','cache','missing','partial_oracle'])
def test_generic_import_actual_canonical_admission_and_legacy_display(repo, client, monkeypatch, name, expected, mode):
    p = parsed(repo,name)
    original_facts = hydration.hydrate_deck_cards(None,p.mainboard)
    existing = [repo.save_deck(name,s,p.mainboard,p.sideboard,analyze_deck(original_facts)['primary_archetype'])
                for s in ['builtin','user','file']]
    if mode in {'cache','partial_oracle'}:
        seed_cache(repo,p.mainboard+p.sideboard)
    if mode != 'offline':
        monkeypatch.setattr(hydration,'fallback_card_payload',lambda _:None)
    if mode == 'partial_oracle':
        target = 'Lightning Bolt' if name == 'Burn' else 'Counterspell'
        row = repo.get_cached_card_by_name(target)
        assert row
        row.oracle_text = ''
        repo.session.commit()
    legacy = DeckService(repo)
    legacy_main,legacy_side = legacy._resolve_card_metadata(p.mainboard),legacy._resolve_card_metadata(p.sideboard)
    before,before_cards = rows(repo),card_rows(repo)
    results = []
    for _ in range(2):
        response = client.post('/decks/import',json={'name':name,'source':'user','deck_text':BUILTIN_DECKS[name]})
        assert response.status_code == 200,response.text
        result = response.json()
        assert not result['errors']
        canonical = hydration.hydrate_deck_cards(repo,p.mainboard)
        observation = assert_classification(result,canonical)
        assert result['mainboard'] == p.mainboard and result['sideboard'] == p.sideboard
        assert result['resolved_mainboard_cards'] == legacy_main
        assert result['resolved_sideboard_cards'] == legacy_side
        assert result['mana_curve'] == legacy._compute_curve(legacy_main)
        assert result['color_profile'] == legacy._color_profile(legacy_main)
        assert rows(repo)[result['deck_id']]['archetype_guess'] == result['archetype_guess']
        results.append(result)
    assert results[0]['deck_id'] != results[1]['deck_id']
    assert results[0]['classification_provenance'] == results[1]['classification_provenance']
    assert set(rows(repo)) == set(before) | {r['deck_id'] for r in results}
    assert all(rows(repo)[rid] == old for rid,old in before.items())
    assert card_rows(repo) == before_cards
    listed = client.get('/decks')
    assert listed.status_code == 200
    visible = [r for r in listed.json() if r['name']==name and r['source']=='user']
    assert len(visible) == 1 and visible[0]['id']==results[-1]['deck_id']
    assert visible[0]['archetype_guess']==results[-1]['archetype_guess']
    analysis = client.post('/decks/analyze',json={'deck':p.mainboard})
    start = client.post('/matches/start',json={'deck_a':p.mainboard,'deck_b':p.mainboard,
        'deck_a_id':results[0]['deck_id'],'deck_b_id':results[1]['deck_id'],
        'controller_a':'human','controller_b':'human','seed':419})
    if mode in {'offline','cache'}:
        assert results[-1]['archetype_guess'] == expected
        assert analysis.status_code == start.status_code == 200
        assert analysis.json() == results[-1]['analysis']
        import main
        match = main.ACTIVE_MATCHES[start.json()['id']]
        profiles = [{'seat':seat,'own':ai.archetype,'opponent':ai.opponent_archetype,
                     'profile':deepcopy(ai.matchup_profile)} for seat,ai in match.ai.items()]
        assert all(a['own']==a['opponent']==expected for a in profiles)
    else:
        assert results[-1]['archetype_guess']=='unknown'
        assert analysis.status_code == start.status_code == 422
        assert analysis.json()['detail']['code'] == start.json()['detail']['code'] == 'card_data_unavailable'
        if mode=='missing':
            assert results[-1]['analysis']['confidence']==0
        else:
            assert results[-1]['analysis']['confidence']>0 and results[-1]['analysis']['type_metadata_coverage']==1
        profiles = []
    assert all(rows(repo)[rid] == old for rid,old in before.items())
    TRACE.append({'kind':'desired-import','name':name,'mode':mode,'results':results,
        'canonical_observation':observation,'actual_constructed_profiles':profiles,
        'analyze_status':analysis.status_code,'start_status':start.status_code,
        'preserved_ids':[r.id for r in existing],'legacy_display_preserved':True,'history_preserved':True})


@pytest.mark.parametrize('failure',['confidence','signal'])
def test_canonical_facts_do_not_override_unknown_admission_certificate(repo,client,monkeypatch,failure):
    actual = service_module.analyze_deck
    def uncertified(deck):
        result = actual(deck)
        return {**result,'confidence':0} if failure=='confidence' else {**result,'signals':result['signals']+['fallback_midrange']}
    monkeypatch.setattr(service_module,'analyze_deck',uncertified)
    result = client.post('/decks/import',json={'name':'Burn','deck_text':BUILTIN_DECKS['Burn']}).json()
    assert result['deck_id'] and result['classification_status']=='unknown' and result['archetype_guess']=='unknown'
    assert rows(repo)[result['deck_id']]['archetype_guess']=='unknown'


def test_parser_validation_still_blocks_invalid_inventory(repo,client):
    p = parsed(repo,'Burn')
    old = repo.save_deck('Burn','user',p.mainboard,p.sideboard,analyze_deck(hydration.hydrate_deck_cards(None,p.mainboard))['primary_archetype'])
    before = rows(repo)
    result = client.post('/decks/import',json={'name':'Burn','deck_text':'4 Lightning Bolt'}).json()
    assert result['deck_id'] is None and result['errors'] and rows(repo)==before and old.id in before
    assert result['mainboard']==[{'card_name':'Lightning Bolt','quantity':4}]


def test_real_catalog_sideboard_and_upsert_identity_are_preserved(repo,client):
    item = next(i for i in EXPANSION_TOP_DECKS if 'Sideboard:' in i['deck_text'])
    p = DeckService(repo).parser.parse(item['deck_text'])
    assert not p.errors and p.sideboard
    source = 'expansion_top:'+item['code'].lower()
    before = rows(repo)
    results = [client.post('/decks/import',json={'name':item['deck_name'],'source':source,'deck_text':item['deck_text']}).json()
               for _ in range(2)]
    assert all(not r['errors'] and r['mainboard']==p.mainboard and r['sideboard']==p.sideboard for r in results)
    assert results[0]['deck_id']==results[1]['deck_id']
    assert set(rows(repo))==set(before)|{results[0]['deck_id']}
    assert all(rows(repo)[rid]==value for rid,value in before.items())
    assert_classification(results[-1],hydration.hydrate_deck_cards(repo,p.mainboard))
@pytest.mark.parametrize('controllers', [('human','ai'), ('ai','human')])
@pytest.mark.parametrize('import_mode', ['offline', 'missing'])
def test_canonical_import_preserves_existing_actual_ai_root_private_views_and_restart(repo, client, monkeypatch, controllers, import_mode):
    import main
    entries = [parsed(repo,n) for n,_ in FAMILIES]
    for p in entries:
        seed_cache(repo,p.mainboard+p.sideboard)
    existing = [repo.save_deck(name,'user',p.mainboard,p.sideboard,
                analyze_deck(hydration.hydrate_deck_cards(repo,p.mainboard))['primary_archetype'])
                for (name,_),p in zip(FAMILIES,entries)]
    constructors, decisions = [], []
    original_init, original_choose = AIAgent.__init__, AIAgent.choose_action
    def init(self,*a,**k):
        original_init(self,*a,**k)
        constructors.append({'own':self.archetype,'opponent':self.opponent_archetype,'profile':deepcopy(self.matchup_profile)})
    def choose(self,state,moves,seat):
        root = pickle.dumps(state,5)
        private,_ = decision_view(state,seat,moves)
        assert set(private.starting_decks) == {seat}
        hidden = state.players[3-seat].hand + state.players[1].library + state.players[2].library
        assert all(is_unknown(private.cards[cid]) and not private.cards[cid].name for cid in hidden)
        picked = original_choose(self,state,moves,seat)
        action = complete_action(picked.action)
        checked_action(deepcopy(state),self.engine,seat,deepcopy(action))
        assert pickle.dumps(state,5) == root
        decisions.append({'seat':seat,'action':action,'reasoning':picked.reasoning,'root_unchanged':True,'checked_legal':True})
        return picked
    monkeypatch.setattr(AIAgent,'__init__',init)
    monkeypatch.setattr(AIAgent,'choose_action',choose)
    payload = {'deck_a':entries[0].mainboard,'deck_b':entries[1].mainboard,
        'deck_a_id':existing[0].id,'deck_b_id':existing[1].id,'controller_a':controllers[0],
        'controller_b':controllers[1],'seed':421,'ai_difficulty':'master'}
    response = client.post('/matches/start',json=payload,headers={'Idempotency-Key':'existing-root'})
    assert response.status_code == 200,response.text
    mid = response.json()['id']; match = main.ACTIVE_MATCHES[mid]
    assert [c['own'] for c in constructors] == ['Burn','Control']
    actor = main._default_player_for_state(match)
    if match.controllers[actor] == 'human':
        response = client.post(f'/matches/{mid}/action',json={'player_id':actor,'action':{'type':'keep_hand'}})
        assert response.status_code == 200,response.text
    response = client.post(f'/matches/{mid}/autoplay',params={'ticks':1})
    assert response.status_code == 200 and decisions
    root = pickle.dumps(match.state,5)
    saved = serialize_match_snapshot(match.state)
    config = deepcopy(main._controller_snapshot(match))
    inventory = deepcopy((match.mainboards,match.sideboards,match.deck_ids))
    # Prepare a genuinely empty cache after the active match has been established.
    for row in repo.list_cards():
        repo.session.delete(row)
    repo.session.commit()
    if import_mode == 'missing':
        monkeypatch.setattr(hydration,'fallback_card_payload',lambda _:None)
    before, before_cards = rows(repo), card_rows(repo)
    before_ctors, before_decisions = len(constructors),len(decisions)
    imported = client.post('/decks/import',json={'name':'Burn','source':'user','deck_text':BUILTIN_DECKS['Burn']})
    assert imported.status_code == 200 and not imported.json()['errors']
    expected = 'Burn' if import_mode == 'offline' else 'unknown'
    assert imported.json()['archetype_guess'] == expected
    assert imported.json()['classification_status'] == ('resolved' if import_mode == 'offline' else 'unknown')
    new_id = imported.json()['deck_id']
    assert new_id not in before and set(rows(repo)) == set(before) | {new_id}
    assert all(rows(repo)[rid] == value for rid,value in before.items())
    assert pickle.dumps(match.state,5) == root
    assert main._controller_snapshot(match) == config
    assert (match.mainboards,match.sideboards,match.deck_ids) == inventory
    assert len(constructors) == before_ctors and len(decisions) == before_decisions
    assert card_rows(repo) == before_cards == []
    main.ACTIVE_MATCHES.pop(mid)
    restored = client.post('/matches/start',json=payload,headers={'Idempotency-Key':'existing-root'})
    assert restored.status_code == 200,restored.text
    assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == saved
    assert main._controller_snapshot(main.ACTIVE_MATCHES[mid]) == config
    assert all(rows(repo)[rid] == value for rid,value in before.items())
    TRACE.append({'kind':'desired-active-root-preservation','controllers':controllers,'import_mode':import_mode,
        'original_constructors':constructors[:before_ctors],'original_actual_decisions':decisions[:before_decisions],
        'import_response':imported.json(),'prior_ids':[r.id for r in existing],'new_id':new_id,
        'full_pickle_root_unchanged':True,'private_views_checked':True,'complete_action_checked_legal':True,
        'restart_complete_state_and_config_equal':True,'old_rows_unchanged':True})



@pytest.fixture(scope='module',autouse=True)
def trace():
    yield
    path = os.environ.get('MTG_GENERIC_FIX_TRACE')
    if path:
        Path(path).write_text(json.dumps({'schema_version':1,'cases':TRACE},indent=2)+'\n')
