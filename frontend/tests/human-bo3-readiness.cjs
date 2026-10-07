// Render actual Controls with authoritative readiness; no browser certificate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const {Controls} = require(process.env.MTG_CONTROLS_BUILD);
const noop = () => {};
const base = {decks: [], selectedA:null, selectedB:null, startMode:'human_vs_human', difficulty:'strong',
  bestOf:3, legalMoves:[], autoplayDelayMs:500, responseCountdown:null, autoResponsePaused:false,
  setSelectedA:noop,setSelectedB:noop,setStartMode:noop,setDifficulty:noop,setBestOf:noop,onStart:noop,
  onPassPriority:noop,onKeepHand:noop,onMulligan:noop,onNextStep:noop,onAutoplayTick:noop,
  setAutoplayDelayMs:noop,onSubmitBlocks:noop,onSubmitAttack:noop,onApplySideboard:noop,onNextGame:noop,
  onSetPriorityStops:noop,onChooseReplacement:noop,onChooseTriggerOrder:noop,onChooseTriggerTarget:noop,
  onChooseOptionalEffect:noop,onChooseMechanic:noop,onToggleAutoResponsePause:noop};
const inventory = applied => ({applied, mainboard:[{quantity:60,card_name:'Mountain'}], sideboard:[]});
function render(controllers, sideboarding, chooser=2) {
  return renderToStaticMarkup(React.createElement(Controls,{...base,match:{id:'owned', winner:1,
    match_complete:false, game_number:1, controllers, sideboarding, next_play_draw_chooser:chooser,
    players:{'1':{hand:[],battlefield:[]},'2':{hand:[],battlefield:[]}}, step:'end_step',priority_player:1,
    active_player:1, mode:'human_vs_human'}}));
}
function disabled(html,label) {
  const match=html.match(new RegExp('<button([^>]*)>'+label+'</button>'));
  assert.ok(match,label);return match[1].includes('disabled');
}
for (const first of [false,true]) for (const second of [false,true]) {
  const html=render({'1':'human','2':'human'},{'1':inventory(first),'2':inventory(second)});
  assert.equal(disabled(html,'P2 Play First'),!(first&&second));
  assert.equal(disabled(html,'P2 Draw First'),!(first&&second));
  assert.equal(disabled(html,'Confirm No Swaps'),first);
  if (!first || !second) assert.ok(html.includes('Waiting for'));
}
assert.equal(disabled(render({'1':'human','2':'ai'},{'1':inventory(false)},null),'Start Next Game \\(AI chooses play\\)'),true);
assert.equal(disabled(render({'1':'human','2':'ai'},{'1':inventory(true)},null),'Start Next Game \\(AI chooses play\\)'),false);
assert.equal(disabled(render({'1':'ai','2':'ai'},{},null),'Start Next Game \\(AI chooses play\\)'),false);
assert.equal(disabled(render({'1':'human','2':'human'},{},1),'P1 Play First'),true);
const source=fs.readFileSync(process.env.MTG_CONTROLS_SOURCE,'utf8');
assert.ok(source.includes('props.onApplySideboard(selectedSbPlayer, [], [])'));
console.log('PASS eight actual Controls readiness renders; explicit no-swaps callback bound');
