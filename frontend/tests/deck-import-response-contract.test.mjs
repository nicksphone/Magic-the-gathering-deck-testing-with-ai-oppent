// Protocol-only: actual client and parsers, inert fetch, no server or deck save.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import ts from 'typescript';

const apiDirectory = fileURLToPath(new URL('../src/api/', import.meta.url));
const pureManaModule = fileURLToPath(new URL('../src/components/manual-mana-output.ts', import.meta.url));
const rawBytes = fs.readFileSync(new URL('../../backend/tests/fixtures/deck_service_metadata_6900/kazandu-mammoth-scryfall-raw.json', import.meta.url));
assert.equal(createHash('sha256').update(rawBytes).digest('hex'),
  '74e2b3ef8022a0bc21fbb033e51a41db797cd195c89feb5b4c72c5e07c0b45b8');
const raw = JSON.parse(rawBytes);

function client(response) {
  const calls = [], deadlines = [], signal = Object.freeze({protocolOnly: true});
  const counts = {json: 0, text: 0};
  const modules = new Map();
  const context = vm.createContext({Error, TypeError, SyntaxError, JSON,
    AbortSignal: {timeout(ms) { deadlines.push(ms); return signal; }},
    fetch: async (url, init) => {
      calls.push({url, init});
      if (response.fetchError) throw response.fetchError;
      return {ok: response.status === undefined || response.status < 400,
        status: response.status ?? 200,
        json: async () => { counts.json++; if (response.jsonError) throw response.jsonError; return response.body; },
        text: async () => { counts.text++; return response.text; }};
    }});
  function load(filename) {
    filename = path.resolve(filename);
    assert.ok((filename.startsWith(path.resolve(apiDirectory) + path.sep) || filename === pureManaModule)
      && filename.endsWith('.ts'));
    if (modules.has(filename)) return modules.get(filename).exports;
    const mod = {exports: {}};
    modules.set(filename, mod);
    // Supply only Vite's environment object. Compile complete actual modules;
    // do not extract/reimplement req, importDeck or any response validator.
    const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename, reportDiagnostics: true,
      compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
      transformers: {before: [ctx => source => {
        const visit = node => ts.isPropertyAccessExpression(node) && node.name.text === 'env'
          && ts.isMetaProperty(node.expression) && node.expression.keywordToken === ts.SyntaxKind.ImportKeyword
          ? ts.factory.createObjectLiteralExpression([]) : ts.visitEachChild(node, visit, ctx);
        return ts.visitNode(source, visit);
      }]},
    });
    assert.equal(output.diagnostics?.filter(d => d.category === ts.DiagnosticCategory.Error).length ?? 0, 0);
    const evaluate = vm.runInContext(`(function(require, module, exports) {\n${output.outputText}\n})`, context, {filename});
    evaluate(specifier => {
      assert.ok(specifier.startsWith('.'), 'Only actual relative client dependencies may load');
      const dependency = path.resolve(path.dirname(filename), specifier);
      return load(path.extname(dependency) ? dependency : dependency + '.ts');
    }, mod, mod.exports);
    return mod.exports;
  }
  const {api} = load(path.join(apiDirectory, 'client.ts'));
  return {api, calls, deadlines, signal, counts,
    HttpResponseError: load(path.join(apiDirectory, 'errors.ts')).HttpResponseError};
}

function saved() {
  const front = raw.card_faces[0];
  return {deck_id: 7, name: 'Public response protocol', archetype_guess: 'Midrange', errors: [], suggestions: [],
    mainboard: [{quantity: 60, card_name: raw.name}], sideboard: [],
    mana_curve: {'0': 0, '1': 0, '2': 0, '3': 60, '4': 0, '5+': 0, lands: 0, unknown: 0},
    color_profile: {W: 0, U: 0, B: 0, R: 0, G: 60},
    resolved_mainboard_cards: [{quantity: 60, card_name: raw.name, card_metadata: {
      scryfall_id: raw.id, name: raw.name, oracle_text: front.oracle_text, mana_cost: front.mana_cost,
      type_line: front.type_line, layout: raw.layout, colors: front.colors, power: front.power,
      toughness: front.toughness, image_uri: null, legalities: raw.legalities,
      card_faces: raw.card_faces.map(face => ({...face, image_uri: null})),
      rulings: [], card_data_sources: ['offline_seed'], match_ready: true,
    }}], resolved_sideboard_cards: [],
    analysis: {primary_archetype: 'Midrange', secondary_archetype: 'Aggro', confidence: 0.5,
      scores: {Midrange: 1, Aggro: 1}, signals: [], land_count_estimate: 0,
      creature_density_estimate: 1, avg_cmc_estimate: 3, face_card_count_estimate: 60,
      split_card_count_estimate: 0, type_metadata_coverage: 1},
    classification_status: 'resolved', future_public_field: {full_record: raw}};
}

