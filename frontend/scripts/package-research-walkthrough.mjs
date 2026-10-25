import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync as executeFileSync, spawn, spawnSync } from 'node:child_process';
import { lstat, mkdir, readFile, readdir, realpath, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crc32, deflateSync, inflateSync } from 'node:zlib';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repository = resolve(frontend, '..');
const root = join(frontend, 'test-results', 'research-walkthrough');
const label = 'SYNTHETIC TEST DATA — NOT REAL SEC FINANCIAL RESULTS';
const baseline = '2e45d04b2adec942d90c3548c3a104a990c7f249';
const pngNames = ['01-synthetic-company-revenue.png', '02-synthetic-period-provenance.png',
  '03-synthetic-annual-comparison.png', '04-synthetic-copy-freshness.png'];
const noteName = 'synthetic-research-note.md';
const rawNames = [...pngNames, noteName, 'capture.json'];
const captureBindings = ['frontend/e2e/fixtures/data.ts', 'frontend/e2e/fixtures/browser.ts',
  'frontend/e2e/fixtures/ignored-abort.ts', 'frontend/playwright.config.ts',
  'frontend/playwright.capture.config.ts', 'frontend/e2e/research-walkthrough.capture.ts'];
const sourceNames = [...captureBindings, 'frontend/scripts/e2e-server.mjs',
  'frontend/scripts/e2e-process-group.mjs', 'frontend/scripts/package-research-walkthrough.mjs',
  'frontend/package-lock.json', '.github/workflows/frontend-e2e.yml'];
// Exact inventory of the unchanged launcher's cp loop, including optional roots.
const copyRoots = ['app', 'components', 'lib', 'public', 'next.config.ts', 'next-env.d.ts',
  'package.json', 'tsconfig.json', 'postcss.config.js', 'postcss.config.mjs', 'tailwind.config.ts', 'tailwind.config.js'];
const inventoryLimits = { entries: 4096, fileBytes: 10_000_000, totalBytes: 64_000_000, pathBytes: 512 };
const excluded = name => name.split('/').some(part => /^\.env(?:\.|$)/.test(part));
const ordinal = (a, b) => a < b ? -1 : a > b ? 1 : 0;
const settings = { viewport: { width: 1440, height: 1000 }, theme: 'light', locale: 'en-US', timezone: 'UTC', scale: 1 };
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const json = object => `${JSON.stringify(object, null, 2)}\n`;
const escapeHtml = text => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const decode = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
const packagingStages = Object.freeze(['PRECONDITIONS', 'RAW_CUSTODY', 'METADATA_SCHEMA', 'NETWORK_LEDGER',
  'PLAYWRIGHT_RESULT', 'CLEANUP_RECEIPT', 'RENDER_INVENTORY', 'NATIVE_NOTE',
  'PNG_01', 'PNG_02', 'PNG_03', 'PNG_04', 'SOURCE_BINDINGS', 'CI_IDENTITY', 'MANIFEST_VALIDATION', 'PUBLICATION']);
const pngStages = Object.freeze(['PNG_01', 'PNG_02', 'PNG_03', 'PNG_04']);
let failureStage = 'UNKNOWN';
function setFailureStage(stage) {
  failureStage = packagingStages.includes(stage) ? stage : 'UNKNOWN';
}
function reportPackageFailure() {
  console.error(`RW-PACKAGE-FAIL stage=${packagingStages.includes(failureStage) ? failureStage : 'UNKNOWN'}`);
  process.exitCode = 1;
}
function execFileSync(file, args, options) {
  // Node otherwise echoes child stderr before throwing. Package diagnostics must
  // not forward Git error text; stdout, exit checks and other modes are unchanged.
  return executeFileSync(file, args, process.argv[2] === '--package' ? { ...options, stdio: 'pipe' } : options);
}

