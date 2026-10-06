import assert from 'node:assert/strict';

// Fixture intent is explicit; the public legal view supplies the actual index,
// complete output and mandatory costs. Never infer a flexible human payment.
export async function activateIndexedMana(browser, {api, id, seat, cardId, color}) {
  const response = await fetch(`${api}/matches/${id}/legal-moves?player_id=${seat}`);
  assert.equal(response.status, 200);
  const {moves} = await response.json();
  const offered = moves.filter(move => move.type === 'activate_mana_ability' &&
    move.card_id === cardId && Number(move.outputs?.[color] ?? 0) > 0);
  assert.equal(offered.length, 1, 'Fixture must identify one actual offered indexed ability');
  const move = offered[0];
  assert.ok(Array.isArray(move.output_options) && move.output_options.length);
  assert.ok(move.activation_costs && Array.isArray(move.hybrid_symbols));
  assert.equal(move.hybrid_symbols.length, 0, 'These fixtures have no implicit hybrid branch');
  const payment = move.activation_costs;
  assert.equal(payment.discard_cards, payment.fixed_discard_card_ids.length);
  assert.equal(payment.sacrifice_creatures, payment.fixed_sacrifice_card_ids.length,
    'No flexible resource may be silently selected by this helper');
  const selector = `[data-mana-source=${JSON.stringify(cardId)}][data-mana-index="${move.ability_index}"]`;
  const {evaluate, waitFor} = browser;
  await waitFor(`Boolean(document.querySelector(${JSON.stringify(selector)}))`);
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).closest('details').open = true`);
  assert.equal(await evaluate(`Boolean(document.querySelector(${JSON.stringify(selector)}).querySelector('[role=alert]'))`), false);
  const before = await fetch(`${api}/matches/${id}`).then(result => result.json());
  const select = `${selector} select[aria-label^="Base mana output"]`;
  if (await evaluate(`Boolean(document.querySelector(${JSON.stringify(select)}))`)) {
    const options = move.output_options.map((option, index) => ({...option, index})).filter(option => option.color === color);
    assert.equal(options.length, 1, 'Fixture must select one complete engine-offered BASE vector');
    assert.equal(await evaluate(`document.querySelector(${JSON.stringify(select)}).value`), '');
    assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}).querySelector('fieldset button').matches(':disabled')`), true);
    await evaluate(`(() => {const select=document.querySelector(${JSON.stringify(select)}); const option=select.querySelector('option[value="${options[0].index}"]'); if(!option || select.matches(':disabled')) throw Error('Missing offered base output'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(select,option.value); select.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    const drafted = await fetch(`${api}/matches/${id}`).then(result => result.json());
    assert.deepEqual(drafted, before, 'Output draft must not mutate the authoritative match');
    for (const cid of [...payment.fixed_discard_card_ids, ...payment.fixed_sacrifice_card_ids]) {
      assert.equal(await evaluate(`(() => {const input=[...document.querySelector(${JSON.stringify(selector)}).querySelectorAll('input[type=checkbox]')].find(input=>input.getAttribute('aria-label')?.includes(${JSON.stringify(cid)}));return Boolean(input?.checked && input.disabled);})()`), true);
    }
    const button = `${selector} fieldset button`;
    await waitFor(`!document.querySelector(${JSON.stringify(button)}).matches(':disabled')`);
    await evaluate(`document.querySelector(${JSON.stringify(button)}).click()`);
  } else {
    const vector = move.output_bundles === undefined ? {[color]: move.outputs[color]} : move.output_bundles[color];
    const label = 'Add projected ' + [...'WUBRGC'].filter(symbol => vector[symbol] > 0)
      .map(symbol => `${vector[symbol]} ${symbol}`).join(' + ');
    const button = `([...document.querySelector(${JSON.stringify(selector)}).querySelectorAll('button')].find(button=>button.textContent.trim()===${JSON.stringify(label)}))`;
    await waitFor(`${button} && !${button}.matches(':disabled')`);
    await evaluate(`${button}.click()`);
  }
  console.log(`Indexed mana UI: ${JSON.stringify({seat, card_id: cardId, ability_index: move.ability_index, color, cost: move.cost_text})}`);
}
