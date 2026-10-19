// Render the real panel with a seeded hook value; no browser or network claim.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const require = createRequire(import.meta.url);
const report = {complete:0,requested:2,cards:[
  {name:'Lightning Bolt',oracle_source:'fallback',match_ready:true,rulings:false,known_unsupported:[]},
  {name:'Time Warp',oracle_source:'missing',match_ready:false,rulings:false,known_unsupported:[]},
],missing:{cached:2,oracle:1,mana_cost:1,rulings:2}};
let hooks = 0;
const react = {...React,useState(initial) { hooks++; return React.useState(hooks === 8 ? report : initial); }};
const source = fs.readFileSync(new URL('../src/components/DeckPanel.tsx', import.meta.url),'utf8');
const output = ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText;
const mod = {exports:{}};
new Function('require','module','exports',output)((name) => name === 'react' ? react :
  name === '../api/client' ? {api:{}} : require(name), mod, mod.exports);
const html = renderToStaticMarkup(React.createElement(mod.exports.DeckPanel,{decks:[],onDecksLoaded(){}}));
assert.ok(html.includes('Cached/knowledge Oracle records: 0/2 available'));
assert.ok(html.includes('Offline seed Oracle: 1'));
assert.ok(html.includes('Local match data ready: 1/2. Art and rulings sync separately.'));
assert.ok(!html.includes('Card metadata: 0/2 available'));
const client = ts.createSourceFile('client.ts',fs.readFileSync(new URL('../src/api/client.ts',import.meta.url),'utf8'),ts.ScriptTarget.Latest,true);
const metadata = client.statements.find(s => ts.isTypeAliasDeclaration(s) && s.name.text === 'ResolvedCardMetadata');
assert.ok(metadata);
for (const name of ['id','card_data_sources','match_ready']) {
  const field = metadata.type.members.find(m => m.name?.getText(client) === name);
  assert.ok(field?.questionToken, `${name} must be optional for legacy responses/local projections`);
}
assert.equal((source.match(/- local metadata \$\{resolved\}/g) || []).length,3);
console.log('PASS real DeckPanel SSR labels and optional local metadata type contract (not browser qualification)');
