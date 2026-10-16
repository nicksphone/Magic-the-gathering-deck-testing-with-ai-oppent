import React, {StrictMode, useEffect} from 'react';
import {createRoot} from 'react-dom/client';

const counts = {renders: 0, mounts: 0, cleanups: 0};
const environment = {nodeEnv: process.env.NODE_ENV, dev: import.meta.env.DEV, prod: import.meta.env.PROD};
globalThis.__MTG_DEVELOPMENT_RUNTIME_PROOF__ = {reactVersion: React.version, environment, counts};

function ReplayProof() {
  counts.renders++;
  useEffect(() => {
    counts.mounts++;
    return () => { counts.cleanups++; };
  }, []);
  return React.createElement('span', null, 'Development runtime proof');
}

createRoot(document.getElementById('root')).render(
  React.createElement(StrictMode, null, React.createElement(ReplayProof)),
);
