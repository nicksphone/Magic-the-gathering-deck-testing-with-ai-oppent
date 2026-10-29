import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {combatDraftGuidance, emptyCombatDraft} from '../src/components/combat-selection.ts';

// Synthetic UI protocol vectors, not real-card gameplay qualification.
const attack={type:'attack',options:['a','b']};
const block={type:'block',attackers:[{id:'a',name:'Attacker A'},{id:'b',name:'Attacker B'}],
  blockers:[{id:'wall',name:'Wall'},{id:'bear',name:'Bear'}]};
assert.equal(combatDraftGuidance(undefined,attack),null);
assert.equal(combatDraftGuidance(emptyCombatDraft()),null);
assert.match(combatDraftGuidance(emptyCombatDraft(),attack),/No attackers selected/);
assert.match(combatDraftGuidance({...emptyCombatDraft(),attackers:['a','stale']},attack),/1 attacker selected, not submitted/);
assert.match(combatDraftGuidance({...emptyCombatDraft(),attackers:['a','b']},attack),/2 attackers selected, not submitted/);
assert.match(combatDraftGuidance({...emptyCombatDraft(),selectedBlocker:'bear'},undefined,block),/Bear is selected; click an attacker/);
assert.match(combatDraftGuidance({...emptyCombatDraft(),blocks:{a:['wall'],b:['wall']}},undefined,block),/2 block assignments drafted, not submitted/);
assert.match(combatDraftGuidance({...emptyCombatDraft(),blocks:{gone:['bear']},selectedBlocker:'gone'},undefined,block),/No blocks drafted/);

const require=createRequire(import.meta.url);
const {createElement}=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const runtime=require('react/jsx-runtime');
const compiled=await build({entryPoints:[new URL('../src/components/Controls.tsx',import.meta.url).pathname],
  bundle:true,write:false,platform:'node',format:'cjs',packages:'external',jsx:'automatic',
  define:{'import.meta.env.VITE_API_BASE_URL':"''"}});
const module={exports:{}};
new Function('require','module','exports',compiled.outputFiles[0].text)(require,module,module.exports);
const original={jsx:runtime.jsx,jsxs:runtime.jsxs},buttons=[];
for(const key of ['jsx','jsxs'])runtime[key]=(type,props,...args)=>{
  if(type==='button')buttons.push(props);
  return original[key](type,props,...args);
};
try {
  const actions=[];
  const props={decks:[],selectedA:null,selectedB:null,startMode:'player_vs_ai',humanSeat:1,
    difficulty:'strong',bestOf:3,autoplayDelayMs:600,responseCountdown:null,autoResponsePaused:true,
    actingPlayerId:1,match:{id:'synthetic',game_number:1,turn:1,step:'declare_blockers',winner:null,
      priority_player:1,active_player:2,score:{'1':0,'2':0},controllers:{'1':'human','2':'ai'},stack:[],
      players:{'1':{battlefield:[]},'2':{battlefield:[]}}},
    legalMoves:[{type:'pass_priority'},block],
    combatDraft:{...emptyCombatDraft(),selectedBlocker:'bear'},onPassPriority:()=>actions.push('pass')};
  const html=renderToStaticMarkup(createElement(module.exports.Controls,props));
  assert.match(html,/role="status"[^>]*>Block draft: not submitted/);
  assert.match(html,/Bear is selected; click an attacker/);
  assert.deepEqual(actions,[],'Guidance rendering cannot submit a decision');
  const pass=buttons.find(b=>b.children==='Pass Priority');
  assert.equal(pass.disabled,false,'A draft does not prevent priority responses');
  pass.onClick();assert.deepEqual(actions,['pass']);
}finally{Object.assign(runtime,original);}
console.log('PASS combat draft counts, stale selections, explicit confirmation, actual status rendering and unchanged priority action');
