import { readdir, readFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';

async function linuxMembers(pgid) {
  const members = [];
  for (const pid of await readdir('/proc')) {
    if (!/^\d+$/.test(pid)) continue;
    let stat;
    try { stat = await readFile(`/proc/${pid}/stat`, 'utf8'); }
    catch (error) { if (error.code === 'ENOENT' || error.code === 'ESRCH') continue; throw error; }
    // comm can contain spaces/parentheses. Fields after the last ')' start at
    // state (field 3); group/session/starttime are fields 5/6/22.
    const fields = stat.slice(stat.lastIndexOf(')') + 2).trim().split(/\s+/);
    if (Number(fields[2]) === pgid) members.push({ pid: Number(pid), session: Number(fields[3]), state: fields[0], startTime: fields[19] });
  }
  return members;
}

// Construct only for the PID returned by our detached spawn. PGID ownership is
// independent of the leader's ChildProcess.exitCode/signalCode. Linux setsid
// gives this group a session with the same ID; reused leaders are refused.
export class OwnedProcessGroup {
  constructor(pgid, { readMembers = linuxMembers, signal = (group, name) => process.kill(-group, name), sleep = delay, now = Date.now } = {}) {
    if (!Number.isSafeInteger(pgid) || pgid <= 1 || pgid === process.pid) throw new Error('Invalid owned process group');
    this.pgid = pgid;
    this.readMembers = readMembers; this.signal = signal; this.sleep = sleep; this.now = now;
    this.leaderStartTime = null;
    this.captured = false; this.terminated = false; this.stopping = null;
  }
  async members() {
    const members = await this.readMembers(this.pgid);
    if (members.some(member => member.session !== this.pgid)) throw new Error('Process group ownership changed; refusing termination');
    const leader = members.find(member => member.pid === this.pgid);
    if (leader && this.leaderStartTime !== null && leader.startTime !== this.leaderStartTime) throw new Error('Process group leader identity changed; refusing termination');
    return members;
  }
  async capture() {
    if (this.captured) return;
    const members = await this.members();
    this.leaderStartTime = members.find(member => member.pid === this.pgid)?.startTime ?? null;
    this.captured = true;
    if (!members.length) this.terminated = true;
  }
  async activeMembers() {
    // Zombies have exited, execute no code and hold no working-directory files.
    // PID 1 may delay reaping them; kill(-PGID, 0) alone cannot distinguish this.
    return (await this.members()).filter(member => !['Z', 'X', 'x'].includes(member.state));
  }
  async waitUntilTerminated(milliseconds) {
    const deadline = this.now() + milliseconds;
    do {
      if (!(await this.activeMembers()).length) return true;
      if (this.now() >= deadline) return false;
      await this.sleep(Math.min(50, Math.max(1, deadline - this.now())));
    } while (true);
  }
  async send(name) {
    // Recheck identity before each signal, including escalation after leader death.
    if (!(await this.activeMembers()).length) return;
    try { await this.signal(this.pgid, name); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
  terminate({ graceMs = 5000, forceMs = 5000 } = {}) {
    if (this.stopping) return this.stopping;
    this.stopping = (async () => {
      await this.capture();
      if (this.terminated) return;
      await this.send('SIGTERM');
      if (!await this.waitUntilTerminated(graceMs)) {
        await this.send('SIGKILL');
        if (!await this.waitUntilTerminated(forceMs)) throw new Error('Owned process group still has running descendants; temporary files retained');
      }
      this.terminated = true;
    })();
    return this.stopping;
  }
  async cleanupAfterTermination(cleanup, options) {
    await this.terminate(options);
    if ((await this.activeMembers()).length) throw new Error('Owned process group termination no longer verified; temporary files retained');
    await cleanup();
  }
}
