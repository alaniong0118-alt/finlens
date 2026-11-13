// Real mounted suite, two incoming-global profiles; no server or native transport.
import { describe, before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { JSDOM } from 'jsdom';

const keys = ['window', 'document', 'HTMLElement', 'Node', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
const capture = () => new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
function restore(descriptors) {
  for (const [key, descriptor] of descriptors) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
}

for (const profile of ['absent', 'neighbor']) describe(`two-filing lifecycle: ${profile} incoming globals`, { concurrency: false }, async () => {
  let original, expected, neighbor;
  before(async () => {
    original = capture();
    for (const key of keys) delete globalThis[key];
    if (profile === 'neighbor') {
      neighbor = new JSDOM('<!doctype html><html><body><p id="sentinel">Neighbor retained</p></body></html>', { url: 'http://finlens.test' });
      for (const key of keys.filter(key => key !== 'IS_REACT_ACT_ENVIRONMENT')) {
        Object.defineProperty(globalThis, key, { configurable: true, enumerable: false, writable: false, value: neighbor.window[key] });
      }
      Object.defineProperty(globalThis, 'Event', { configurable: true, enumerable: true, get: () => neighbor.window.Event });
      // Configurable/read-only is valid incoming state; ownership must define
      // its flag explicitly and restore every descriptor rather than assign it.
      Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, enumerable: false, writable: false, value: true });
    }
    expected = capture();
  });
  after(() => {
    neighbor?.window.close();
    restore(original);
  });

  // Distinct module instances exercise the actual complete suite twice. The
  // nested suite must acquire and release its own realm for every profile.
  await import(`./dual-filing-evidence.test.mjs?lifecycle=${profile}`);

  test('restores exact incoming descriptor presence, flags and identities', () => {
    for (const key of keys) {
      const actual = Object.getOwnPropertyDescriptor(globalThis, key), wanted = expected.get(key);
      assert.equal(Boolean(actual), Boolean(wanted), `${key} presence`);
      for (const flag of ['configurable', 'enumerable', 'writable']) assert.equal(actual?.[flag], wanted?.[flag], `${key} ${flag}`);
      for (const identity of ['value', 'get', 'set']) assert.ok(actual?.[identity] === wanted?.[identity], `${key} ${identity} identity`);
    }
  });
  if (profile === 'neighbor') test('neighbor can still mount and handle an event after the complete two-filing suite', async () => {
    assert.ok(document === neighbor.window.document, 'neighbor retains its original document identity');
    assert.equal(document.querySelector('#sentinel').textContent, 'Neighbor retained');
    const { createRoot } = await import('react-dom/client');
    const host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host);
    let clicks = 0;
    try {
      await act(async () => root.render(React.createElement('button', { onClick: () => { clicks++; } }, 'Neighbor button')));
      assert.equal(host.querySelector('button').ownerDocument, neighbor.window.document);
      await act(async () => host.querySelector('button').dispatchEvent(new MouseEvent('click', { bubbles: true })));
      assert.equal(clicks, 1);
    } finally {
      await act(async () => root.unmount()); host.remove();
    }
  });
});