function freeze(value) {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) freeze(item);
    Object.freeze(value);
  }
  return value;
}

async function rejected(body, label) {
  const f = client({body: freeze(body)});
  let adopted = false;
  await assert.rejects(f.api.importDeck('Public deck', '60 ' + raw.name).then(value => {
    adopted = true;
    return value;
  }), error => error instanceof Error && error.name === 'Error'
    && /deck import response/i.test(error.message), label);
  assert.equal(adopted, false, label);
  assert.equal(f.calls.length, 1);
  assert.equal(f.counts.json, 1);
  assert.equal(f.counts.text, 0);
}

test('saved import preserves complete public card data and the original POST semantics', async () => {
  const body = freeze(saved()), f = client({body});
  const result = await f.api.importDeck('My custom deck', '60 ' + raw.name);
  assert.equal(result, body);
  assert.equal(result.resolved_mainboard_cards[0].card_metadata.card_faces[1], body.resolved_mainboard_cards[0].card_metadata.card_faces[1]);
  assert.equal(result.future_public_field.full_record, raw);
  assert.equal(result.analysis, body.analysis);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].url, '/api/decks/import');
  assert.equal(f.calls[0].init.method, 'POST');
  assert.equal(f.calls[0].init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(f.calls[0].init.body), {name: 'My custom deck', deck_text: '60 ' + raw.name, source: 'user'});
  assert.equal(f.calls[0].init.signal, f.signal);
  assert.deepEqual(f.deadlines, [30000]);
  assert.deepEqual(f.counts, {json: 1, text: 0});
});

test('unsaved parse-error response permits null IDs, null suggestions and unresolved metadata', async () => {
  const body = saved();
  body.deck_id = null; body.errors = ['Mainboard has 0 cards. Minimum is 60.'];
  body.suggestions = [{line: 1, input: 'Unresolved public input', suggestion: null, score: 0}];
  body.mainboard = [{quantity: 0, card_name: 'Unresolved public input'}];
  body.resolved_mainboard_cards = [{...body.mainboard[0], card_metadata: null}];
  body.classification_status = 'unknown'; body.archetype_guess = 'unknown';
  body.mana_curve = {unknown: 0}; body.color_profile = {};
  body.analysis = {confidence: 0, signals: ['missing_card_metadata']};
  const f = client({body: freeze(body)});
  assert.equal(await f.api.importDeck('Unresolved', '0 Unresolved public input', 'file'), body);
  assert.equal(JSON.parse(f.calls[0].init.body).source, 'file');
});

test('legacy optional projections and incomplete nullable cache metadata remain valid', async () => {
  const legacy = saved();
  delete legacy.resolved_mainboard_cards; delete legacy.resolved_sideboard_cards; delete legacy.analysis;
  assert.equal(await client({body: freeze(legacy)}).api.importDeck('Legacy', '60 ' + raw.name), legacy);
  const partial = saved();
  partial.resolved_mainboard_cards[0].card_metadata = {scryfall_id: raw.id, name: raw.name,
    power: null, toughness: null, image_uri: null, match_ready: false, future_cache_field: {value: 1}};
  partial.analysis = {};
  assert.equal(await client({body: freeze(partial)}).api.importDeck('Partial cache', '60 ' + raw.name), partial);
});

test('HTTP errors and fetch or JSON failures retain the existing request error behavior', async () => {
  const http = client({status: 422, text: '{"detail":{"message":"Public import rejection"}}'});
  await assert.rejects(http.api.importDeck('Rejected', '60 ' + raw.name), error =>
    error instanceof http.HttpResponseError && error.status === 422 && error.message === 'Public import rejection');
  assert.deepEqual(http.counts, {json: 0, text: 1});
  for (const kind of ['fetchError', 'jsonError']) {
    const error = new Error('Public transport protocol');
    const f = client({[kind]: error});
    await assert.rejects(f.api.importDeck('Rejected', '60 ' + raw.name), actual => actual === error);
    assert.equal(f.calls.length, 1);
    assert.equal(f.counts.json, kind === 'jsonError' ? 1 : 0);
  }
});

test('successful import rejects a null or array response before adoption', async () => {
  await rejected(null, 'null response');
  await rejected([], 'array response');
});

test('successful import rejects missing required text and a string deck ID', async () => {
  const missing = saved(); delete missing.name;
  await rejected(missing, 'missing name');
  await rejected({...saved(), deck_id: '7'}, 'string deck ID');
});

