import assert from 'node:assert/strict';

// Exercise the visible review flow; never manufacture persisted approval.
export async function reviewStart(browser, { recover = false, bestOf = 3 } = {}) {
  const { click, waitFor, evaluate } = browser;
  const label = recover ? 'Recover pending match start' : `Start Best-of-${bestOf} Match`;
  const checkbox = '[aria-label="Acknowledge exploratory interactive match"]';
  assert.equal(await evaluate(`Boolean(document.querySelector(${JSON.stringify(checkbox)}))`), false,
    'A new or legacy intent must not already have review approval');
  await click(label);
  await waitFor(`Boolean(document.querySelector(${JSON.stringify(checkbox)}))`, 45000);
  assert.equal(await evaluate(`document.querySelector(${JSON.stringify(checkbox)}).checked`), false);
  assert.equal(await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent.trim() === ${JSON.stringify(label)}).disabled`), true,
    'Review cannot start until deliberate acknowledgement, even for empty gaps');
  assert.ok((await evaluate("document.querySelector('[aria-label=\"Interactive match support preflight\"]').innerText")).includes('not certification'));
  await evaluate(`document.querySelector(${JSON.stringify(checkbox)}).click()`);
  await waitFor(`document.querySelector(${JSON.stringify(checkbox)}).checked && [...document.querySelectorAll('button')].some(b => b.textContent.trim() === ${JSON.stringify(label)} && !b.disabled)`);
  return label;
}

export async function startReviewed(browser, options) {
  await browser.click(await reviewStart(browser, options));
}
