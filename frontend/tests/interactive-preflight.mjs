import assert from 'node:assert/strict';
import { canStartReviewed, parsePendingInteractiveStart, reviewMatchesPayload, startSignature } from '../src/lib/interactive-preflight.ts';

const payload = {
  deck_a: [{ quantity: 60, card_name: 'Island' }], deck_b: [{ quantity: 60, card_name: 'Forest' }],
  deck_a_sideboard: [{ quantity: 1, card_name: 'Willbender' }], deck_b_sideboard: [],
  deck_a_id: 1, deck_b_id: 2, controller_a: 'human', controller_b: 'ai',
  mode: 'player_vs_ai', ai_difficulty: 'master', best_of: 3,
};
const coverage = { status: 'exploratory', known_unsupported_cards: [] };
const review = { version: 1, signature: startSignature(payload), coverage, exploratoryAcknowledged: true };
const pending = { key: 'a'.repeat(32), payload, review };
assert.equal(canStartReviewed(review, payload), true);
assert.equal(canStartReviewed({ ...review, exploratoryAcknowledged: false }, payload), false, 'Empty gaps still need acknowledgement');
assert.equal(canStartReviewed(null, payload), false);
const reordered = Object.fromEntries(Object.entries(payload).reverse());
reordered.deck_a = [{ card_name: 'Island', quantity: 60 }];
assert.equal(startSignature(payload), startSignature(reordered));
for (const change of [
  { deck_a_id: 3 }, { deck_b_id: 3 }, { best_of: 5 }, { mode: 'human_vs_human' },
  { controller_a: 'ai' }, { controller_b: 'human' }, { ai_difficulty: 'strong' },
  { deck_a: [{ quantity: 59, card_name: 'Island' }] },
  { deck_b: [{ quantity: 60, card_name: 'Mountain' }] },
  { deck_a_sideboard: [] }, { deck_b_sideboard: [{ quantity: 1, card_name: 'Willbender' }] },
  { seed: 73 },
]) assert.equal(canStartReviewed(review, { ...payload, ...change }), false, JSON.stringify(change));
assert.deepEqual(parsePendingInteractiveStart(JSON.stringify(pending)), pending);
const legacy = parsePendingInteractiveStart(JSON.stringify({ key: pending.key, payload }));
assert.equal(legacy.key, pending.key);
assert.equal(canStartReviewed(legacy.review, legacy.payload), false);
for (const badReview of [
  { ...review, version: 2 }, { ...review, signature: 'different' },
  { ...review, exploratoryAcknowledged: 'yes' },
  { ...review, coverage: { status: 'certified', known_unsupported_cards: [] } },
  { ...review, coverage: { status: 'exploratory', known_unsupported_cards: [{ deck: 'A', card_name: 'Willbender', mechanics: 'morph' }] } },
]) {
  assert.equal(reviewMatchesPayload(badReview, payload), false);
  const held = parsePendingInteractiveStart(JSON.stringify({ ...pending, review: badReview }));
  assert.equal(held.key, pending.key, 'Untrusted review must not lose an uncertain intent/key');
  assert.equal(held.review, undefined);
}
for (const raw of [null, '', '{', 'x'.repeat(500001), 'null', '[]', '{}',
  JSON.stringify({ ...pending, key: 'bad' }),
  ...[{ deck_a: 'bad' }, { deck_a: [{ quantity: -1, card_name: 'Island' }] },
    { deck_b: [{ quantity: 1.5, card_name: 'Forest' }] }, { deck_a_sideboard: 'bad' },
    { controller_b: 'robot' }, { controller_b: ['ai'] }, { mode: 'unknown' }, { mode: ['player_vs_ai'] },
    { ai_difficulty: 'unknown' }, { best_of: 2 }, { deck_a_id: -1 }]
    .map(change => JSON.stringify({ ...pending, payload: { ...payload, ...change } })),
]) assert.equal(parsePendingInteractiveStart(raw), null);
console.log('PASS interactive preflight: exact wire identity, all settings/sideboards, deliberate empty-gap acknowledgement, versioned and legacy recovery, malformed persistence');
