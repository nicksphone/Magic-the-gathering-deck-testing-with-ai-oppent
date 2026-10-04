import assert from 'node:assert/strict';
import { openBrowser } from './browser-driver.mjs';

const api = 'http://127.0.0.1:10199';
for (const seat of [1, 2]) for (const free of [false, true]) for (const payment of ['discard', 'sacrifice']) {
  const response = await fetch(`${api}/fixture?face_kind=${free ? 'free_' : ''}spell_cost_${seat}`, { method: 'POST' });
  assert.equal(response.status, 200);
  const fixture = await response.json();
  const owner = fixture.players[String(seat)];
  const paid = (payment === 'discard' ? owner.hand : owner.battlefield).find(card => card.name === (payment === 'discard' ? 'Island' : 'Grizzly Bears'));
  const target = fixture.players[String(3-seat)].battlefield.find(card => card.name === 'Grizzly Bears');
  const { evaluate, command, waitFor, click, reload, close } = await openBrowser('http://127.0.0.1:15173/');
  const ready = label => `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith(${JSON.stringify(label)}) && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor("document.body.innerText.includes('Cast Bone Shards')");
    await evaluate(`(() => {
      const box = [...document.querySelectorAll('.cast-card-box')].find(box => box.textContent.includes('Cast Bone Shards'));
      const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === 'base_${payment}'));
      select.value = 'base_${payment}'; select.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(`Boolean(document.querySelector('select[aria-label="${payment === 'discard' ? 'Discard' : 'Sacrifice'} for cost Bone Shards"]'))`);
    assert.equal(await evaluate(ready('Cast Bone Shards')), false);
    await evaluate(`(() => {
      const payment = document.querySelector('select[aria-label="${payment === 'discard' ? 'Discard' : 'Sacrifice'} for cost Bone Shards"]');
      [...payment.options].forEach(option => option.selected = option.value === ${JSON.stringify(paid.id)});
      payment.dispatchEvent(new Event('change', { bubbles: true }));
      const box = payment.closest('.cast-card-box');
      const target = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.textContent.startsWith('Target ')));
      target.value = ${JSON.stringify(target.id)}; target.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await waitFor(ready('Cast Bone Shards'));
    await click('Cast Bone Shards');
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    for (let i = 0; i < 2; i++) {
      await waitFor(ready('Pass Priority'));
      await click('Pass Priority');
      if (i === 0) await waitFor(`document.body.innerText.includes('Priority: P${3-seat}')`);
    }
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 0)()`);
    await reload();
    await waitFor("document.body.innerText.includes('Battlefield') && document.body.innerText.includes('Griselbrand') && !document.body.innerText.includes('Restoring saved session')");
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    assert.ok(final.players[String(seat)].graveyard.some(card => card.id === paid.id));
    assert.ok(final.players[String(seat)].hand.some(card => card.name === 'Lightning Bolt'));
    assert.ok(final.players[String(seat)].battlefield.some(card => card.name === 'Griselbrand'));
    assert.ok(final.players[String(3-seat)].graveyard.some(card => card.id === target.id));
    assert.equal(final.players[String(seat)].mana_pool.B, free ? 1 : 0);
    console.log(`PASS seat ${seat}: ${free ? 'free' : 'normal'} cast with deliberate ${payment}, correct target/payment and refresh`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}

for (const seat of [1, 2]) for (const kind of ['counted_cost', 'free_counted_cost', 'land_cost']) {
  const fixture = await (await fetch(`${api}/fixture?face_kind=${kind}_${seat}`, { method: 'POST' })).json();
  const name = kind === 'land_cost' ? 'Raze' : 'Cathartic Reunion';
  const payment = kind === 'land_cost' ? 'Sacrifice' : 'Discard';
  const cards = fixture.players[String(seat)][kind === 'land_cost' ? 'battlefield' : 'hand']
    .filter(card => ['Island', 'Swamp'].includes(card.name));
  const { evaluate, command, waitFor, click, close } = await openBrowser('http://127.0.0.1:15173/');
  const enabled = `[...document.querySelectorAll('button')].some(button => button.textContent.trim().startsWith('Cast ${name}') && !button.matches(':disabled'))`;
  try {
    await waitFor("document.body.innerText.includes('Saved matches') && !document.body.innerText.includes('Restoring saved session')");
    await evaluate(`localStorage.setItem('mtg.activeMatch', ${JSON.stringify(fixture.id)})`);
    await command('Page.reload');
    await waitFor(`Boolean(document.querySelector('select[aria-label="${payment} for cost ${name}"]'))`);
    assert.equal(await evaluate(enabled), false);
    async function select(ids) {
      await evaluate(`(() => {
        const select = document.querySelector('select[aria-label="${payment} for cost ${name}"]');
        [...select.options].forEach(option => option.selected = ${JSON.stringify(ids)}.includes(option.value));
        select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await select([cards[0].id]);
    if (payment === 'Discard') {
      assert.equal(await evaluate(enabled), false);
      await select(cards.map(card => card.id));
    } else {
      const target = fixture.players[String(3-seat)].battlefield[0];
      await evaluate(`(() => {
        const box = document.querySelector('select[aria-label="${payment} for cost ${name}"]').closest('.cast-card-box');
        const select = [...box.querySelectorAll('select')].find(select => [...select.options].some(option => option.value === ${JSON.stringify(target.id)}));
        select.value = ${JSON.stringify(target.id)}; select.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
    }
    await waitFor(enabled);
    await click(`Cast ${name}`);
    await waitFor(`(async () => (await (await fetch('${api}/matches/${fixture.id}')).json()).stack.length === 1)()`);
    await command('Page.reload');
    await waitFor(`document.body.innerText.includes('${name}')`);
    const final = await (await fetch(`${api}/matches/${fixture.id}`)).json();
    for (const card of cards) assert.ok(final.players[String(seat)].graveyard.some(paid => paid.id === card.id));
    assert.equal(final.players[String(seat)].mana_pool.R, kind.startsWith('free_') ? 1 : 0);
    console.log(`PASS seat ${seat}: ${kind} counts/candidates, button gating, selected payment and refresh`);
  } finally {
    await evaluate("localStorage.removeItem('mtg.activeMatch')");
    await close();
  }
}
