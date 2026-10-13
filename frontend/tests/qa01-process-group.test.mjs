import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative, resolve, isAbsolute } from 'node:path';
import { OwnedProcessGroup } from '../scripts/e2e-process-group.mjs';

const pgid = process.pid + 100000;
const member = (pid = pgid, extra = {}) => ({ pid, session: pgid, state: 'S', startTime: '100', ...extra });
function model(initial, onSignal = () => []) {
  let members = initial, clock = 0;
  const signals = [];
  const group = new OwnedProcessGroup(pgid, {
    readMembers: async () => members,
    signal: async (target, name) => { assert.equal(target, pgid); signals.push(name); members = onSignal(name, members); },
    sleep: async ms => { clock += ms; }, now: () => clock,
  });
  return { group, signals, replace: next => { members = next; } };
}
test('QA-01 cleanup: normal group shutdown verifies termination before deleting files', async () => {
  const { group, signals } = model([member(), member(pgid + 1)]);
  let deleted = false;
  await group.cleanupAfterTermination(async () => { assert.deepEqual(await group.activeMembers(), []); deleted = true; });
  assert.deepEqual(signals, ['SIGTERM']); assert.equal(deleted, true);
});
test('QA-01 cleanup: dead leader cannot hide a live descendant', async () => {
  const { group, signals, replace } = model([member(), member(pgid + 1)]);
  await group.capture(); replace([member(pgid + 1)]);
  await group.terminate(); assert.deepEqual(signals, ['SIGTERM']); assert.equal(group.terminated, true);
});
test('QA-01 cleanup: SIGTERM-ignoring descendant receives bounded SIGKILL', async () => {
  const { group, signals } = model([member(), member(pgid + 1)], (name, members) => name === 'SIGKILL' ? [] : members.filter(m => m.pid !== pgid));
  await group.terminate({ graceMs: 100, forceMs: 100 });
  assert.deepEqual(signals, ['SIGTERM', 'SIGKILL']); assert.equal(group.terminated, true);
});
test('QA-01 cleanup: failure cleanup coalesces with simultaneous shutdown requests', async () => {
  const { group, signals } = model([member()]);
  const first = group.terminate(); assert.equal(group.terminate(), first);
  await assert.rejects(async () => {
    try { throw new Error('Synthetic test failure'); }
    finally { await group.cleanupAfterTermination(async () => assert.deepEqual(await group.activeMembers(), [])); }
  }, /Synthetic test failure/);
  await first; assert.deepEqual(signals, ['SIGTERM']);
});
test('QA-01 cleanup: unverifiable termination retains the temporary directory', async () => {
  const { group, signals } = model([member(pgid + 1)], (_name, members) => members);
  let deleted = false;
  await assert.rejects(group.cleanupAfterTermination(async () => { deleted = true; }, { graceMs: 50, forceMs: 50 }), /temporary files retained/);
  assert.deepEqual(signals, ['SIGTERM', 'SIGKILL']); assert.equal(deleted, false);
});
for (const [name, changed] of [['session changed', member(pgid + 1, { session: pgid + 2 })], ['leader PID reused', member(pgid, { startTime: '200' })]]) {
  test(`QA-01 cleanup: ${name} refuses unsafe signalling/deletion`, async () => {
    const { group, signals, replace } = model([member()]);
    await group.capture(); replace([changed]); let deleted = false;
    await assert.rejects(group.cleanupAfterTermination(async () => { deleted = true; }), /identity changed|ownership changed/);
    assert.deepEqual(signals, []); assert.equal(deleted, false);
  });
}
test('QA-01 cleanup: already-exited zombie descendants require no signal', async () => {
  const { group, signals } = model([member(pgid + 1, { state: 'Z' })]);
  await group.cleanupAfterTermination(async () => assert.deepEqual(await group.activeMembers(), []));
  assert.deepEqual(signals, []); assert.equal(group.terminated, true);
});

// Real detached Linux process trees, not Next/backend services. Windows skips
// these explicitly; Ubuntu CI runs them before starting the isolated browser.
async function removeOwned(root) {
  const rel = relative(resolve(tmpdir()), resolve(root));
  assert.ok(!isAbsolute(rel) && !rel.startsWith('..') && !/[\\/]/.test(rel) && rel.startsWith('finlens-qa01-cleanup-'));
  await rm(root, { recursive: true, force: true });
}
for (const mode of ['normal shutdown', 'unexpected leader death', 'SIGTERM-ignoring descendant', 'test failure cleanup']) {
  test(`QA-01 Linux process-tree integration: ${mode}`, { skip: process.platform !== 'linux', timeout: 12000 }, async ctx => {
    const root = await mkdtemp(join(tmpdir(), 'finlens-qa01-cleanup-'));
    let tree, group, unrelated, unrelatedGroup, descendantPid;
    ctx.after(async () => {
      if (group) await group.terminate({ graceMs: 100, forceMs: 2000 });
      if (unrelatedGroup) await unrelatedGroup.terminate({ graceMs: 100, forceMs: 2000 });
      await removeOwned(root);
    });
    const ignore = mode === 'SIGTERM-ignoring descendant';
    const leafCode = `${ignore ? "process.on('SIGTERM', () => {});" : ''}process.stdout.write('ready\\n'); setInterval(() => {}, 1000);`;
    const leaderCode = `const {spawn}=require('node:child_process'); const leaf=spawn(process.execPath,['-e',${JSON.stringify(leafCode)}],{stdio:['ignore','pipe','ignore']}); leaf.stdout.once('data',()=>process.send({leaf:leaf.pid})); setInterval(()=>{},1000);`;
    tree = spawn(process.execPath, ['-e', leaderCode], { cwd: root, detached: true, stdio: ['ignore', 'ignore', 'ignore', 'ipc'] });
    const ready = once(tree, 'message', { signal: AbortSignal.timeout(3000) });
    group = new OwnedProcessGroup(tree.pid);
    const [, message] = await Promise.all([group.capture(), ready]);
    const signals = [], nativeSignal = group.signal;
    group.signal = (target, name) => { signals.push(name); return nativeSignal(target, name); };
    [{ leaf: descendantPid }] = message;
    // Separate owned control group proves termination never signals neighbours.
    unrelated = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { detached: true, stdio: 'ignore' });
    unrelatedGroup = new OwnedProcessGroup(unrelated.pid); await unrelatedGroup.capture();
    assert.ok((await group.activeMembers()).some(m => m.pid === descendantPid));
    if (mode === 'unexpected leader death') {
      const exited = once(tree, 'exit', { signal: AbortSignal.timeout(3000) });
      tree.kill('SIGKILL'); await exited;
      assert.ok((await group.activeMembers()).some(m => m.pid === descendantPid));
    }
    const cleanup = async () => {
      assert.deepEqual(await group.activeMembers(), []);
      await removeOwned(root);
    };
    if (mode === 'test failure cleanup') {
      await assert.rejects(async () => {
        try { throw new Error('Synthetic browser test failure'); }
        finally { await group.cleanupAfterTermination(cleanup, { graceMs: 200, forceMs: 2000 }); }
      }, /Synthetic browser test failure/);
    } else await group.cleanupAfterTermination(cleanup, { graceMs: 200, forceMs: 2000 });
    assert.deepEqual(await group.activeMembers(), []);
    assert.deepEqual(signals, ignore ? ['SIGTERM', 'SIGKILL'] : ['SIGTERM']);
    await assert.rejects(stat(root), error => error.code === 'ENOENT');
    assert.ok((await unrelatedGroup.activeMembers()).some(m => m.pid === unrelated.pid));
  });
}
