"""Full-RAW/first-consumer witnesses; original HTTP module is NOT executed here."""
import ast
from copy import deepcopy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_card_view, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone, _infer_keywords
from rules_engine import combat
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine

FIXTURES=Path(__file__).parent/'fixtures'
SOURCE=FIXTURES/'combat_assignment022/SOURCES.json'
SOURCE_SHA='7490f45d3924dcdf8362e69e6cf74eb81a8cfbcbc8c6ab887bfc7ce2f166a618'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
SOURCES=json.loads(SOURCE.read_text())


def official(name):
    row=SOURCES[name];data=(FIXTURES/row['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==row['file_sha256']
    raw=json.loads(data.splitlines()[row['line']-1] if row['line'] else data)
    for key in row['steps']:raw=raw[key]
    assert hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==row['object_sha256']
    assert raw['id']==row['id'] and raw['oracle_id']==row['oracle_id'] and raw['name']==name
    return raw


CREATURES=tuple(name for name in sorted(SOURCES) if 'Creature' in official(name)['type_line'])


def damage_construction():
    # Execute only actual source construction/helpers and this one pure scenario,
    # not module imports/main/HTTP. This is not whole-module qualification.
    path=Path(__file__).with_name('test_combat_damage_assignment.py')
    tree=ast.parse(path.read_text())
    names={'_state','_creature','_enter_damage','_finish_shared_blocker_choice',
           'test_trample_assignment_to_planeswalker_reduces_loyalty'}
    nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    ns=dict(__file__=str(path),CardInstance=CardInstance,MatchFactory=MatchFactory,Step=Step,Zone=Zone,
            RulesEngine=RulesEngine,combat=combat,checked_action=checked_action,ActionRejected=ActionRejected,
            pytest=pytest,serialize_match_snapshot=serialize_match_snapshot,
            deserialize_match_snapshot=deserialize_match_snapshot)
    imports=[node for node in tree.body if isinstance(node,ast.ImportFrom)
             and node.module=='tests.combat_canonical_022']
    exec(compile(ast.Module(body=imports+nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns


def make_creature(ns,state,cid,owner,name):
    fn=ns['_creature'];raw=official(name)
    args=[state,cid,owner,name]
    # The old mandatory printed-argument fixture signature and its narrowed
    # canonical replacement are both exercised; assertions do not change.
    params=inspect.signature(fn).parameters
    if 'power' in params and params['power'].default is inspect.Parameter.empty:
        args.extend([int(raw['power']),int(raw['toughness'])])
    fn(*args)
    return state.cards[cid]


def assert_official_card(card,name):
    raw=official(name)
    for field in ('name','oracle_text','mana_cost','type_line','layout'):
        assert getattr(card,field)==raw.get(field,''),field
    for field in ('power','toughness','loyalty'):
        value=raw.get(field)
        assert getattr(card,field)==(int(value) if value is not None else None),field
    assert card.printed_power==raw.get('power')
    assert card.printed_toughness==raw.get('toughness')
    assert card.colors==raw['colors']
    assert card.card_faces==raw.get('card_faces',[])
    assert card.image_uri==raw['image_uris']['normal']
    # Native CardInstance uses the existing combat-keyword projection. For
    # example Morph remains in the complete Oracle, not that runtime list.
    assert card.keywords==_infer_keywords(raw['oracle_text'])
    record=card.characteristic_record
    assert type(record) is dict
    assert record['version']==1
    for key,value in record['physical'].items():
        assert getattr(card,key)==value,key
    for key,value in record['values'].items():
        assert getattr(card,key)==value,key


@pytest.mark.parametrize('name',tuple(sorted(SOURCES)))
def test_complete_pinned_raw_is_fresh_and_independent(name):
    first=official(name);second=official(name)
    assert first['object']=='card' and first['id'] and first['oracle_id']
    assert {'legalities','image_uris','rulings_uri','color_identity','oracle_text','mana_cost','type_line'}<=first.keys()
    first['legalities'].clear()
    assert second==official(name)


@pytest.mark.parametrize('owner',(1,2))
@pytest.mark.parametrize('name',CREATURES)
def test_actual_damage_helper_forwards_full_facts_to_native_view_and_snapshot(name,owner):
    ns=damage_construction();state=ns['_state']()
    card=make_creature(ns,state,'full-raw-witness',owner,name)
    assert_official_card(card,name)
    assert card.id=='full-raw-witness' and card.owner==card.controller==owner
    assert card.zone==Zone.BATTLEFIELD and card.summoning_sick is False
    viewed=serialize_card_view(state,card.id)
    assert viewed['name']==name and viewed['type_line']==official(name)['type_line']
    restored=deserialize_match_snapshot(serialize_match_snapshot(state))
    assert_official_card(restored.cards[card.id],name)
    assert serialize_match_snapshot(restored)==serialize_match_snapshot(state)


@pytest.mark.parametrize('owner',(1,2))
def test_actual_damage_base_is_born_canonical_without_stock_or_rng_repair(owner):
    ns=damage_construction();state=ns['_state']()
    old=MatchFactory.from_decks([{'quantity':60,'card_name':'Island'}],
                                [{'quantity':60,'card_name':'Island'}],seed=73)
    assert state.rng.getstate()==old.rng.getstate()
    assert len(state.players[owner].hand)==7 and len(state.players[owner].library)==53
    for card in state.cards.values():assert_official_card(card,'Island')
    assert state.sideboard_facts['coverage_ok'] is True
    assert len(state.sideboard_facts['inventory'])==120
    assert serialize_match_snapshot(deserialize_match_snapshot(serialize_match_snapshot(state)))==serialize_match_snapshot(state)


@pytest.mark.parametrize('owner',(1,2))
def test_existing_stock_tamper_still_rejects_with_original_root_unchanged(owner):
    ns=damage_construction();state=ns['_state']();before=serialize_match_snapshot(state)
    bad=deepcopy(state);bad.cards[bad.players[owner].hand[0]].name='Noncard stock tamper'
    with pytest.raises(ValueError,match='Sideboard stock'):
        serialize_match_snapshot(bad)
    assert serialize_match_snapshot(state)==before


def test_named_template_birth_preserves_scene_rng_and_does_not_alias_other_cards():
    ns=damage_construction();state=ns['_state']();rng=state.rng.getstate()
    first=make_creature(ns,state,'first-canonical',1,'Llanowar Elves')
    second=make_creature(ns,state,'second-canonical',2,'Llanowar Elves')
    assert_official_card(first,'Llanowar Elves');assert_official_card(second,'Llanowar Elves')
    assert first.characteristic_record is not second.characteristic_record
    assert first.characteristic_record['physical'] is not second.characteristic_record['physical']
    first.characteristic_record['physical']['keywords'].append('Noncard alias sentinel')
    assert second.characteristic_record['physical']['keywords']==official('Llanowar Elves')['keywords']
    assert state.rng.getstate()==rng


def test_original_planeswalker_producer_forwards_actual_full_card_before_real_action():
    ns=damage_construction();real=RulesEngine.take_action;seen=[]
    class Reached(Exception):pass
    def check(engine,state,player,action):
        assert_official_card(state.cards['teferi'],'Teferi, Hero of Dominaria')
        seen.append((player,deepcopy(action)))
        result=real(engine,state,player,action)
        raise Reached
    with patch.object(RulesEngine,'take_action',check),pytest.raises(Reached):
        ns['test_trample_assignment_to_planeswalker_reduces_loyalty']()
    assert seen==[(1,{'type':'pass_priority'})]


def test_original_graveyard_producer_forwards_full_impulse_to_real_materializer():
    module=importlib.import_module('tests.test_ai_combat_search')
    real=AIAgent._materialize_action;seen=[]
    def check(agent,state,move,player):
        assert_official_card(state.cards['impulse'],'Impulse')
        seen.append(player)
        return real(agent,state,move,player)
    with patch.object(AIAgent,'_materialize_action',check):
        module.test_ai_materializes_graveyard_spell_target_for_recursion()
    assert seen==[1]


def test_original_named_lethal_fixture_really_presents_unblocked_lethal():
    # The separately authorized life3 setup must be genuinely lethal at printed3/3.
    module=importlib.import_module('tests.test_ai_combat_search');captured=[]
    class Reached(Exception):pass
    def capture(agent,state,*args):
        captured.append(state)
        raise Reached
    with patch.object(AIAgent,'_choose_blocks',capture),pytest.raises(Reached):
        module.test_master_block_search_prevents_lethal_damage_when_trade_is_available()
    state=captured[0];before=serialize_match_snapshot(state);unblocked=deepcopy(state)
    assert state.players[2].life==3
    unblocked.blocks={};unblocked.mechanic_choice_players=set()
    combat.combat_damage(unblocked)
    assert unblocked.players[2].life==0,'Named positive no longer instantiates its original lethal-prevention mechanism'
    assert serialize_match_snapshot(state)==before


@pytest.mark.parametrize('defending_player',(1,2))
@pytest.mark.parametrize('starting_life,expected_life',((3,0),(4,1)))
def test_canonical_hill_giant_unblocked_life_boundary(defending_player,starting_life,expected_life):
    from tests.combat_canonical_022 import canonical_card,canonical_entry
    attacking_player=3-defending_player
    state=MatchFactory.from_decks([canonical_entry('Forest',60)],[canonical_entry('Forest',60)],seed=66)
    state.pregame_pending=False;state.kept_hands={1,2}
    state.step=Step.DECLARE_BLOCKERS;state.active_player=attacking_player;state.priority_player=defending_player
    state.players[defending_player].life=starting_life
    attacker=canonical_card('Hill Giant',id='attacker',owner=attacking_player,controller=attacking_player,zone=Zone.BATTLEFIELD)
    blocker=CardInstance('blocker','Bear',defending_player,defending_player,Zone.BATTLEFIELD,['Creature'],power=2,toughness=2)
    state.cards.update({attacker.id:attacker,blocker.id:blocker})
    state.players[attacking_player].battlefield.append(attacker.id)
    state.players[defending_player].battlefield.append(blocker.id)
    state.attackers=[attacker.id]
    assert_official_card(attacker,'Hill Giant')
    assert (attacker.power,attacker.toughness)==(3,3)
    before=serialize_match_snapshot(state);unblocked=deepcopy(state)
    unblocked.blocks={};unblocked.mechanic_choice_players=set()
    combat.combat_damage(unblocked)
    assert unblocked.players[defending_player].life==expected_life
    if expected_life==1:
        assert unblocked.winner is None
    assert serialize_match_snapshot(state)==before
