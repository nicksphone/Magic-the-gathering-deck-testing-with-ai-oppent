import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
const require=createRequire(import.meta.url);
const {createElement}=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const runtime=require('react/jsx-runtime');
const built=await build({entryPoints:[new URL('../src/components/Controls.tsx',import.meta.url).pathname],bundle:true,write:false,platform:'node',format:'cjs',packages:'external',jsx:'automatic',define:{'import.meta.env.VITE_API_BASE_URL':"''"}});
const mod={exports:{}};new Function('require','module','exports',built.outputFiles[0].text)(require,mod,mod.exports);
const original={jsx:runtime.jsx,jsxs:runtime.jsxs};let buttons=[];
for(const key of ['jsx','jsxs'])runtime[key]=(type,props,...args)=>{if(type==='button')buttons.push(props);return original[key](type,props,...args);};
const noop=()=>{};
const base={decks:[],selectedA:null,selectedB:null,startMode:'player_vs_ai',humanSeat:1,difficulty:'strong',bestOf:3,autoplayDelayMs:600,responseCountdown:null,autoResponsePaused:true,
 setSelectedA:noop,setSelectedB:noop,setStartMode:noop,setHumanSeat:noop,setDifficulty:noop,setBestOf:noop,
 onStart:noop,onNextStep:noop,onAutoplayTick:noop,legalMoves:[],onToggleAutoResponsePause:noop};
// Explicitly synthetic component protocol vectors, not game execution.
const state=seat=>({id:'protocol-match',turn:2,step:'precombat_main',active_player:seat,priority_player:seat,winner:null,score:{1:0,2:0},controllers:{[seat]:'human',[3-seat]:'ai'},players:{1:{battlefield:[]},2:{battlefield:[]}},stack:[]});
function render(p){buttons=[];const html=renderToStaticMarkup(createElement(mod.exports.Controls,{...base,...p}));return{html,buttons:[...buttons]};}
try{
 assert.ok(!render({match:null}).html.includes('aria-label="Turn commands"'));
 for(const seat of [1,2]){
  const calls=[];const match=state(seat),props={match,actingPlayerId:seat,legalMoves:[{type:'pass_priority'}],onPassPriority:()=>calls.push('pass'),onToggleAutomaticPlay:()=>calls.push('auto'),autoProgressPaused:false};
  assert.match(render({...props,match:{...match,step:undefined}}).html,/Awaiting phase/,'Partial restored metadata never invents a phase or crashes the display');
  let r=render(props);assert.ok(r.html.includes('aria-label="Turn commands"'),'Active-match turn actions have a dedicated region');
  let pass=r.buttons.filter(b=>b.children==='Pass Priority');assert.equal(pass.length,1,'One actual pass control, not a duplicated callback');assert.equal(pass[0].disabled,false);pass[0].onClick();assert.deepEqual(calls,['pass']);
  const auto=r.buttons.find(b=>b.id==='automatic-play-toggle');assert.ok(auto);auto.onClick();assert.deepEqual(calls,['pass','auto']);
  const freshCard={id:'h',name:'Protocol haste creature',types:['Creature'],summoning_sick:true,tapped:false,power:2,toughness:2,keywords:['haste']};
  const keeper={...props,match:{...match,players:{...match.players,[seat]:{battlefield:[freshCard]}}},legalMoves:[{type:'choose_mechanic',kind:'legend_keeper',player_id:seat,options:['h']}]};
  assert.ok(!render(keeper).html.includes(', summoning sick'),'Choice labels also respect effective haste');
  assert.ok(render({...keeper,match:{...keeper.match,players:{...keeper.match.players,[seat]:{battlefield:[{...freshCard,keywords:[]}]}}}}).html.includes(', summoning sick'),'Losing haste restores the choice label');
  assert.equal(render({...props,legalMoves:[]}).buttons.find(b=>b.children==='Pass Priority').disabled,true);
  assert.equal(render({...props,match:{...match,controllers:{[seat]:'ai',[3-seat]:'human'}}}).buttons.find(b=>b.children==='Pass Priority').disabled,true);
  const aiPending=render({...props,match:{...match,controllers:{[seat]:'ai',[3-seat]:'human'},pending_mechanic_choice:{kind:'synthetic_unknown',player_id:seat}},legalMoves:[]});
  assert.ok(!aiPending.html.includes('Review required choice'),'An AI-owned pending choice never instructs the human to answer it');
  r=render({...props,legalMoves:[{type:'pass_priority'},{type:'choose_mechanic',kind:'synthetic_unknown',player_id:seat}],match:{...match,pending_mechanic_choice:{kind:'synthetic_unknown',player_id:seat}}});
  assert.equal(r.buttons.find(b=>b.children==='Pass Priority').disabled,true);assert.match(r.html,/Review required choice/);
  const attack={type:'attack',options:['a'],defenders:[{id:'player:'+(3-seat),kind:'player',label:'Opponent'}]};
  r=render({...props,legalMoves:[{type:'pass_priority'},attack]});let commit=r.buttons.find(b=>b.className==='turn-command-primary');assert.equal(commit.type,'submit');assert.equal(commit.form,'attack-declaration');assert.equal(commit.children,'Submit Attackers');assert.equal(commit.onClick,undefined,'HTML form validation and existing onSubmit retain control');
  const block={type:'block',attackers:[{id:'a',name:'Attacker'}],blockers:[{id:'b',name:'Blocker'}]};r=render({...props,legalMoves:[{type:'pass_priority'},block]});commit=r.buttons.find(b=>b.className==='turn-command-primary');assert.equal(commit.form,'block-declaration');assert.equal(commit.children,'Submit Blocks');
  const cost={mana_cost:'{W/U}',hybrid_symbols:[{symbol:'W/U',choices:['W','U']}]};
  r=render({...props,combatDraft:{attackers:['a'],attackTargets:{},bands:[],blocks:{},selectedBlocker:null},legalMoves:[{type:'pass_priority'},{...attack,attack_costs:{a:{['player:'+(3-seat)]:cost}}}]});assert.equal(r.buttons.find(b=>b.className==='turn-command-primary').disabled,true,'Missing combat payment cannot use the dock to bypass the original guard');
 }
 console.log('PASS both-seat turn region, single exact pass callback, automatic-play callback, AI/choice admission, real combat form association and payment guard');
}finally{Object.assign(runtime,original);}
