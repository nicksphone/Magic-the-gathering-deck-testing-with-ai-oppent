import assert from 'node:assert/strict';
import { groupBattlefield, cardStates, landPlayHint, phaseIndex } from '../src/components/table-model.ts';
const forest = {id:'f1',name:'Forest',types:['Land'],tapped:false,summoning_sick:false,power:null,toughness:null,mana_source_colors:['G'],mana_source_amounts:{G:1}};
const cards = [forest,{...forest,id:'f2',tapped:true},{...forest,id:'f3',counters:{charge:1}},{...forest,id:'animated',types:['Land','Creature'],power:2,toughness:2}];
const grouped = groupBattlefield(cards);
assert.equal(grouped.lands.length,2,'differing counters must not be grouped');
assert.deepEqual(grouped.lands[0].cards.map(c=>c.id),['f1','f2']);
assert.equal(grouped.lands[0].untapped,1);
assert.equal(grouped.nonLands[0].id,'animated','animated lands remain visible in combat row');
assert.deepEqual(groupBattlefield([{...forest,mana_source_colors:undefined,mana_source_amounts:undefined}]).lands[0].colors,[],'never infer mana from a name');
assert.deepEqual(cardStates({...forest,id:'a',types:['Creature'],summoning_sick:true,tapped:true},{attackers:['a'],blocks:{enemy:['a']}},true,true),['Tapped','Attacking','Blocking','Summoning sick','Targetable','Selected']);
assert.equal(phaseIndex('declare_blockers'),2);
assert.equal(phaseIndex('unrecognized'),-1);
console.log('PASS table grouping identities, animated lands, authoritative mana, explicit states and phase mapping');
const main = {winner:null,step:'precombat_main',active_player:1,priority_player:1,stack:[],players:{1:{land_plays_remaining:0},2:{land_plays_remaining:1}}};
assert.equal(landPlayHint(main,1),'No land plays remaining this turn');
assert.equal(landPlayHint({...main,step:'draw'},1),'Play in your main phase');
assert.equal(landPlayHint(main,2),'Wait for your turn');
assert.equal(landPlayHint({...main,priority_player:2},1),'Wait for priority');
assert.equal(landPlayHint({...main,stack:[{}]},1),'Wait for the stack to clear');
assert.equal(landPlayHint({...main,pregame_pending:true},1),'Keep your opening hand first');
assert.equal(landPlayHint({...main,pending_mechanic_choice:{}},1),'Complete the pending choice first');
assert.equal(landPlayHint({...main,winner:2},1),'Game over');
assert.equal(landPlayHint({...main,players:{1:{}}},1),'No legal land play available');
console.log('PASS explicit land timing, priority, allowance and legacy-server hints');

// Synthetic public-view vectors: keywords are effective, base_keywords are not.
const fresh = Object.freeze({id:'fresh',name:'Protocol creature',types:Object.freeze(['Creature']),
  tapped:false,summoning_sick:true,power:2,toughness:2,keywords:Object.freeze(['haste'])});
assert.deepEqual(cardStates(fresh,{}),[],'effective haste bypasses the sickness restriction badge');
assert.equal(fresh.summoning_sick,true,'presentation must preserve the raw condition');
assert.deepEqual(cardStates({...fresh,tapped:true},{attackers:['fresh'],blocks:{enemy:['fresh']}},true,true),
  ['Tapped','Attacking','Blocking','Targetable','Selected'],'haste must not remove other state badges');
const lostHaste = {...fresh,keywords:[],base_keywords:['haste'],oracle_text:'Haste'};
assert.deepEqual(cardStates(lostHaste,{}),['Summoning sick'],'losing effective haste restores the badge despite printed/base haste');
assert.deepEqual(cardStates({...lostHaste,keywords:['haste']},{}),[],'regaining effective haste bypasses the badge without clearing raw sickness');
assert.deepEqual(cardStates({...fresh,keywords:undefined},{}),['Summoning sick'],'ordinary fresh creatures retain the badge');
assert.deepEqual(cardStates({...fresh,keywords:['flying']},{}),['Summoning sick'],'other effective keywords do not bypass sickness');
assert.deepEqual(cardStates({...lostHaste,summoning_sick:false},{}),[],'an established creature remains unaffected');
assert.deepEqual(cardStates({...fresh,types:['Artifact'],keywords:[]},{}),[],'noncreatures do not acquire a sickness badge');
console.log('PASS 9 haste-badge checks: effective keywords, keyword loss/regain, raw condition and other states preserved');
