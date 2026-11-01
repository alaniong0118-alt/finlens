import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import ts from 'typescript';

// Load real component dependencies; relative imports belong to their importer.
export function componentLoader(frontendRoot) {
  const cache = new Map();
  function load(filename) {
    filename = resolve(filename);
    if (cache.has(filename)) return cache.get(filename);
    const module = { exports: {} };
    cache.set(filename, module.exports); // Also expose partial exports to cycles.
    const output = ts.transpileModule(readFileSync(filename, 'utf8'), { compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020, esModuleInterop: true,
    } }).outputText;
    const localRequire = name => {
      if (!name.startsWith('@/') && !name.startsWith('.')) return createRequire(filename)(name);
      const base = name.startsWith('@/') ? resolve(frontendRoot, name.slice(2)) : resolve(dirname(filename), name);
      const dependency = [base, base + '.tsx', base + '.ts', resolve(base, 'index.tsx'), resolve(base, 'index.ts')]
        .find(candidate => existsSync(candidate) && /\.[cm]?[jt]sx?$/.test(candidate));
      if (!dependency) throw new Error(`Cannot resolve ${name} from ${filename}`);
      return load(dependency);
    };
    try {
      new Function('require', 'exports', 'module', output)(localRequire, module.exports, module);
      cache.set(filename, module.exports);
      return module.exports;
    } catch (error) { cache.delete(filename); throw error; }
  }
  return load;
}
