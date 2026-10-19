import assert from 'node:assert/strict';
import {openBrowser} from './browser-driver.mjs';

const frontend = process.env.MTG_FRONTEND_ORIGIN || 'http://127.0.0.1:15173';
const browser = await openBrowser(`${frontend}/tests/fixtures/ci-development-runtime/probe.html`);
let failure, proof;
try {
  await browser.waitFor('globalThis.__MTG_DEVELOPMENT_RUNTIME_PROOF__');
  const environment = await browser.evaluate('globalThis.__MTG_DEVELOPMENT_RUNTIME_PROOF__.environment');
  assert.deepEqual(environment, {nodeEnv: 'development', dev: true, prod: false});
  await browser.waitFor('globalThis.__MTG_DEVELOPMENT_RUNTIME_PROOF__.counts.mounts >= 2');
  proof = await browser.evaluate('globalThis.__MTG_DEVELOPMENT_RUNTIME_PROOF__');
  assert.deepEqual(proof.counts, {renders: 2, mounts: 2, cleanups: 1});
} catch (error) { failure = error; }
try { await browser.close(); }
catch (error) { failure = failure ? new AggregateError([failure, error], 'Development proof and page closure failed') : error; }
if (failure) throw failure;
console.log('DEVELOPMENT_RUNTIME_PROOF', JSON.stringify(proof));
