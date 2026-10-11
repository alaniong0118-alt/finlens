// Offline bridge: consume an actual API JSON response and exercise the real
// frontend parser and renderer. Invoked by the bounded backend regression.
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { evidencePassages } from '../lib/research.ts';

const require = createRequire(import.meta.url);
const cache = new Map();
function component(path) {
  if (cache.has(path)) return cache.get(path);
  const exports = {};
  const output = ts.transpileModule(readFileSync(path, 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = name => {
    if (!name.startsWith('@/')) return require(name);
    const base = fileURLToPath(new URL(`../${name.slice(2)}`, import.meta.url));
    return component(['.tsx', '.ts'].map(extension => base + extension).find(existsSync));
  };
  new Function('require', 'exports', output)(localRequire, exports);
  cache.set(path, exports);
  return exports;
}

const { EvidenceResults } = component(fileURLToPath(new URL('../components/filing-research.tsx', import.meta.url)));
const result = JSON.parse(readFileSync(0, 'utf8'));
const html = renderToStaticMarkup(React.createElement(EvidenceResults, { result }));
// Decode React's text escapes once; this reads the actual complete-passage nodes,
// not previews or metadata. No HTML whitespace normalization hides text changes.
const entities = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'" };
const displayedTexts = [...html.matchAll(/<p class="excerpt details-body">([\s\S]*?)<\/p>/g)]
  .map(match => match[1].replace(/&(?:amp|lt|gt|quot|#x27);/g, entity => entities[entity]));
process.stdout.write(JSON.stringify({
  passages: evidencePassages(result),
  html, displayedTexts,
}));
