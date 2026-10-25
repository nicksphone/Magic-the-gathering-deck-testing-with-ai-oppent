import assert from 'node:assert/strict';
import {newAiPlays} from '../src/lib/ai-plays.ts';

// Synthetic public snapshots: presentation regression, not gameplay evidence.
const player = (id, name) => ({id, name, hand: [], battlefield: [], graveyard: [], exile: []});
const base = {id:'notice-game', game_number:1, revision:1, turn:2, controllers:{1:'human',2:'ai'},
  players:{1:player(1,'Player A'),2:player(2,'Player B')}, stack:[], log:['Opening public event']};
const cast = 'Player B casts/activates Lava Spike.';
const next = {...base, revision:2, log:[...base.log,cast,'Player A takes 3 damage.','Lava Spike resolves.']};
assert.deepEqual(newAiPlays(null,next,1), [], 'Loading an old game must not replay its log');
const [notice] = newAiPlays(base,next,2);
assert.equal(notice?.name,'Lava Spike','An already-resolved AI spell still needs a notice');
assert.equal(notice.playerName,'Player B');
assert.equal(notice.controller,2);
assert.deepEqual(notice.targets,[], 'Life loss is not target evidence');
assert.deepEqual(newAiPlays(next,next,3),[], 'Rereads do not announce again');
assert.deepEqual(newAiPlays(next,{...next,revision:1},4),[], 'Stale snapshots never replay actions');
assert.deepEqual(newAiPlays(base,{...next,id:'another-game'},5),[]);
assert.deepEqual(newAiPlays(base,{...next,game_number:2},6),[]);
assert.deepEqual(newAiPlays(base,{...next,controllers:{1:'human',2:'human'}},7),[]);
assert.deepEqual(newAiPlays(base,{...next,controllers:undefined},8),[], 'Never guess which seat is AI');
const human = {...base,revision:2,log:[...base.log,'Player A casts/activates Lava Spike.']};
assert.deepEqual(newAiPlays(base,human,9),[]);
const rolling = {...base,log:Array.from({length:120},(_,i)=>`public event ${i}`)};
const two = {...base,revision:3,log:[...rolling.log.slice(2),cast,cast]};
const repeated = newAiPlays(rolling,two,10);
assert.equal(repeated.length,2, 'Rolling equal-length log and identical consecutive casts are distinct');
assert.notEqual(repeated[0].id,repeated[1].id);
const again = newAiPlays(next,{...next,revision:3,log:[...next.log,cast]},11);
assert.equal(again.length,1);
assert.notEqual(again[0].id,notice.id);
assert.deepEqual(newAiPlays(base,{...next,log:['unrelated reset',cast]},12),[], 'No shared log frontier means baseline, not a guessed event replay');
assert.deepEqual(newAiPlays(base,{...next,log:[...base.log,'Player B takes 3 damage.']},13),[]);
const publicCard = {id:'public-target',name:'Visible creature',image_uri:'/card-images/visible.jpg'};
const onStack = {...next, players:{...next.players,1:{...base.players[1],battlefield:[publicCard]}},
  stack:[{id:'stack-1',label:'Lava Spike',controller:2,targets:['public-target']}]};
assert.deepEqual(newAiPlays(base,onStack,14)[0].targets,['Visible creature']);
assert.deepEqual(newAiPlays({...base,stack:onStack.stack},onStack,18)[0].targets,[],
  'A new same-named cast cannot inherit targets from an older retained stack item');
const privateCard = {id:'secret',name:'Private card',image_uri:'/card-images/secret.jpg'};
const privateState = {...next,players:{...next.players,2:{...base.players[2],hand:[{...privateCard,name:'Lava Spike'}]}}};
assert.equal(newAiPlays(base,privateState,15)[0].imageUri,undefined,'Never inspect a hidden hand to find art');
const resolved = {...next,players:{...next.players,2:{...base.players[2],graveyard:[{...privateCard,name:'Lava Spike'}]}}};
assert.equal(newAiPlays(base,resolved,16)[0].imageUri,'/card-images/secret.jpg');
const opposite = {...base,controllers:{1:'ai',2:'human'},revision:2,log:[...base.log,'Player A casts/activates Thalia, Guardian of Thraben.']};
assert.equal(newAiPlays(base,opposite,17)[0].name,'Thalia, Guardian of Thraben');
console.log('PASS AI public cast notices: resolved, rolling/repeated, seats, baseline, stale, targets, hidden-data exclusion');
