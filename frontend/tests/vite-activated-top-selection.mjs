import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(`${process.env.MTG_FRONTEND_DEPS}/package.json`);
const {defineConfig} = await import(require.resolve('vite'));
const {default: react} = await import(require.resolve('@vitejs/plugin-react'));
export default defineConfig({
  root: path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'),
  cacheDir: `${process.env.MTG_OFFICER_RUNTIME}/vite-cache`,
  plugins: [react()],
  resolve: {alias: {
    react: path.dirname(require.resolve('react/package.json')),
    'react-dom': path.dirname(require.resolve('react-dom/package.json')),
  }},
  server: {host: '127.0.0.1', port: 15237, strictPort: true,
    fs: {allow: [path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), process.env.MTG_FRONTEND_DEPS]}},
});
