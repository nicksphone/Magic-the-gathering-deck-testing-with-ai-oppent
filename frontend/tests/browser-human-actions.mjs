import assert from "node:assert/strict";

const origin = "http://127.0.0.1:19222";
const page = await (await fetch(`${origin}/json/new?http://127.0.0.1:15173/tests/human-actions.html`, { method: "PUT" })).json();
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  const waiter = pending.get(message.id);
  if (!waiter) return;
  pending.delete(message.id);
  message.error ? waiter.reject(new Error(JSON.stringify(message.error))) : waiter.resolve(message.result);
};
function command(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Chromium command timed out: ${method}`)); }, 15000);
    pending.set(id, { resolve: (result) => { clearTimeout(timer); resolve(result); }, reject: (error) => { clearTimeout(timer); reject(error); } });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const response = await command("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
  return response.result.value;
}
async function waitFor(expression) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Browser condition timed out: ${expression}\n${await evaluate("document.body.innerText")}`);
}
async function click(prefix) {
  await evaluate(`(() => { const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith(${JSON.stringify(prefix)})); if (!button || button.disabled) throw new Error('Missing/enabled button: ' + ${JSON.stringify(prefix)}); button.click(); })()`);
}
async function reset() {
  await click("Reset Fixture");
  await waitFor("window.fixtureActions?.length === 0 && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
}
try {
  await waitFor("window.fixtureState && document.querySelector('[data-testid=ready]')?.textContent === 'Ready'");
  assert.equal(await evaluate("[...document.querySelectorAll('.hand-row button')].some(button => button.textContent.includes('Island'))"), false);
  await click("Play Land Forest");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'forest')");
  assert.equal(await evaluate("window.fixtureActions[0].player_id"), 2);
  console.log("PASS seat-2 land uses seat 2 and reaches battlefield");

  await reset();
  await evaluate("(() => { const select = document.querySelector('[aria-label=\"Ability target player\"]'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Activate Prodigal Pyromancer");
  await waitFor("window.fixtureState.stack.length === 1");
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].life === 19");
  console.log("PASS targeted permanent ability resolves against player 1");

  await reset();
  await evaluate("(() => { const label = [...document.querySelectorAll('label')].find(l => l.textContent.includes('Grizzly Bears (2 power)')); label.querySelector('input').click(); })()");
  await click("Crew Smuggler's Copter");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'copter' && c.types.includes('Creature'))");
  console.log("PASS explicit crew selection makes Vehicle a creature");

  await reset();
  await evaluate("(() => { const box = [...document.querySelectorAll('.cast-card-box')].find(b => b.querySelector('button')?.textContent.includes('Shock')); const select = [...box.querySelectorAll('select')].find(s => s.options[0].text === 'Target Player'); select.value = '1'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await click("Cast Shock");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions[0].action.from_exile"), true);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['1'].life === 18");
  console.log("PASS permitted exile spell preserves source zone and resolves");

  await reset();
  await click("Cast Llanowar Elves");
  await waitFor("window.fixtureState.stack.length === 1");
  assert.equal(await evaluate("window.fixtureActions[0].action.from_library"), true);
  await click("Resolve Stack");
  await waitFor("window.fixtureState.players['2'].battlefield.some(c => c.id === 'elf')");
  console.log("PASS permitted top-library spell reaches battlefield");
} finally {
  socket.close();
  await fetch(`${origin}/json/close/${page.id}`);
}
