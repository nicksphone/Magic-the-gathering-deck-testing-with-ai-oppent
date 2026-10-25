import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source = ts.createSourceFile('App.tsx', readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8'),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const printer = ts.createPrinter();
const effects = [];
let guard;
let defaultPaused;
function visit(node) {
  if (ts.isVariableDeclaration(node) && ts.isArrayBindingPattern(node.name)
      && node.name.elements[0]?.name?.getText(source) === 'autoResponsePaused') {
    const initial = node.initializer.arguments[0];
    assert.ok(initial.kind === ts.SyntaxKind.TrueKeyword || initial.kind === ts.SyntaxKind.FalseKeyword);
    defaultPaused = initial.kind === ts.SyntaxKind.TrueKeyword;
  }
  if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'humanResponseWindowActive') guard = node.initializer;
  if (ts.isCallExpression(node) && node.expression.getText(source) === 'useEffect'
      && node.arguments[1]?.getText(source).includes('humanResponseWindowActive')) {
    effects.push(printer.printNode(ts.EmitHint.Expression, node.arguments[0], source));
  }
  ts.forEachChild(node, visit);
}
visit(source);
assert.ok(guard);
assert.equal(typeof defaultPaused, 'boolean', 'Use the actual App initial pause state');
assert.equal(effects.length, 3, 'Exercise all actual response effects');
const failures = [];
let checks = 0;
function check(actual, expected, label) {
  checks++;
  if (actual !== expected) failures.push({label, actual, expected});
}
const controls = ts.createSourceFile('Controls.tsx', readFileSync(new URL('../src/components/Controls.tsx', import.meta.url), 'utf8'),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let live;
const controlExpressions = {};
let timerDisabled;
function visitControls(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(controls) === 'interruptWindowLive') live = node.initializer;
  if (ts.isVariableDeclaration(node) && ['humanResponseTimerAvailable', 'interruptWindowLabel', 'interruptWindowDetail'].includes(node.name.getText(controls))) {
    controlExpressions[node.name.getText(controls)] = node.initializer;
  }
  if (ts.isJsxOpeningElement(node) && node.tagName.getText(controls) === 'button'
      && node.attributes.properties.some(p => ts.isJsxAttribute(p) && p.name.getText(controls) === 'onClick'
        && p.initializer?.getText(controls) === '{props.onToggleAutoResponsePause}')) {
    timerDisabled = node.attributes.properties.find(p => ts.isJsxAttribute(p) && p.name.getText(controls) === 'disabled')?.initializer?.expression;
  }
  ts.forEachChild(node, visitControls);
}
visitControls(controls);
assert.ok(live);
const displayedLive = new Function('props', 'humanResponseTimerAvailable', `return (${live.getText(controls)});`);
for (const [responseCountdown, autoResponsePaused, expected] of [[5, false, true], [5, true, false], [null, false, false]]) {
  check(displayedLive({responseCountdown, autoResponsePaused}, true), expected, 'Actual Controls paused/open display');
}
for (const row of [
  {controller: 'human', stack: 1, pass: true, mode: 'player_vs_ai', available: true},
  {controller: 'ai', stack: 1, pass: false, mode: 'player_vs_ai', available: false},
  {controller: 'human', stack: 0, pass: true, mode: 'player_vs_ai', available: false},
  {controller: 'human', stack: 1, pass: false, mode: 'player_vs_ai', available: false},
  {controller: 'human', stack: 1, pass: true, mode: 'human_vs_human', available: false},
]) {
  const props = {match: {mode: row.mode}, autoResponsePaused: true, responseCountdown: null,
    legalMoves: row.pass ? [{type: 'pass_priority'}] : []};
  const values = {props, currentController: row.controller, stackSize: row.stack};
  const evaluate = node => new Function(...Object.keys(values), `return (${node.getText(controls)});`)(...Object.values(values));
  values.humanResponseTimerAvailable = controlExpressions.humanResponseTimerAvailable
    ? evaluate(controlExpressions.humanResponseTimerAvailable) : false;
  values.interruptWindowLive = evaluate(live);
  const label = evaluate(controlExpressions.interruptWindowLabel);
  const detail = evaluate(controlExpressions.interruptWindowDetail);
  check(label.includes('Human auto-pass timer off'), row.available, `Actual label eligibility ${JSON.stringify(row)}`);
  check(detail.includes('Human priority has no time limit'), row.available, `Actual detail eligibility ${JSON.stringify(row)}`);
  check(timerDisabled ? evaluate(timerDisabled) : false, !row.available, `Actual optional button eligibility ${JSON.stringify(row)}`);
}
for (const seat of [1, 2]) {
  const timers = new Map();
  let nextTimer = 0, countdown = null, paused = defaultPaused, passes = 0, cleanups = [];
  const signature = {current: ''};
  const inFlight = {current: false};
  const match = {id: 'timer-match', mode: 'player_vs_ai', controllers: {1: seat === 1 ? 'human' : 'ai', 2: seat === 2 ? 'human' : 'ai'},
    stack: [{id: 'first-stack'}], winner: null, pregame_pending: false, match_complete: false};
  const window = {setTimeout(callback, milliseconds) {
    assert.equal(milliseconds, 1000);
    const id = ++nextTimer;
    timers.set(id, callback);
    return id;
  }, clearTimeout(id) {timers.delete(id);}};
  const setResponseCountdown = value => {countdown = typeof value === 'function' ? value(countdown) : value;};
  const context = () => {
    const values = {match, legalPlayerId: seat, legalMoves: [{type: 'pass_priority'}], restoring: false,
      mutationPending: false, autoProgressPaused: false, canAutoPass: false};
    const active = new Function(...Object.keys(values), `return (${guard.getText(source)});`)(...Object.values(values));
    return {...values, humanResponseWindowActive: active, autoResponsePaused: paused, responseCountdown: countdown,
      setResponseCountdown, setAutoResponsePaused: value => {paused = value;}, responseWindowSigRef: signature,
      responsePassInFlight: inFlight, gate: {current: {busy: false}}, window,
      passPriority: async () => {passes++;}, setActionError: () => {throw Error('Unexpected pass error');},
      setAutoProgressPaused: () => {throw Error('Unexpected progression error');}};
  };
  function render() {
    for (const cleanup of cleanups) cleanup();
    cleanups = [];
    // Each effect sees the same render snapshot, as in React.
    const values = context();
    for (const effect of effects) {
      const cleanup = new Function(...Object.keys(values), `return (${effect});`)(...Object.values(values))();
      if (typeof cleanup === 'function') cleanups.push(cleanup);
    }
  }
  function tick() {
    const [id, callback] = timers.entries().next().value;
    timers.delete(id);
    callback();
    render();
  }
  render(); render();
  check(paused, true, `seat${seat}: human priority is held by default`);
  check(countdown, null, `seat${seat}: no timer before explicit opt-in`);
  check(timers.size, 0, `seat${seat}: no scheduled automatic human pass`);
  for (let second = 0; second < 12; second++) {
    if (timers.size) tick();
    await Promise.resolve();
  }
  check(passes, 0, `seat${seat}: elapsed time without opt-in never passes`);
  // A separate, explicitly opted-in protocol window retains all original
  // countdown, pause/resume and one-pass assertions below.
  match.stack = [{id: 'opt-in-stack'}];
  signature.current = ''; countdown = null; paused = false; passes = 0;
  render(); render();
  check(countdown, 6, `seat${seat}: initial countdown`);
  if (timers.size) tick();
  check(countdown, 5, `seat${seat}: one elapsed second`);
  paused = true; render();
  check(countdown, 5, `seat${seat}: pause preserves remaining time`);
  check(timers.size, 0, `seat${seat}: pause cancels ticking`);
  check(passes, 0, `seat${seat}: paused does not pass`);
  paused = false; render();
  check(countdown, 5, `seat${seat}: resume preserves remaining time`);
  check(timers.size, 1, `seat${seat}: resume schedules ticking`);
  if (timers.size) {
    for (let i = 0; i < 5; i++) tick();
    await Promise.resolve();
    check(passes, 1, `seat${seat}: one pass at zero`);
    render();
    check(passes, 1, `seat${seat}: no repeat pass for same stack`);
    match.stack = [{id: 'second-stack'}]; render(); render();
    check(countdown, null, `seat${seat}: changed window does not inherit timer consent`);
    check(paused, true, `seat${seat}: changed window requires fresh opt-in`);
    check(timers.size, 0, `seat${seat}: changed window holds indefinitely`);
    for (let second = 0; second < 12; second++) {
      if (timers.size) tick();
      await Promise.resolve();
    }
    check(passes, 1, `seat${seat}: new window never passes without new consent`);
    paused = false; render(); render();
    check(countdown, 6, `seat${seat}: explicit opt-in starts the new window timer`);
    // All effects see this same render snapshot. Changing the window exactly
    // when the old timer reaches zero must not pass in the new window.
    countdown = 0; match.stack = [{id: 'third-stack'}]; render();
    await Promise.resolve();
    check(passes, 1, `seat${seat}: expired old timer cannot pass a new response window`);
    paused = true; render();
    match.stack = []; render(); render();
    check(countdown, null, `seat${seat}: empty stack clears countdown`);
    check(paused, true, `seat${seat}: leaving response resets to indefinite human hold`);
    check(timers.size, 0, `seat${seat}: no timer after window ends`);
  }
  for (const cleanup of cleanups) cleanup();
}
assert.deepEqual(failures, [], 'Actual timer effect lifecycle must preserve pause/resume');
console.log(`PASS ${checks} actual response effect lifecycle checks, both seats`);
