// Structural assignment of actual JSON literals, never JSON.parse(any) or a cast.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
const front = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
assert.ok(process.env.CATALOG_METADATA_JSON);
const rows = JSON.parse(fs.readFileSync(process.env.CATALOG_METADATA_JSON,'utf8'));
assert.ok(rows.length >= 119);
const configFile = ts.readConfigFile(path.join(front,'tsconfig.json'),ts.sys.readFile);
assert.equal(configFile.error, undefined);
const config = ts.parseJsonConfigFileContent(configFile.config,ts.sys,front);
assert.equal(config.errors.length,0);
const virtual = path.join(front,'tests/actual-metadata-response.generated.ts');
// Check each real object separately: heterogeneous array inference adds artificial
// optional-undefined dictionary keys when empty and populated legalities coexist.
const contents = `import type {ResolvedDeckCard} from '../src/api/client';\n` + rows.map((row,i) =>
  `const actual${i} = ${JSON.stringify(row)};\nexport const checked${i}: ResolvedDeckCard = actual${i};\n`).join('');
const host = ts.createCompilerHost(config.options);
const read = host.readFile.bind(host), exists = host.fileExists.bind(host), get = host.getSourceFile.bind(host);
host.readFile = file => file === virtual ? contents : read(file);
host.fileExists = file => file === virtual || exists(file);
host.getSourceFile = (file,languageVersion,onError,createNew) => file === virtual ?
  ts.createSourceFile(file,contents,languageVersion,true) : get(file,languageVersion,onError,createNew);
const program = ts.createProgram([virtual,path.join(front,'src/vite-env.d.ts')],config.options,host);
const diagnostics = ts.getPreEmitDiagnostics(program);
if (diagnostics.length) console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics,{
  getCurrentDirectory:()=>front,getCanonicalFileName:f=>f,getNewLine:()=> '\n'}));
assert.equal(diagnostics.length,0,'Actual metadata values must be assignable without casts to the frozen full response type');
const source = program.getSourceFile(path.join(front,'src/api/client.ts'));
const metadata = source.statements.find(n => ts.isTypeAliasDeclaration(n) && n.name.text === 'ResolvedCardMetadata');
const id = metadata.type.members.find(n=>n.name?.getText(source)==='scryfall_id');
assert.equal(id.questionToken,undefined);
assert.equal(id.type.kind,ts.SyntaxKind.StringKeyword);
console.log(`PASS ${rows.length} actual metadata response records: full structural TypeScript assignment, required string Scryfall ID unchanged`);
