import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'vite';

export function buildDevelopmentFrontend({root, configFile, outDir}) {
  if (process.env.NODE_ENV !== 'development') throw new Error('Development frontend requires NODE_ENV=development');
  return build({root, configFile, mode: 'development',
    define: {'import.meta.env.VITE_REQUEST_SIGNAL_DIAGNOSTICS': JSON.stringify('1')},
    build: {outDir, target: 'es2022', minify: false,
    rollupOptions: {input: {application: path.join(root, 'index.html'),
      attackAll: path.join(root, 'tests/attack-all.html'),
      humanActions: path.join(root, 'tests/human-actions.html'),
      interactivePreflight: path.join(root, 'tests/interactive-preflight.html'),
      simulationPreflight: path.join(root, 'tests/simulation-preflight.html'),
      developmentProof: path.join(root, 'tests/fixtures/ci-development-runtime/probe.html')}}}});
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [root, configFile, outDir, ...extra] = process.argv.slice(2);
  if (extra.length || ![root, configFile, outDir].every(value => value && path.isAbsolute(value))) {
    throw new Error('Expected absolute frontend root, Vite config and owned output directory');
  }
  await buildDevelopmentFrontend({root, configFile, outDir});
}