function inside(base, target) {
  const rel = relative(base, target);
  assert(rel && !isAbsolute(rel) && rel !== '..' && !rel.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`), 'Path outside owned subtree');
  return target;
}
async function noLinks(base, target) {
  inside(base, target);
  assert.equal(await realpath(base), base, 'Base must have canonical custody');
  let current = base;
  for (const part of relative(base, target).split(/[\\/]/)) {
    current = join(current, part);
    const info = await lstat(current);
    assert(!info.isSymbolicLink(), 'Symlink input/output refused');
  }
}
async function boundedRead(base, target, maxBytes) {
  await noLinks(base, target);
  const info = await lstat(target);
  assert(info.isFile() && info.size > 0 && info.size <= maxBytes, 'Invalid file type/size');
  const bytes = await readFile(target);
  assert(bytes.length <= maxBytes, 'File changed beyond size bound');
  return bytes;
}
function inventoryRecord(revision, entries) {
  assert(/^[a-f0-9]{40}$/.test(revision));
  assert(entries.length > 0 && entries.length <= inventoryLimits.entries);
  let total = 0;
  const seen = new Set();
  for (const entry of entries) {
    assert.equal(typeof entry.path, 'string');
    const parts = entry.path.split('/');
    assert(parts[0] === 'frontend' && copyRoots.includes(parts[1]) && !excluded(entry.path));
    assert(parts.every(part => part && part !== '.' && part !== '..') && !/[\\\x00-\x1f\x7f]/.test(entry.path));
    assert(Buffer.byteLength(entry.path) <= inventoryLimits.pathBytes && !seen.has(entry.path)); seen.add(entry.path);
    if (entry.kind === 'directory') exactKeys(entry, ['path', 'kind']);
    else {
      exactKeys(entry, ['path', 'kind', 'bytes', 'sha256', 'executable']);
      assert.equal(entry.kind, 'file'); assert.equal(typeof entry.executable, 'boolean');
      assert(Number.isSafeInteger(entry.bytes) && entry.bytes >= 0 && entry.bytes <= inventoryLimits.fileBytes);
      assert(/^[a-f0-9]{64}$/.test(entry.sha256)); total += entry.bytes;
    }
  }
  assert(total <= inventoryLimits.totalBytes);
  const body = { schema_version: 1, source_revision: revision, copy_roots: copyRoots,
    entries: [...entries].sort((a, b) => ordinal(a.path, b.path)) };
  return { ...body, sha256: sha256(Buffer.from(json(body))) };
}
function validateInventory(record, revision) {
  assert.deepEqual(record, inventoryRecord(revision, record.entries), 'Inconsistent render inventory');
}
function admitInventory(revision, committed, observed) {
  const intended = inventoryRecord(revision, committed), actual = inventoryRecord(revision, observed);
  const byPath = new Map(observed.map(entry => [entry.path, entry]));
  const ordered = [...committed].sort((a, b) => Number(b.path === 'frontend/next-env.d.ts') - Number(a.path === 'frontend/next-env.d.ts') || ordinal(a.path, b.path));
  for (const entry of ordered) assert.deepEqual(byPath.get(entry.path), entry, `Render input differs from reviewed commit: ${entry.path}`);
  assert.deepEqual(actual, intended, 'Missing or extra copied render inputs');
  return intended;
}
async function scanCopiedInputs(io = {
  stat: name => lstat(join(repository, name)),
  children: name => readdir(join(repository, name)),
  read: name => readFile(join(repository, name)),
}) {
  const entries = []; let total = 0;
  const walk = async name => {
    // Exclude before stat/read/recursion: private env files are never opened or hashed.
    if (excluded(name)) return;
    assert(entries.length < inventoryLimits.entries && Buffer.byteLength(name) <= inventoryLimits.pathBytes);
    const info = await io.stat(name);
    assert(!info.isSymbolicLink(), 'Copied source symlink refused');
    if (info.isDirectory()) {
      entries.push({ path: name, kind: 'directory' });
      const children = await io.children(name); assert(children.length <= inventoryLimits.entries);
      for (const child of children.sort(ordinal)) {
        assert(child && !/[\\/\x00-\x1f\x7f]/.test(child) && child !== '.' && child !== '..');
        await walk(`${name}/${child}`);
      }
    } else {
      assert(info.isFile() && info.size >= 0 && info.size <= inventoryLimits.fileBytes);
      total += info.size; assert(total <= inventoryLimits.totalBytes);
      const bytes = await io.read(name); assert.equal(bytes.length, info.size);
      entries.push({ path: name, kind: 'file', bytes: bytes.length, sha256: sha256(bytes), executable: !!(info.mode & 0o111) });
    }
  };
  for (const name of copyRoots) {
    const path = `frontend/${name}`;
    try { await walk(path); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return entries;
}
function committedRenderInputs(revision) {
  const git = args => execFileSync('git', ['--no-optional-locks', ...args], { cwd: repository, maxBuffer: 4_000_000 });
  const launcherPath = 'frontend/scripts/e2e-server.mjs';
  const launcher = git(['show', `${revision}:${launcherPath}`]);
  assert(launcher.equals(git(['show', `${baseline}:${launcherPath}`])), 'Launcher copy policy changed; requires new review');
  const inventory = launcher.toString('utf8').match(/for \(const name of (\[[^\n]+\])\)/);
  assert(inventory); assert.deepEqual(JSON.parse(inventory[1].replaceAll("'", '"')), copyRoots);
  const rows = decode(git(['ls-tree', '-r', '-t', '-z', revision, '--', ...copyRoots.map(name => `frontend/${name}`)])).split('\0').filter(Boolean);
  assert(rows.length <= inventoryLimits.entries);
  const entries = []; let total = 0;
  for (const row of rows) {
    const match = row.match(/^(\d{6}) (blob|tree) ([a-f0-9]{40})\t(.+)$/); assert(match);
    const [, mode, type, oid, path] = match;
    if (path === 'frontend') continue; // ls-tree -t includes this uncopied ancestor.
    if (excluded(path)) continue;
    if (type === 'tree') { assert.equal(mode, '040000'); entries.push({ path, kind: 'directory' }); }
    else {
      assert(['100644', '100755'].includes(mode), 'Unsupported reviewed input type');
      const size = Number(git(['cat-file', '-s', oid]).toString().trim());
      assert(Number.isSafeInteger(size) && size >= 0 && size <= inventoryLimits.fileBytes);
      total += size; assert(total <= inventoryLimits.totalBytes);
      const bytes = execFileSync('git', ['cat-file', 'blob', oid], { cwd: repository, maxBuffer: inventoryLimits.fileBytes + 1 });
      assert.equal(bytes.length, size);
      entries.push({ path, kind: 'file', bytes: size, sha256: sha256(bytes), executable: mode === '100755' });
    }
  }
  return entries;
}
async function collectRenderInventory(revision) {
  assert.equal(await realpath(frontend), frontend);
  const admitted = admitInventory(revision, committedRenderInputs(revision), await scanCopiedInputs());
  const launcherPath = 'frontend/scripts/e2e-server.mjs';
  const reviewedLauncher = execFileSync('git', ['show', `${revision}:${launcherPath}`], { cwd: repository, maxBuffer: 200_000 });
  assert((await boundedRead(repository, join(repository, launcherPath), 200_000)).equals(reviewedLauncher),
    'Actual launcher differs from reviewed copy policy');
  return admitted;
}
function publicText(text) {
  assert(!/(?:\b[A-Za-z]:[\\/]|\\\\|\/(?:home|Users|tmp|private|runner|workspace)\/)/i.test(text), 'Private host path refused');
  assert(!/(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|BEGIN [A-Z ]*PRIVATE KEY|(?:password|api[_-]?key|access[_-]?token)\s*[=:])/i.test(text), 'Credential-like text refused');
  assert(!text.includes('\0'), 'NUL text refused');
}
function iso(value) {
  assert.equal(typeof value, 'string');
  assert(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value) && new Date(value).toISOString() === value, 'Invalid execution timestamp');
  return Date.parse(value);
}
function exactKeys(object, keys) { assert.deepEqual(Object.keys(object).sort(), [...keys].sort()); }
function validateMetadata(meta) {
  exactKeys(meta, ['schema_version', 'label', 'expected_baseline', 'source_revision', 'test', 'project', 'config',
    'settings', 'runtime', 'started_at', 'completed_at', 'captures', 'bindings', 'clipboard', 'network', 'execution_scope',
    'render_inventory', 'admission_sha256']);
  assert.equal(meta.schema_version, 1); assert.equal(meta.label, label); assert.equal(meta.expected_baseline, baseline);
  assert(/^[a-f0-9]{40}$/.test(meta.source_revision));
  validateInventory(meta.render_inventory, meta.source_revision);
  assert(/^[a-f0-9]{64}$/.test(meta.admission_sha256));
  assert.equal(meta.test, 'portable synthetic research walkthrough');
  assert.equal(meta.project, 'synthetic-walkthrough-chromium');
  assert.equal(meta.config, 'frontend/playwright.capture.config.ts');
  assert.equal(meta.execution_scope, 'synthetic frontend only; live database NOT VERIFIED');
  assert.deepEqual(meta.settings, settings);
  exactKeys(meta.runtime, ['node', 'platform', 'arch', 'chromium', 'playwright', 'next']);
  assert.equal(meta.runtime.platform, 'linux'); assert(/^v24\./.test(meta.runtime.node));
  assert.equal(meta.runtime.playwright, '1.64.0');
  assert(['x64', 'arm64'].includes(meta.runtime.arch));
  for (const field of ['chromium', 'next']) assert(/^\d+(?:\.\d+){1,3}$/.test(meta.runtime[field]));
  const start = iso(meta.started_at), end = iso(meta.completed_at);
  assert(end >= start && end - start <= 45_000, 'Capture exceeds existing per-test budget');
  assert.equal(meta.captures.length, 4);
  let previous = start;
  meta.captures.forEach((capture, index) => {
    exactKeys(capture, ['name', 'captured_at', 'full_page']);
    assert.equal(capture.name, pngNames[index]); assert.equal(capture.full_page, index === 3);
    const time = iso(capture.captured_at); assert(time >= previous && time <= end); previous = time;
  });
  exactKeys(meta.bindings, captureBindings);
  for (const hash of Object.values(meta.bindings)) assert(/^[a-f0-9]{64}$/.test(hash));
  exactKeys(meta.clipboard, ['mechanism', 'encoding', 'sha256']);
  assert.equal(meta.clipboard.mechanism, 'native Chromium navigator.clipboard.readText');
  assert.equal(meta.clipboard.encoding, 'UTF-8'); assert(/^[a-f0-9]{64}$/.test(meta.clipboard.sha256));
  setFailureStage('NETWORK_LEDGER');
  exactKeys(meta.network, ['requests', 'failures', 'violations']);
  assert.deepEqual(meta.network.failures, []); assert.deepEqual(meta.network.violations, []);
  assert(meta.network.requests.length > 0 && meta.network.requests.length <= 200);
  for (const request of meta.network.requests) {
    exactKeys(request, ['method', 'path', 'pin', 'query']);
    assert.equal(request.method, 'GET');
    assert(/^\/(?:companies|capabilities|companies\/(?:AAA|BBB)\/(?:freshness|sources|financials\/(?:summary|annual|metrics\/revenue)))$/.test(request.path));
    assert.equal(typeof request.query, 'string');
    const match = request.path.match(/^\/companies\/(AAA|BBB)\/(.+)$/);
    const query = [...new URLSearchParams(request.query)].sort(([a], [b]) => a.localeCompare(b));
    if (!match || match[2] === 'freshness') { assert.equal(request.pin, null); assert.deepEqual(query, []); }
    else {
      assert.equal(request.pin, match[1] === 'AAA' ? '0' : '1');
      if (match[2] === 'sources') assert.deepEqual(query, []);
      if (match[2] === 'financials/summary') assert.deepEqual(query, [['period', 'quarter']]);
      if (match[2] === 'financials/metrics/revenue') assert.deepEqual(query, [['limit', '12'], ['period', 'quarter']]);
      if (match[2] === 'financials/annual') assert(query.length === 0 || json(query) === json([['fiscal_year', '2025']]));
    }
  }
  setFailureStage('METADATA_SCHEMA');
  publicText(json(meta));
}
function validateNote(bytes) {
  const note = decode(bytes);
  assert(note.startsWith('# FinLens research note\n') && note.endsWith('\n'));
  for (const token of ['- Metric: Revenue\n', '- Comparison: Annual fiscal end-year 2025\n',
    '- Ticker: AAA\n', '- Ticker: BBB\n', '- Exact normalized value: 5000000000\n',
    '- Exact normalized value: 9000000000\n', '- Independent publication version: 0\n',
    '- Independent publication version: 1\n', 'publication versions are not freshness guarantees.']) assert(note.includes(token), 'Incomplete native note');
  publicText(note);
  return note;
}
function validatePng(bytes, index) {
  assert(Buffer.isBuffer(bytes) && bytes.length <= 20_000_000 && bytes.length >= 45);
  assert(bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])));
  let offset = 8, count = 0, header, ended = false, dataEnded = false, sawData = false;
  const compressed = [], ancillary = new Set(); let compressedBytes = 0;
  while (offset < bytes.length) {
    assert(++count <= 4096 && offset + 12 <= bytes.length, 'Malformed PNG chunk boundary');
    const length = bytes.readUInt32BE(offset), end = offset + 12 + length;
    assert(length <= 20_000_000 && end <= bytes.length, 'Malformed PNG chunk length');
    const type = bytes.toString('latin1', offset + 4, offset + 8);
    assert(/^[A-Za-z]{4}$/.test(type) && !(bytes[offset + 6] & 32), 'Invalid PNG chunk type');
    assert.equal(crc32(bytes.subarray(offset + 4, end - 4)), bytes.readUInt32BE(end - 4), 'PNG CRC mismatch');
    const chunk = bytes.subarray(offset + 8, end - 4);
    if (!header) {
      assert(type === 'IHDR' && length === 13 && count === 1, 'IHDR must be first');
      const width = chunk.readUInt32BE(0), height = chunk.readUInt32BE(4), color = chunk[9];
      assert.equal(width, 1440);
      assert(index === 3 ? height >= 1000 && height <= 30_000 : height === 1000);
      assert(chunk[8] === 8 && [2, 6].includes(color) && chunk[10] === 0 && chunk[11] === 0 && chunk[12] === 0,
        'Only noninterlaced 8-bit RGB/RGBA PNG is supported');
      const channels = color === 2 ? 3 : 4, stride = width * channels, decodedBytes = (stride + 1) * height;
      assert(decodedBytes <= 128 * 1024 * 1024, 'Decoded PNG exceeds memory ceiling');
      header = { width, height, color, channels, stride, decodedBytes };
    } else if (type === 'IDAT') {
      assert(!dataEnded, 'IDAT chunks must be consecutive'); sawData = true;
      compressedBytes += length; assert(compressedBytes <= 20_000_000); compressed.push(chunk);
    } else if (type === 'IEND') {
      assert(length === 0 && sawData && compressedBytes > 0 && end === bytes.length, 'Invalid or incomplete IEND');
      ended = true;
    } else {
      // These non-image ancillary chunks have explicit layouts. Everything else,
      // including palette, transparency, ICC, animation and unknown chunks, fails closed.
      assert(!sawData && ['sRGB', 'gAMA', 'pHYs'].includes(type) && !ancillary.has(type), 'Unsupported PNG chunk/order');
      ancillary.add(type);
      if (type === 'sRGB') assert(length === 1 && chunk[0] <= 3);
      if (type === 'gAMA') assert(length === 4 && chunk.readUInt32BE(0) > 0);
      if (type === 'pHYs') assert(length === 9 && chunk[8] <= 1);
    }
    if (sawData && type !== 'IDAT') dataEnded = true;
    offset = end;
  }
  assert(ended && header && sawData && offset === bytes.length, 'Missing PNG image data/end');
  const input = Buffer.concat(compressed, compressedBytes);
  const inflated = inflateSync(input, { maxOutputLength: header.decodedBytes, info: true });
  assert.equal(inflated.engine.bytesWritten, input.length, 'Trailing/concatenated compressed data');
  assert.equal(inflated.buffer.length, header.decodedBytes, 'Wrong PNG row geometry');
  let prior = Buffer.alloc(header.stride), row = Buffer.alloc(header.stride);
  const pixels = createHash('sha256');
  for (let y = 0; y < header.height; y++) {
    const start = y * (header.stride + 1), filter = inflated.buffer[start];
    assert(filter <= 4, 'Invalid PNG row filter');
    for (let x = 0; x < header.stride; x++) {
      const left = x >= header.channels ? row[x - header.channels] : 0;
      const up = prior[x], upperLeft = x >= header.channels ? prior[x - header.channels] : 0;
      let predictor = 0;
      if (filter === 1) predictor = left;
      if (filter === 2) predictor = up;
      if (filter === 3) predictor = Math.floor((left + up) / 2);
      if (filter === 4) {
        const p = left + up - upperLeft, a = Math.abs(p - left), b = Math.abs(p - up), c = Math.abs(p - upperLeft);
        predictor = a <= b && a <= c ? left : b <= c ? up : upperLeft;
      }
      row[x] = (inflated.buffer[start + 1 + x] + predictor) & 255;
    }
    pixels.update(row); [prior, row] = [row, prior];
  }
  return { width: header.width, height: header.height, bit_depth: 8, color_type: header.color,
    decoded_bytes: header.decodedBytes, decoded_pixels_sha256: pixels.digest('hex') };
}
function validateResult(report, metadata) {
  assert.deepEqual(report.errors, []);
  for (const [key, count] of Object.entries({ expected: 1, unexpected: 0, flaky: 0, skipped: 0 })) assert.equal(report.stats[key], count);
  const specs = [];
  const visit = suite => { specs.push(...(suite.specs ?? [])); (suite.suites ?? []).forEach(visit); };
  report.suites.forEach(visit);
  assert.equal(specs.length, 1); assert.equal(specs[0].title, 'portable synthetic research walkthrough');
  assert.equal(specs[0].ok, true); assert.equal(specs[0].tests.length, 1);
  const test = specs[0].tests[0];
  assert.equal(test.projectName, 'synthetic-walkthrough-chromium'); assert.equal(test.status, 'expected');
  assert.equal(test.results.length, 1); assert.equal(test.results[0].status, 'passed');
  assert.equal(test.results[0].retry, 0); assert(!test.results[0].error);
  assert.deepEqual(test.results[0].errors ?? [], []);
  if (metadata) {
    const start = iso(test.results[0].startTime), duration = test.results[0].duration;
    assert(Number.isFinite(duration) && duration >= 0 && duration <= 45_000);
    assert(iso(metadata.started_at) >= start && iso(metadata.completed_at) <= start + duration,
      'Runner result does not cover this capture interval');
  }
}
function ciIdentity(env) {
  if (env.CI !== 'true') return { run_id: null, job: null, attempt: null };
  assert.equal(env.GITHUB_ACTIONS, 'true', 'CI capture requires the reviewed GitHub job');
  assert(/^\d+$/.test(env.GITHUB_RUN_ID ?? '') && /^[1-9]\d*$/.test(env.GITHUB_RUN_ATTEMPT ?? ''));
  assert.equal(env.GITHUB_JOB, 'synthetic_capture');
  return { run_id: env.GITHUB_RUN_ID, job: env.GITHUB_JOB, attempt: env.GITHUB_RUN_ATTEMPT };
}
function validateCleanup(receipt, metadata) {
  exactKeys(receipt, ['source_revision', 'launcher_sha256', 'started_at', 'completed_at', 'exit_code', 'signal', 'render_inventory_sha256']);
  assert.equal(receipt.source_revision, metadata.source_revision);
  assert(/^[a-f0-9]{64}$/.test(receipt.launcher_sha256));
  assert.equal(receipt.render_inventory_sha256, metadata.render_inventory.sha256);
  assert.equal(receipt.exit_code, 0); assert.equal(receipt.signal, null);
  assert(iso(receipt.started_at) <= iso(metadata.started_at));
  assert(iso(receipt.completed_at) >= iso(metadata.completed_at));
}

// Playwright's graceful close waits for a close event, not a successful launcher
// exit code. Keep that exit evidence separately; never infer cleanup from PNGs.
async function serveWithReceipt() {
  assert.equal(process.env.FINLENS_CAPTURE_AUTHORIZED, 'true');
  assert.equal(process.platform, 'linux');
  const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repository, encoding: 'utf8' }).trim();
  assert.equal(revision, process.env.FINLENS_CAPTURE_REVISION);
  // Admission happens before launcher spawn or output creation. Protected dirty
  // next-env is not an exception; a clean, reviewed Linux checkout is required.
  const admitted = await collectRenderInventory(revision);
  assert.equal(await realpath(frontend), frontend);
  for (const path of [join(frontend, 'test-results'), root]) {
    await mkdir(path).catch(error => { if (error.code !== 'EEXIST') throw error; });
    await noLinks(frontend, path); assert((await lstat(path)).isDirectory());
  }
  const receiptPath = join(root, 'cleanup.json');
  for (const name of ['source-admission.json', 'cleanup.json', 'raw', 'package', 'result.json']) {
    await lstat(join(root, name)).then(() => { throw new Error('Existing evidence output refused'); }, error => {
      if (error.code !== 'ENOENT') throw error;
    });
  }
  const launcherHash = sha256(await boundedRead(frontend, join(frontend, 'scripts', 'e2e-server.mjs'), 200_000));
  await writeFile(join(root, 'source-admission.json'), json(admitted), { flag: 'wx' });
  const startedAt = new Date().toISOString();
  const child = spawn(process.execPath, ['scripts/e2e-server.mjs'], { cwd: frontend, stdio: 'inherit', windowsHide: true });
  let stopping = false;
  const stop = signal => { stopping = true; child.kill(signal); };
  const term = () => stop('SIGTERM'), interrupt = () => stop('SIGINT');
  process.on('SIGTERM', term); process.on('SIGINT', interrupt);
  try {
    const result = await new Promise((done, reject) => {
      child.once('error', reject); child.once('close', (code, signal) => done({ code, signal }));
    });
    assert(stopping && result.code === 0 && result.signal === null, 'Launcher did not finish verified graceful cleanup');
    assert.deepEqual(await collectRenderInventory(revision), admitted, 'Render inputs changed during execution');
    await writeFile(receiptPath, json({ source_revision: revision, launcher_sha256: launcherHash,
      started_at: startedAt, completed_at: new Date().toISOString(), exit_code: result.code, signal: result.signal,
      render_inventory_sha256: admitted.sha256 }), { flag: 'wx' });
  } finally { process.off('SIGTERM', term); process.off('SIGINT', interrupt); }
}
function viewer(images, note) {
  const captions = ['Selected Synthetic Alpha and quarterly Revenue.', 'Quarterly reporting period and supplied synthetic provenance.',
    'FY2025 annual Alpha $5B / Beta $9B; independent publications 0 / 1.',
    'Full-page record: actual native copy feedback and expanded freshness limitations.'];
  return `<!doctype html>\n<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>FinLens synthetic research walkthrough</title><style>body{max-width:1440px;margin:auto;padding:24px;font:17px/1.5 system-ui;color:#17283b;background:#f5f7fa}h1,.label{background:#fff3cd;color:#402b00;padding:16px}figure{margin:32px 0}img{width:100%;height:auto;border:1px solid #789}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:24px}figcaption{font-weight:bold}</style>
<h1>${label}</h1><p>Actual frontend rendering with intercepted test responses. Capture annotations are added only by the capture scenario. No live database, SEC or provider verification. Synthetic URLs, including synthetic.htm, are illustrative identities and were never opened.</p>
<p>Historical prepared-data records remain separately labelled in the existing showcase manifest. Their original PASS/FAIL/BLOCKED scopes are unchanged. Current live database data: NOT VERIFIED.</p>
${images.map((bytes, index) => `<figure><figcaption><span class="label">${label}</span><p>${captions[index]}</p></figcaption><img alt="${captions[index]} ${label}" src="data:image/png;base64,${bytes.toString('base64')}"></figure>`).join('\n')}
<h2>${label}</h2><p>Native clipboard note, displayed as escaped text. The companion ${noteName} retains its original UTF-8 bytes; links are inert text here.</p><pre>${escapeHtml(note)}</pre>
<p>Freshness status and timestamps are fixed fixture inputs. A publication version is not a freshness guarantee. Shared fiscal labels do not prove comparability; no cross-company calculation is supplied. No byte-identical PNG guarantee across differing runtimes. Rehearsal and independent artifact acceptance remain separate gates.</p></html>\n`;
}

async function packageEvidence() {
  setFailureStage('PRECONDITIONS');
  assert.equal(process.env.FINLENS_CAPTURE_AUTHORIZED, 'true', 'Execution authorization switch is OFF');
  assert.equal(process.platform, 'linux');
  const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repository, encoding: 'utf8' }).trim();
  assert.equal(revision, process.env.FINLENS_CAPTURE_REVISION);
  execFileSync('git', ['merge-base', '--is-ancestor', baseline, revision], { cwd: repository, stdio: 'pipe' });
  setFailureStage('RAW_CUSTODY');
  const raw = inside(root, join(root, 'raw'));
  await noLinks(frontend, raw);
  assert.deepEqual((await readdir(raw)).sort(), [...rawNames].sort(), 'Exactly four PNGs, one note and metadata required');
  const bytes = Object.fromEntries(await Promise.all(rawNames.map(async name =>
    [name, await boundedRead(root, join(raw, name), name.endsWith('.png') ? 20_000_000 : 2_000_000)])));
  setFailureStage('METADATA_SCHEMA');
  const metadata = JSON.parse(decode(bytes['capture.json'])); validateMetadata(metadata);
  assert.equal(metadata.source_revision, revision);
  assert.equal(metadata.runtime.node, process.version); assert.equal(metadata.runtime.arch, process.arch);
  setFailureStage('PLAYWRIGHT_RESULT');
  const report = JSON.parse(decode(await boundedRead(root, join(root, 'result.json'), 2_000_000)));
  validateResult(report, metadata);
  setFailureStage('CLEANUP_RECEIPT');
  const cleanup = JSON.parse(decode(await boundedRead(root, join(root, 'cleanup.json'), 20_000)));
  validateCleanup(cleanup, metadata);
  setFailureStage('RENDER_INVENTORY');
  const admissionBytes = await boundedRead(root, join(root, 'source-admission.json'), 2_000_000);
  const admitted = JSON.parse(decode(admissionBytes)); validateInventory(admitted, revision);
  assert.equal(sha256(admissionBytes), metadata.admission_sha256);
  assert.deepEqual(admitted, metadata.render_inventory, 'Admission/capture inventory mismatch');
  assert.deepEqual(await collectRenderInventory(revision), admitted, 'Package-phase render inventory mismatch');
  setFailureStage('NATIVE_NOTE');
  const note = validateNote(bytes[noteName]); assert.equal(sha256(bytes[noteName]), metadata.clipboard.sha256);
  const pngValidation = Object.fromEntries(pngNames.map((name, index) => {
    setFailureStage(pngStages[index]);
    return [name, validatePng(bytes[name], index)];
  }));
  setFailureStage('SOURCE_BINDINGS');
  const bindings = {};
  for (const name of sourceNames) {
    const content = await boundedRead(repository, join(repository, name), 2_000_000);
    const committed = execFileSync('git', ['show', `${revision}:${name}`], { cwd: repository, maxBuffer: 2_000_000 });
    assert(content.equals(committed), 'Capture sources must match reviewed committed bytes');
    bindings[name] = sha256(content);
  }
  for (const name of captureBindings) assert.equal(bindings[name], metadata.bindings[name], 'Source changed after capture');
  assert.equal(cleanup.launcher_sha256, bindings['frontend/scripts/e2e-server.mjs']);
  setFailureStage('MANIFEST_VALIDATION');
  const files = new Map([...pngNames, noteName].map(name => [name, bytes[name]]));
  files.set('index.html', Buffer.from(viewer(pngNames.map(name => bytes[name]), note), 'utf8'));
  setFailureStage('CI_IDENTITY');
  const ci = ciIdentity(process.env);
  setFailureStage('MANIFEST_VALIDATION');
  const manifest = { schema_version: 1, task: 'REL-PRODUCT-03', label,
    evidence_class: 'SYNTHETIC UI CAPTURE', live_database: 'NOT VERIFIED',
    historical_evidence: 'Separate historical manifests and classifications remain unchanged.',
    expected_repository_baseline: baseline, captured_repository_revision: revision,
    source_sha256: bindings, capture: metadata, ci, png_validation: pngValidation,
    render_input_checks: { prelaunch: admitted.sha256, execution_end: cleanup.render_inventory_sha256, packaging: admitted.sha256 },
    runner: { result: 'passed', cases: 1, retries: 0, includes_fixture_teardown: true }, cleanup,
    independent_artifact_acceptance: 'PENDING', human_rehearsal: 'NOT TESTED',
    hash_policy: 'SHA-256 over exact file bytes. Manifest excludes its own hash. No screenshot normalization.',
    artifacts: [...files].map(([name, content]) => ({ path: name, bytes: content.length, sha256: sha256(content) })) };
  publicText(json(manifest));
  assert.equal(manifest.artifacts.filter(item => item.path.endsWith('.png')).length, 4);
  assert.deepEqual(manifest.artifacts.map(item => item.path), [...pngNames, noteName, 'index.html']);
  return { files, manifest };
}
const publishValidated = async (prepare, publish) => publish(await prepare());
async function publishPackage({ files, manifest }) {
  setFailureStage('PUBLICATION');
  // No arbitrary CLI paths, overwrite, recursive copy, deletion, credential access
  // or external requests. Fresh output only, after all validation has succeeded.
  const output = inside(root, join(root, 'package'));
  await noLinks(frontend, root);
  await mkdir(output);
  for (const [name, content] of files) await writeFile(inside(output, join(output, name)), content, { flag: 'wx' });
  // Written last: partial output without this file is never an accepted package.
  await writeFile(join(output, 'manifest.json'), json(manifest), { flag: 'wx' });
  console.log('Synthetic package prepared; independent artifact review and rehearsal remain pending.');
}

async function checkRenderInventoryInMemory() {
  const publicFiles = new Map([['frontend/app/page.tsx', Buffer.from('reviewed page')],
    ['frontend/next-env.d.ts', Buffer.from('reviewed type references')]]);
  const reads = [];
  const io = {
    stat: async name => {
      assert(!excluded(name), 'Private environment input must not even be statted');
      if (name === 'frontend/app') return { isSymbolicLink: () => false, isDirectory: () => true };
      const bytes = publicFiles.get(name); if (!bytes) throw Object.assign(new Error('absent'), { code: 'ENOENT' });
      return { isSymbolicLink: () => false, isDirectory: () => false, isFile: () => true, size: bytes.length, mode: 0o100644 };
    },
    children: async () => ['.env', '.env.local', ...[...publicFiles.keys()].filter(name => name.startsWith('frontend/app/')).map(name => name.slice('frontend/app/'.length))],
    read: async name => { assert(!excluded(name), 'Private env must never be opened/hashed'); reads.push(name); return publicFiles.get(name); },
  };
  const intended = [{ path: 'frontend/app', kind: 'directory' }, ...[...publicFiles].map(([path, bytes]) =>
    ({ path, kind: 'file', bytes: bytes.length, sha256: sha256(bytes), executable: false }))];
  const clean = await scanCopiedInputs(io), admitted = admitInventory(baseline, intended, clean);
  assert.equal(admitted.source_revision, baseline); validateInventory(admitted, baseline);
  assert.throws(() => validateInventory(admitted, '0'.repeat(40)), 'Inventory must bind the intended revision');
  assert(reads.length === 2 && reads.every(name => !excluded(name)));
  publicFiles.set('frontend/app/page.tsx', Buffer.from('modified page'));
  assert.throws(() => admitInventory(baseline, intended, clean.map(entry => entry.path.endsWith('page.tsx') ? { ...entry, sha256: 'f'.repeat(64) } : entry)));
  assert.throws(() => admitInventory(baseline, intended, intended.slice(1)));
  assert.throws(() => validateInventory({ ...admitted, entries: admitted.entries.slice(1) }, baseline));
  assert.throws(() => validateInventory({ ...admitted, sha256: '0'.repeat(64) }, baseline));
  await assert.rejects(async () => admitInventory(baseline, intended, await scanCopiedInputs(io)));
  publicFiles.set('frontend/app/page.tsx', Buffer.from('reviewed page'));
  publicFiles.set('frontend/app/untracked.css', Buffer.from('unexpected style'));
  await assert.rejects(async () => admitInventory(baseline, intended, await scanCopiedInputs(io)));
  publicFiles.delete('frontend/app/untracked.css');
  publicFiles.set('frontend/next-env.d.ts', Buffer.from('protected modified references'));
  await assert.rejects(async () => admitInventory(baseline, intended, await scanCopiedInputs(io)), /frontend\/next-env\.d\.ts/);
  let published = false;
  await assert.rejects(publishValidated(() => admitInventory(baseline, intended, []), () => { published = true; }));
  assert.equal(published, false, 'Rejected inventory must never reach success-manifest publication');
  console.log('PASS: clean revision admission; modified/extra/missing/changed inputs and protected next-env rejected; private env never read; publication blocked on rejection.');
}
async function checkPngInMemory() {
  // Independently assembled standard PNGs. Probe CRC uses the bit algorithm,
  // not the native CRC used by validation; pixels are constant 17, not decoded expectations.
  const probeCrc = bytes => {
    let value = 0xffffffff;
    for (const byte of bytes) { value ^= byte; for (let bit = 0; bit < 8; bit++) value = (value >>> 1) ^ ((value & 1) ? 0xedb88320 : 0); }
    return (value ^ 0xffffffff) >>> 0;
  };
  assert.equal(probeCrc(Buffer.from('123456789')), 0xcbf43926);
  const chunk = (type, data = Buffer.alloc(0)) => {
    const result = Buffer.alloc(data.length + 12); result.writeUInt32BE(data.length); result.write(type, 4, 4, 'ascii');
    data.copy(result, 8); result.writeUInt32BE(probeCrc(result.subarray(4, -4)), result.length - 4); return result;
  };
  const header = (color = 6, height = 1000) => {
    const data = Buffer.alloc(13); data.writeUInt32BE(1440); data.writeUInt32BE(height, 4); data[8] = 8; data[9] = color; return data;
  };
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const frame = (head, chunks) => Buffer.concat([signature, chunk('IHDR', head), ...chunks, chunk('IEND')]);
  const rowsFor = channels => {
    const stride = 1440 * channels, rows = Buffer.alloc((stride + 1) * 1000);
    for (let y = 0; y < 1000; y++) {
      const start = y * (stride + 1), filter = y % 5; rows[start] = filter;
      if (filter === 0) rows.fill(17, start + 1, start + 1 + stride);
      if (filter === 1) rows.fill(17, start + 1, start + 1 + channels);
      if (filter === 3) rows.fill(9, start + 1, start + 1 + channels);
    }
    return rows;
  };
  const rgbaRows = rowsFor(4), stream = deflateSync(rgbaRows), head = header();
  const valid = frame(head, [chunk('IDAT', stream)]), before = sha256(valid);
  for (const color of [2, 6]) {
    const channels = color === 2 ? 3 : 4, compressed = deflateSync(rowsFor(channels));
    const split = Math.floor(compressed.length / 2);
    const image = frame(header(color), [chunk('sRGB', Buffer.from([0])), chunk('IDAT', compressed.subarray(0, split)), chunk('IDAT', compressed.subarray(split))]);
    assert.equal(validatePng(image, 0).decoded_pixels_sha256, sha256(Buffer.alloc(1440 * 1000 * channels, 17)));
  }
  validatePng(valid, 3); assert.equal(sha256(valid), before);
  // Known Paeth diagonal-choice case: left=10, up=30, upper-left=20 -> 20.
  const paethRows = Buffer.alloc(rgbaRows.length), stride = 1440 * 4;
  paethRows.fill(20, 1, 5); paethRows.fill(30, 5, 9);
  paethRows[stride + 1] = 4; paethRows.fill(246, stride + 2, stride + 6); paethRows.fill(20, stride + 6, stride + 10);
  const expectedPixels = Buffer.alloc(stride * 1000);
  expectedPixels.fill(20, 0, 4); expectedPixels.fill(30, 4, 8);
  expectedPixels.fill(10, stride, stride + 4); expectedPixels.fill(40, stride + 4, stride + 8);
  assert.equal(validatePng(frame(head, [chunk('IDAT', deflateSync(paethRows))]), 0).decoded_pixels_sha256, sha256(expectedPixels));
  const noData = frame(head, []); assert.equal(noData.length, 45);
  const corrupt = Buffer.from(valid); corrupt[41] ^= 1;
  const invalidFilter = Buffer.from(rgbaRows); invalidFilter[0] = 5;
  const badWidth = Buffer.from(head); badWidth.writeUInt32BE(1441);
  const badDepth = Buffer.from(head); badDepth[8] = 16;
  const interlace = Buffer.from(head); interlace[12] = 1;
  const malformedLength = Buffer.from(valid); malformedLength.writeUInt32BE(0xffffffff, 8);
  const highBitType = Buffer.from(valid); highBitType[12] |= 128;
  highBitType.writeUInt32BE(probeCrc(highBitType.subarray(12, 29)), 29);
  const negatives = [noData, corrupt, valid.subarray(0, -1), valid.subarray(0, -12), malformedLength,
    frame(head, [chunk('IHDR', head), chunk('IDAT', stream)]), frame(head, [chunk('IDAT')]),
    frame(head, [chunk('IDAT', Buffer.from('not zlib'))]), frame(head, [chunk('IDAT', stream.subarray(0, -1))]),
    frame(head, [chunk('IDAT', Buffer.concat([stream, Buffer.from([0])]))]),
    frame(head, [chunk('IDAT', Buffer.concat([stream, stream]))]),
    frame(head, [chunk('IDAT', deflateSync(invalidFilter))]),
    frame(head, [chunk('IDAT', deflateSync(rgbaRows.subarray(0, -1)))]),
    frame(head, [chunk('IDAT', deflateSync(Buffer.concat([rgbaRows, Buffer.from([0])])))]),
    frame(badWidth, [chunk('IDAT', stream)]), frame(header(6, 1001), [chunk('IDAT', stream)]),
    frame(header(0), [chunk('IDAT', stream)]), frame(badDepth, [chunk('IDAT', stream)]),
    frame(interlace, [chunk('IDAT', stream)]), frame(head, [chunk('ABCD'), chunk('IDAT', stream)]),
    frame(head, [chunk('IDAT', stream), chunk('gAMA', Buffer.from([0, 0, 0, 1])), chunk('IDAT', stream)]),
    Buffer.concat([valid, Buffer.from([0])]), frame(head, [chunk('sRGB', Buffer.from([5])), chunk('IDAT', stream)]), highBitType,
  ];
  for (const image of negatives) assert.throws(() => validatePng(image, 0));
  assert.throws(() => validatePng(frame(header(6, 30_000), [chunk('IDAT', stream)]), 3));
  let published = false;
  await assert.rejects(publishValidated(() => validatePng(noData, 0), () => { published = true; }));
  assert.equal(published, false, 'Invalid PNG must never reach success-manifest publication');
  console.log(`PASS: 4 complete RGB/RGBA PNG probes (all filters, Paeth diagonal, split IDAT, exact decoded hash, original bytes); ${negatives.length + 1} malformed/decode/resource probes rejected, including 45-byte no-IDAT; publication blocked.`);
}
async function checkFailureDiagnosticsInMemory() {
  // Execute only these serialized pure helpers in disposable Node processes.
  // Never import/invoke packaging, read evidence, or print the hostile inputs.
  const helpers = `const packagingStages=Object.freeze(${JSON.stringify(packagingStages)});
    let failureStage='UNKNOWN';${setFailureStage.toString()};${reportPackageFailure.toString()};
    const hostile=Object.defineProperties({}, {
      message:{get(){throw new Error('message must not be read')}},
      stack:{get(){throw new Error('stack must not be read')}},
      toString:{value(){throw new Error('coercion must not occur')}}});`;
  const invalid = ['UNKNOWN', 'PRIVATE-SENTINEL\nC:\\private\\fixture https://example.invalid/?token=fixture', null];
  for (const stage of [...packagingStages, ...invalid]) {
    const child = spawnSync(process.execPath, ['--input-type=module', '-e', `${helpers}
      try {setFailureStage(${JSON.stringify(stage)});throw hostile;}catch{reportPackageFailure();}`],
    { encoding: 'utf8', timeout: 5000, maxBuffer: 512, windowsHide: true });
    assert.equal(child.status, 1); assert.equal(child.stdout, '');
    const expected = packagingStages.includes(stage) ? stage : 'UNKNOWN';
    assert.equal(child.stderr, `RW-PACKAGE-FAIL stage=${expected}\n`); assert(child.stderr.length < 80);
  }
  // An untrusted object is not coerced into a category, even on an unexpected failure.
  const child = spawnSync(process.execPath, ['--input-type=module', '-e', `${helpers}
    try {setFailureStage(hostile);throw hostile;}catch{reportPackageFailure();}`],
  { encoding: 'utf8', timeout: 5000, maxBuffer: 512, windowsHide: true });
  assert.equal(child.status, 1); assert.equal(child.stdout, ''); assert.equal(child.stderr, 'RW-PACKAGE-FAIL stage=UNKNOWN\n');
  const gitError = spawnSync(process.execPath, ['--input-type=module', '-e', `${helpers}
    import {execFileSync as executeFileSync} from 'node:child_process';${execFileSync.toString()};
    process.argv[2]='--package';setFailureStage('SOURCE_BINDINGS');
    if(execFileSync(process.execPath,['-e',"process.stdout.write('CAPTURED-STDOUT')"],{}).toString()!=='CAPTURED-STDOUT')process.exit(99);
    try {execFileSync(process.execPath,['-e',"process.stderr.write('PRIVATE-STDERR-SENTINEL');process.exit(23)"],{});}
    catch {reportPackageFailure();}`], { encoding: 'utf8', timeout: 5000, maxBuffer: 512, windowsHide: true });
  assert.equal(gitError.status, 1); assert.equal(gitError.stdout, '');
  assert.equal(gitError.stderr, 'RW-PACKAGE-FAIL stage=SOURCE_BINDINGS\n');
  let published = false;
  setFailureStage('NATIVE_NOTE');
  await assert.rejects(publishValidated(() => { throw new Error('in-memory rejection'); }, () => { published = true; }));
  assert.equal(published, false); assert.equal(failureStage, 'NATIVE_NOTE');
  await assert.rejects(publishValidated(() => ({}), () => { setFailureStage('PUBLICATION'); throw new Error('in-memory publication failure'); }));
  assert.equal(failureStage, 'PUBLICATION');
  const successful = { files: new Map([['in-memory', Buffer.from('unchanged bytes')]]), manifest: { marker: 'unchanged probe' } };
  assert.equal(await publishValidated(() => successful, value => { assert.equal(value, successful); return value; }), successful);
  setFailureStage('UNKNOWN');
}
async function checkInMemory() {
  await checkFailureDiagnosticsInMemory();
  await checkRenderInventoryInMemory(); await checkPngInMemory();
  assert.throws(() => inside(root, resolve(root, '..', 'escape')));
  assert.throws(() => inside(root, root));
  assert.equal(inside(root, join(root, 'raw')), join(root, 'raw'));
  for (const text of ['C:\\Users\\private', '/home/private/data', '\\\\host\\share', 'api_key=example', '\0']) assert.throws(() => publicText(text));
  publicText('frontend/e2e/fixtures/data.ts synthetic.htm');
  assert.equal(escapeHtml('<script>&"\''), '&lt;script&gt;&amp;&quot;&#39;');
  assert.equal(decode(Buffer.from('line\r\n—\n')), 'line\r\n—\n');
  assert.throws(() => decode(Buffer.from([0xff])));
  assert.deepEqual(ciIdentity({}), { run_id: null, job: null, attempt: null });
  assert.throws(() => ciIdentity({ CI: 'true' }));
  assert.throws(() => validateMetadata({})); assert.throws(() => validateResult({ errors: ['failure'] }));
  assert.throws(() => validateNote(Buffer.from('replacement fixture')));
  assert.throws(() => validatePng(Buffer.alloc(33), 0));
  assert.equal(sha256(Buffer.from('abc')), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  // Schema probes only: these objects are never written or represented as runs.
  const instant = '2000-01-01T00:00:00.000Z';
  const probe = { schema_version: 1, label, expected_baseline: baseline, source_revision: baseline,
    test: 'portable synthetic research walkthrough', project: 'synthetic-walkthrough-chromium',
    config: 'frontend/playwright.capture.config.ts', settings,
    runtime: { node: 'v24.0.0', platform: 'linux', arch: 'x64', chromium: '1.2.3.4', playwright: '1.64.0', next: '15.5.27' },
    started_at: instant, completed_at: instant,
    captures: pngNames.map((name, index) => ({ name, captured_at: instant, full_page: index === 3 })),
    bindings: Object.fromEntries(captureBindings.map(name => [name, '0'.repeat(64)])),
    render_inventory: inventoryRecord(baseline, [{ path: 'frontend/app', kind: 'directory' }]), admission_sha256: '0'.repeat(64),
    clipboard: { mechanism: 'native Chromium navigator.clipboard.readText', encoding: 'UTF-8', sha256: '0'.repeat(64) },
    network: { requests: [{ method: 'GET', path: '/companies', pin: null, query: '' }], failures: [], violations: [] },
    execution_scope: 'synthetic frontend only; live database NOT VERIFIED' };
  validateMetadata(probe);
  for (const mutate of [value => { value.label = 'unlabelled'; }, value => { value.captures.pop(); },
    value => { value.settings.scale = 2; }, value => { value.network.violations.push('blocked destination'); },
    value => { value.network.requests[0].method = 'POST'; }, value => { value.network.requests[0].query = 'unexpected=field'; },
    value => { value.bindings[captureBindings[0]] = 'bad'; },
    value => { value.source_revision = 'unknown'; }, value => { value.completed_at = null; },
    value => { value.private_path = '/home/private/fixture'; }]) {
    const altered = structuredClone(probe); mutate(altered); assert.throws(() => validateMetadata(altered));
  }
  const report = { errors: [], stats: { expected: 1, unexpected: 0, flaky: 0, skipped: 0 },
    suites: [{ specs: [{ title: probe.test, ok: true, tests: [{ projectName: probe.project, status: 'expected',
      results: [{ status: 'passed', retry: 0, errors: [], startTime: instant, duration: 1 }] }] }] }] };
  validateResult(report, probe);
  const cleanupProbe = { source_revision: baseline, launcher_sha256: '0'.repeat(64),
    started_at: instant, completed_at: instant, exit_code: 0, signal: null,
    render_inventory_sha256: probe.render_inventory.sha256 };
  validateCleanup(cleanupProbe, probe);
  assert.throws(() => validateCleanup({ ...cleanupProbe, exit_code: 1 }, probe));
  assert.throws(() => validateCleanup({ ...cleanupProbe, signal: 'SIGKILL' }, probe));
  assert.throws(() => validateCleanup({ ...cleanupProbe, source_revision: 'unknown' }, probe));
  for (const mutate of [value => { value.errors.push('teardown failure'); }, value => { value.stats.skipped = 1; },
    value => { value.suites[0].specs[0].tests[0].results[0].retry = 1; },
    value => { value.suites[0].specs[0].tests[0].results[0].startTime = '2000-01-02T00:00:00.000Z'; }]) {
    const altered = structuredClone(report); mutate(altered); assert.throws(() => validateResult(altered, probe));
  }
  assert.equal(new Set(rawNames).size, 6); assert.equal(pngNames.length, 4);
  const html = viewer(pngNames.map(() => Buffer.from('in-memory invariant probe')), '<script>inert</script>');
  assert(!html.includes('<script>')); assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));
  assert.equal((html.match(/<img /g) ?? []).length, 4); assert(!/<a\b|https?:\/\//.test(html));
  assert(html.includes(label) && html.includes("default-src 'none'"));
  console.log('PASS: in-memory path, schema/result mutation rejection, SHA-256, UTF-8 preservation, escaping, offline viewer, completeness and default-null CI checks; no evidence generated.');
}

if (process.argv.length !== 3 || !['--check', '--admit-check', '--package', '--serve'].includes(process.argv[2])) {
  console.error('Use --check (in-memory), --admit-check (read-only); --package/--serve require separate execution authorization.');
  process.exitCode = 1;
} else {
  try {
    if (process.argv[2] === '--check') await checkInMemory();
    else if (process.argv[2] === '--admit-check') {
      const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repository, encoding: 'utf8' }).trim();
      await collectRenderInventory(revision); console.log('Render inventory matches current reviewed commit; no execution authorized.');
    }
    else if (process.argv[2] === '--serve') await serveWithReceipt();
    else await publishValidated(packageEvidence, publishPackage);
  }
  catch (error) {
    if (process.argv[2] === '--package') reportPackageFailure();
    else {
      console.error(process.argv[2] === '--admit-check' && /^Render input differs from reviewed commit: frontend\//.test(error.message)
        ? error.message.split('\n')[0] : 'Walkthrough validation failed; no publishable package is established.');
      process.exitCode = 1;
    }
  }
}