test('successful import rejects malformed error and suggestion rows', async () => {
  await rejected({...saved(), errors: [null]}, 'non-text error');
  await rejected({...saved(), suggestions: [{line: 1, input: 'Public input', suggestion: null, score: {}}]}, 'non-numeric score');
});

test('successful import rejects non-array boards and invalid board entries', async () => {
  await rejected({...saved(), mainboard: {}}, 'object mainboard');
  await rejected({...saved(), mainboard: [{quantity: -1, card_name: raw.name}]}, 'negative quantity');
  await rejected({...saved(), sideboard: [null]}, 'null sideboard row');
});

test('successful import rejects malformed curve and color count maps', async () => {
  await rejected({...saved(), mana_curve: []}, 'array mana curve');
  await rejected({...saved(), color_profile: {G: '60'}}, 'string color count');
});

test('present resolved boards must retain their parsed row cardinality, names and quantities', async () => {
  const cases = [
    ['missing resolved row', value => { value.resolved_mainboard_cards = []; }],
    ['different quantity', value => { value.resolved_mainboard_cards[0].quantity = 59; }],
    ['different name', value => { value.resolved_mainboard_cards[0].card_name = 'Different public row'; }],
    ['extra sideboard row', value => { value.resolved_sideboard_cards = [{quantity: 1, card_name: raw.name, card_metadata: null}]; }],
  ];
  for (const [label, change] of cases) { const value = saved(); change(value); await rejected(value, label); }
});

test('successful import rejects non-object card metadata and malformed face text', async () => {
  const arrayMetadata = saved(); arrayMetadata.resolved_mainboard_cards[0].card_metadata = [];
  await rejected(arrayMetadata, 'array metadata');
  const badFace = saved();
  badFace.resolved_mainboard_cards[0].card_metadata.card_faces[0].oracle_text = 7;
  await rejected(badFace, 'numeric face text');
});

test('optional analysis must be an object with correctly typed known values', async () => {
  await rejected({...saved(), analysis: []}, 'array analysis');
  await rejected({...saved(), analysis: {confidence: '0.5'}}, 'string confidence');
});

test('expansion import preserves saved and unsaved objects with the original encoded POST', async () => {
  const complete = saved();
  complete.resolved_mainboard_cards[0].card_metadata.power = 3;
  complete.resolved_mainboard_cards[0].card_metadata.toughness = 3;
  complete.resolved_mainboard_cards[0].card_metadata.card_faces[1].power = null;
  complete.resolved_mainboard_cards[0].card_metadata.card_faces[1].toughness = null;
  complete.catalog = {kind: 'protocol-only', future_field: {retained: true}};
  const unsaved = saved();
  unsaved.deck_id = null; unsaved.errors = ['Public parse error'];
  unsaved.resolved_mainboard_cards[0].card_metadata = null;
  for (const body of [freeze(complete), freeze(unsaved)]) {
    const f = client({body});
    assert.equal(await f.api.importExpansionTopDeck('ZNR / public'), body);
    assert.equal(f.calls.length, 1);
    assert.equal(f.calls[0].url, '/api/decks/expansion-top/ZNR%20%2F%20public/import');
    assert.equal(f.calls[0].init.method, 'POST');
    assert.equal(f.calls[0].init.headers['Content-Type'], 'application/json');
    assert.equal(f.calls[0].init.body, undefined);
    assert.equal(f.calls[0].init.signal, f.signal);
    assert.deepEqual(f.deadlines, [30000]);
    assert.deepEqual(f.counts, {json: 1, text: 0});
  }
});

test('expansion import rejects malformed successful JSON but retains typed HTTP errors', async () => {
  for (const body of [null, {...saved(), resolved_mainboard_cards: []}]) {
    const f = client({body: freeze(body)});
    let adopted = false;
    await assert.rejects(f.api.importExpansionTopDeck('ZNR').then(value => {
      adopted = true;
      return value;
    }), error => error instanceof Error && error.name === 'Error' && /deck import response/i.test(error.message));
    assert.equal(adopted, false);
    assert.equal(f.calls.length, 1);
    assert.deepEqual(f.counts, {json: 1, text: 0});
  }
  const f = client({status: 422, text: '{"detail":{"message":"Public catalog rejection"}}'});
  await assert.rejects(f.api.importExpansionTopDeck('ZNR'), error => error instanceof f.HttpResponseError
    && error.status === 422 && error.message === 'Public catalog rejection');
  assert.deepEqual(f.counts, {json: 0, text: 1});
});
