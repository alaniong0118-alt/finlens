import { spawn } from 'node:child_process';
import { createServer as httpServer } from 'node:http';
import { createServer as netServer } from 'node:net';
import { cp, lstat, mkdtemp, readFile, rm, symlink, unlink } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { OwnedProcessGroup } from './e2e-process-group.mjs';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const envPath = join(frontend, 'next-env.d.ts');
const hash = async () => createHash('sha256').update(await readFile(envPath)).digest('hex');
const before = await hash();
let ownedRoot, child, ownedGroup, upstream, stopping;
let failed = false;
let finishSetup;
const setupFinished = new Promise(done => { finishSetup = done; });
const prefix = 'finlens-qa01-';
const checkPort = port => new Promise((done, reject) => {
  const server = netServer();
  server.once('error', reject);
  server.listen(port, '127.0.0.1', () => server.close(error => error ? reject(error) : done()));
});
async function stop(code = 0) {
  failed ||= code !== 0;
  if (stopping) return stopping;
  stopping = (async () => {
    // A signal during asynchronous copying must not remove a half-built tree
    // while setup continues writing into it. Finish setup, then clean once.
    await setupFinished;
    // Close the deny-all listener even if process-group verification fails.
    try { if (ownedGroup) await ownedGroup.terminate(); }
    finally { if (upstream) { upstream.closeAllConnections(); await new Promise(done => upstream.close(done)); } }
    const cleanupDirectory = async () => { if (ownedRoot) {
      const rel = relative(resolve(tmpdir()), ownedRoot);
      if (isAbsolute(rel) || rel.startsWith('..') || rel.includes('/') || rel.includes('\\') || !rel.startsWith(prefix)) throw new Error('Unsafe temporary cleanup target');
      const link = join(ownedRoot, 'frontend', 'node_modules');
      // Unlink the dependency junction before recursive removal. Never recurse
      // through shared node_modules, and never delete arbitrary computed paths.
      const stat = await lstat(link).catch(error => { if (error.code !== 'ENOENT') throw error; });
      if (stat) { if (!stat.isSymbolicLink()) throw new Error('Dependency link replaced; refusing cleanup'); await unlink(link); }
      await rm(ownedRoot, { recursive: true, force: true });
    } };
    // Verification is mandatory before any owned working-directory deletion,
    // even when the leader exited earlier. Failure retains the directory.
    if (ownedGroup) await ownedGroup.cleanupAfterTermination(cleanupDirectory);
    else await cleanupDirectory();
    if (await hash() !== before) throw new Error('Protected next-env.d.ts changed during E2E');
  })().catch(error => { failed = true; console.error(error.message); }).finally(() => { process.exitCode = failed ? 1 : 0; });
  return stopping;
}
process.on('SIGINT', () => { void stop(); });
process.on('SIGTERM', () => { void stop(); });
try {
  await checkPort(3107); await checkPort(3108);
  if (stopping) throw new Error('Launcher interrupted during setup');
  if (process.platform !== 'linux' && !process.argv.includes('--check-isolation')) throw new Error('Browser execution requires supported Linux/WSL process-group verification. Native Playwright webServer shutdown on Windows cannot run this launcher\'s graceful cleanup. Static isolation checks remain available.');
  ownedRoot = await mkdtemp(join(tmpdir(), prefix));
  const copy = join(ownedRoot, 'frontend');
  // Explicit source inventory excludes .env, generated output, backend and data.
  for (const name of ['app', 'components', 'lib', 'public', 'next.config.ts', 'next-env.d.ts', 'package.json', 'tsconfig.json', 'postcss.config.js', 'postcss.config.mjs', 'tailwind.config.ts', 'tailwind.config.js']) {
    const source = join(frontend, name);
    const stat = await lstat(source).catch(error => { if (error.code !== 'ENOENT') throw error; });
    if (!stat) continue;
    if (stat.isSymbolicLink()) throw new Error(`Refusing source symlink ${name}`);
    await cp(source, join(copy, name), { recursive: true, filter: async path => {
      const info = await lstat(path);
      if (info.isSymbolicLink()) throw new Error('Source tree symlinks are outside the isolation boundary');
      return !/^\.env(?:\.|$)/.test(path.split(/[\\/]/).at(-1));
    } });
  }
  await symlink(join(frontend, 'node_modules'), join(copy, 'node_modules'), process.platform === 'win32' ? 'junction' : 'dir');
  if (process.argv.includes('--check-isolation')) {
    finishSetup();
    await stop();
    if (!failed) console.log('QA-01 isolated source copy, dependency unlink, cleanup and next-env preservation passed; no services started.');
  } else {
    upstream = httpServer((request, response) => {
      if (request.method === 'GET' && request.url === '/__qa_status') {
        response.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ healthy: !failed }));
        return;
      }
      console.error(`QA-01 isolation breach: upstream ${request.method} ${new URL(request.url, 'http://127.0.0.1').pathname}`);
      response.writeHead(503).end('QA-01 deny-all upstream');
      void stop(1);
    });
    await new Promise((done, reject) => { upstream.once('error', reject); upstream.listen(3108, '127.0.0.1', done); });
    const env = Object.fromEntries(['PATH', 'Path', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'COMSPEC', 'PATHEXT'].filter(key => process.env[key] !== undefined).map(key => [key, process.env[key]]));
    Object.assign(env, { NODE_ENV: 'development', NEXT_TELEMETRY_DISABLED: '1', FINLENS_API_BASE_URL: 'http://127.0.0.1:3108' });
    child = spawn(process.execPath, [join(frontend, 'node_modules', 'next', 'dist', 'bin', 'next'), 'dev', '--hostname', '127.0.0.1', '--port', '3107'], { cwd: copy, env, stdio: 'inherit', windowsHide: true, detached: true });
    child.on('error', error => { console.error(error.message); void stop(1); });
    child.on('exit', code => { if (!stopping) void stop(code || 1); });
    if (Number.isInteger(child.pid)) { ownedGroup = new OwnedProcessGroup(child.pid); await ownedGroup.capture(); }
  }
  finishSetup();
} catch (error) { finishSetup(); console.error(`QA-01 launcher: ${error.message}`); await stop(1); }
