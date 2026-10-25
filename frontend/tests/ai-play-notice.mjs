import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import postcss from 'postcss';

const entry = new URL('../src/components/AiPlayNotice.tsx', import.meta.url);
assert.ok(existsSync(entry), 'RED: AiPlayNotice component is not present');
const require = createRequire(import.meta.url);
const {createElement} = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const built = await build({entryPoints: [entry.pathname], bundle: true, write: false,
  platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
  loader: {'.css': 'empty'}, define: {'import.meta.env.VITE_API_BASE_URL': "''"}});
const mod = {exports: {}};
new Function('require', 'module', 'exports', built.outputFiles[0].text)(require, mod, mod.exports);
const render = plays => renderToStaticMarkup(createElement(mod.exports.AiPlayNotice, {plays}));
// Synthetic public-play events, not gameplay or canonical card evidence.
const play = (id, fields = {}) => ({id: String(id), name: 'Protocol card ' + id,
  controller: 2, playerName: 'Player 2', turn: 4, targets: [], ...fields});
const html = render([1, 2, 3, 4, 5].map(id => play(id)));
assert.ok(!html.includes('Protocol card 1') && !html.includes('Protocol card 2'));
for (const id of [3, 4, 5]) assert.ok(html.includes('Protocol card ' + id));
assert.ok(html.indexOf('Protocol card 3') < html.indexOf('Protocol card 4'));
assert.ok(html.indexOf('Protocol card 4') < html.indexOf('Protocol card 5'));
assert.match(html, /role="status"/);
assert.match(html, /aria-live="polite"/);
assert.match(html, /aria-atomic="false"/);
assert.match(html, /AI P2 played/);
assert.match(html, /Turn 4/);
assert.match(html, /Artwork unavailable/, 'Missing art uses genuine CardArt fallback');
assert.match(html, /aria-hidden="true"/, 'Decorative art is not announced twice');
const targeted = render([play('targeted', {controller: 1, name: 'Card <example>',
  imageUri: '/card-images/observed-cached.jpg', targets: ['Public artifact', 'Player 2']})]);
assert.match(targeted, /AI P1 played/);
assert.match(targeted, /Card &lt;example&gt;/);
assert.match(targeted, /Targets: Public artifact, Player 2/);
assert.match(targeted, /observed-cached\.jpg/);
assert.ok(!html.includes('Targets:'), 'No target label is invented for an untargeted play');
for (const value of [html, targeted, render([])]) {
  assert.doesNotMatch(value, /<(?:dialog|button|input|select|textarea)\b/);
  assert.doesNotMatch(value, /aria-modal|autofocus|tabindex|role="alert"/i);
}
const empty = render([]);
assert.match(empty, /role="status"/, 'The common live region may stay mounted while empty');
assert.match(empty, /class="ai-play-notices"/);
assert.doesNotMatch(empty, /AI P\d played/);
const source = readFileSync(entry, 'utf8');
assert.match(source, /key=\{play\.id\}/);
assert.match(source, /setTimeout\(\(\) => setVisible\(false\), 6_000\)/);
assert.match(source, /return \(\) => window\.clearTimeout\(timer\)/);
assert.match(source, /\}, \[\]\)/, 'Keyed notice timer has no snapshot dependencies');
assert.doesNotMatch(source, /\.focus\(|autoFocus|dispatchEvent|onClick/);
const css = postcss.parse(readFileSync(new URL('../src/styles/ai-play-notice.css', import.meta.url), 'utf8'));
let clickThrough = false, reducedMotion = false, narrow = false;
css.walkRules(rule => {
  if (rule.selectors.includes('.ai-play-notices') && rule.selectors.includes('.ai-play-notices *')
    && rule.selectors.includes('.ai-play-notice') && rule.selectors.includes('.ai-play-notice *')) {
    clickThrough = rule.nodes.some(node => node.prop === 'pointer-events' && node.value === 'none' && node.important);
  }
});
css.walkAtRules('media', rule => {
  if (rule.params.includes('prefers-reduced-motion')) reducedMotion = true;
  if (rule.params.includes('390px')) narrow = true;
});
assert.ok(clickThrough, 'Root and every descendant must let board input pass through');
assert.ok(reducedMotion && narrow, 'Styles explicitly cover reduced motion and narrow screens');
console.log('PASS AI-play notice SSR and source/style contracts: latest3 chronological, public names/controllers/targets, genuine art/fallback, polite nonmodal/no controls, click-through; browser timer lifecycle not executed');
