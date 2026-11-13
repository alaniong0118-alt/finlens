// Independent strict RFC4180 reader/reconstructor for downloaded typed reports.
// Does not import the production serializer or its whitelist.
import assert from 'node:assert/strict';

export function readEvidenceCsv(csv) {
  const rows = [];
  let at = 0;
  while (at < csv.length) {
    const row = [];
    for (;;) {
      assert.equal(csv[at++], '"');
      let cell = '', closed = false;
      while (at < csv.length) {
        const char = csv[at++];
        if (char !== '"') { cell += char; continue; }
        if (csv[at] === '"') { cell += '"'; at++; continue; }
        closed = true; break;
      }
      assert.ok(closed, 'quoted field must close'); row.push(cell);
      if (csv[at] === ',') { at++; continue; }
      assert.equal(csv.slice(at, at + 2), '\r\n'); at += 2; break;
    }
    assert.equal(row.length, 3); rows.push(row);
  }
  assert.deepEqual(rows.shift(), ['path', 'type', 'value']);
  const nodes = new Map();
  for (const [path, type, text] of rows) {
    assert.equal(nodes.has(path), false, 'each path occurs once');
    let value;
    if (type === 'object' || type === 'array' || type === 'null') {
      assert.equal(text, ''); value = type === 'object' ? {} : type === 'array' ? [] : null;
    } else if (type === 'string') value = text;
    else if (type === 'boolean') { assert.match(text, /^(true|false)$/); value = text === 'true'; }
    else { assert.equal(type, 'number'); value = Number(text); assert.ok(Number.isFinite(value)); }
    if (path) {
      assert.ok(path.startsWith('/')); const slash = path.lastIndexOf('/');
      const parent = nodes.get(path.slice(0, slash)), key = path.slice(slash + 1);
      assert.ok(parent && typeof parent === 'object');
      assert.ok(!['__proto__', 'prototype', 'constructor'].includes(key));
      assert.equal(Object.hasOwn(parent, key), false);
      if (Array.isArray(parent)) assert.equal(key, String(parent.length));
      parent[key] = value;
    } else assert.equal(nodes.size, 0);
    nodes.set(path, value);
  }
  assert.ok(nodes.has('')); return nodes.get('');
}
