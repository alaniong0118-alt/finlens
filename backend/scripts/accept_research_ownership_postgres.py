"""Opt-in, run-owned PostgreSQL acceptance launcher. Import/default/help are inert.

Authoring this code does not authorize execution. Only --execute plus the reviewed
HEAD, candidate digest, local Docker endpoint and immutable image enables effects.
No caller DSN, existing container, volume, environment-file or cleanup target input.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from uuid import uuid4

BACKEND_BASELINE = "c83449d4e87512c173680369916121a58227ac4d"
BACKEND_INPUTS = ("backend/app", "backend/migrations", "backend/requirements.txt")
FILES = (
    "backend/scripts/accept_research_ownership_postgres.py",
    "backend/tests/acceptance_research_ownership_postgres.py",
    "docs/exec-plans/active/2026-10-30-ucr-ownership-postgres-acceptance.md",
)
PROTECTED = {
    "frontend/next-env.d.ts": "f4e8976c19fc926644d72610bf1058bd6bf52add97e46a02bc0b912a751625c0",
    "backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json": "a783517d2875e39df4c831c410265d0126fbf6a9d3ddba1103f7bd61b057844c",
    "backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json": "f8df96c8890c0ece1e1701b25bc5c43b879c359eceb96acb451a2a0daa58bf7c",
}
MIB = 1024 * 1024
CLI_CAP, CHILD_CAP, EVIDENCE_CAP = 128 * 1024, 512 * 1024, 2 * MIB
LEGACY = ("companies", "financial_facts", "filing_chunks", "company_refresh_state",
          "filing_publications", "refresh_attempts", "alembic_version")
OWNED = ("research_accounts", "research_sessions", "research_artifacts")
UPDATES = {"research_accounts": ("token_cutoff", "revision"),
           "research_sessions": ("state", "revision"), "research_artifacts": ("revision",)}
MOUNTS = {"/var/lib/postgresql/data": 256 * MIB, "/tmp": 16 * MIB,
          "/var/run/postgresql": 16 * MIB, "/dev/shm": 64 * MIB, "/dev": 64 * MIB}
CASE_NAMES = ("migration_and_provisioning", "privileges", "authentication_boundary", "first_distinct", "first_replay",
              "session_last_slot", "artifact_last_slot", "artifact_replay_conflict", "foreign_constraints", "exact_identity",
              "revisions", "reservation_before_revocation", "revocation_before_reservation", "read_before_revocation",
              "revocation_before_read", "reservation_before_invalidation", "invalidation_before_reservation", "token_cutoff",
              "precommit_rollback", "confirmed_cancellation", "confirmed_rotation", "injected_before_commit",
              "injected_after_commit", "denied_reconciliation", "backend_before_commit", "backend_at_dispatch",
              "rollback_failure", "close_failure")
MIGRATION_ENV = '''from alembic import context
connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
with context.begin_transaction():
    context.run_migrations()
'''


class Refusal(ValueError):
    pass


class CommandFailure(RuntimeError):
    def __init__(self, code, *, uncertain=False):
        self.code, self.uncertain = code, uncertain
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise Refusal(code)


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value), "invalid_identifier")
    return '"' + value + '"'


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--docker-context")
    parser.add_argument("--expected-context-endpoint")
    parser.add_argument("--image")
    parser.add_argument("--expected-head")
    parser.add_argument("--candidate-sha256")
    parser.add_argument("--allow-pull", action="store_true")
    args = parser.parse_args(argv)
    require(args.execute, "execution_opt_in_required")
    require(type(args.expected_head) is str and re.fullmatch(r"[0-9a-f]{40}", args.expected_head),
            "execution_commit_required")
    require(type(args.candidate_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", args.candidate_sha256),
            "reviewed_candidate_digest_required")
    require(type(args.docker_context) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", args.docker_context),
            "explicit_context_required")
    endpoint = args.expected_context_endpoint or ""
    require(bool(re.fullmatch(r"npipe:////\./pipe/[A-Za-z0-9_.-]+|unix:///[A-Za-z0-9_./-]+", endpoint))
            and ".." not in endpoint, "approved_local_endpoint_required")
    require(type(args.image) is str and re.fullmatch(r"pgvector/pgvector@sha256:[0-9a-f]{64}", args.image),
            "immutable_image_required")
    return args


def harness_digest(read_bytes):
    """Identical framing for working bytes and committed blobs; no normalization."""
    digest = hashlib.sha256()
    for relative in FILES:
        data = read_bytes(relative)
        require(len(data) <= MIB, "candidate_file_too_large")
        for part in (relative.encode(), data):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()


def candidate_digest(root):
    """Length-framed ordered path/content digest; never scans environment files."""
    return harness_digest(lambda relative: (root / relative).read_bytes())


def admit_repository(args, root, process):
    """Identity consistency only; coordinator review and operator approval are external."""
    def git(arguments):
        result = process.run(["git", *arguments], seconds=5, cwd=str(root), env=clean_environment())
        require(isinstance(result, Output) and type(result.returncode) is int
                and type(result.stdout) is bytes and type(result.stderr) is bytes, "git_result_invalid")
        require(len(result.stdout) + len(result.stderr) <= CLI_CAP, "git_output_limit")
        require(result.returncode == 0 and not result.stderr, "git_admission_failed")
        return result.stdout

    for revision in (BACKEND_BASELINE, args.expected_head):
        require(git(["rev-parse", "--verify", revision + "^{commit}"]) == revision.encode() + b"\n",
                "commit_identity_unverified")
    require(git(["rev-parse", "HEAD"]) == args.expected_head.encode() + b"\n", "execution_head_changed")
    require(git(["branch", "--show-current"]) == b"main\n", "repository_branch_changed")
    diff = ["diff", "--no-ext-diff", "--no-textconv", "--quiet"]
    require(git([*diff, "--cached"]) == b"", "repository_index_changed")
    status = git(["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    allowed = {(b" M " if relative == "frontend/next-env.d.ts" else b"?? ") + relative.encode()
               for relative in PROTECTED}
    entries = status[:-1].split(b"\0") if status.endswith(b"\0") else []
    require((not status or status.endswith(b"\0")) and len(entries) == len(set(entries))
            and all(entry in allowed for entry in entries), "unrelated_worktree_change")
    for relative, expected in PROTECTED.items():
        require(hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, "protected_file_changed")
    require(git([*diff, BACKEND_BASELINE, args.expected_head, "--", *BACKEND_INPUTS]) == b"",
            "reviewed_backend_changed")
    require(git([*diff, "HEAD", "--", *BACKEND_INPUTS]) == b"", "committed_service_inputs_changed")

    def committed_bytes(relative):
        entry = git(["ls-tree", "-z", args.expected_head, "--", relative])
        match = re.fullmatch(rb"100(?:644|755) blob ([0-9a-f]{40})\t" + re.escape(relative.encode()) + b"\0", entry)
        require(match is not None, "committed_harness_entry_invalid")
        return git(["cat-file", "blob", match[1].decode("ascii")])

    require(harness_digest(committed_bytes) == args.candidate_sha256, "committed_candidate_digest_mismatch")


def clean_environment():
    # Do not inherit DATABASE_URL, PG*, Docker selectors, Python hooks or providers.
    return {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP",
                                           "LOCALAPPDATA", "USERPROFILE") if key in os.environ}


@dataclass(frozen=True)
class Output:
    stdout: bytes
    stderr: bytes
    returncode: int


class BoundedProcess:
    """Fixed-size streaming capture; never communicate()/unbounded readline().

    A fake Popen/clock may exercise this adapter offline. Production never accepts
    those adapters through the CLI. Python workers launch no descendant processes.
    Killing the CLI cannot cancel an already submitted Docker daemon operation.
    """
    def __init__(self, popen=subprocess.Popen, clock=time.monotonic):
        self.popen, self.clock = popen, clock

    def run(self, argv, *, seconds, cap=CLI_CAP, data=b"", env=None, cwd=None, progress=None):
        require(0 < seconds <= 900 and 0 < cap <= CHILD_CAP and len(data) <= 65536, "invalid_process_bounds")
        process = self.popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env, cwd=cwd, shell=False)
        deadline = self.clock() + seconds
        case_deadline = [deadline]
        buffers, count, lock = [bytearray(), bytearray()], [0], threading.Lock()
        overflow, input_failed, reader_failed = threading.Event(), threading.Event(), threading.Event()
        reader_eof = [threading.Event(), threading.Event()]
        line = bytearray()

        def read(index, pipe):
            try:
                while True:
                    # BufferedReader.read(n) can wait for n bytes and hide progress.
                    block = pipe.read1(4096)
                    if block == b"":
                        reader_eof[index].set()
                        return
                    require(type(block) is bytes, "capture_protocol_invalid")
                    with lock:
                        count[0] += len(block)
                        if count[0] > cap:
                            overflow.set()
                            return
                        buffers[index].extend(block)
                        if index == 0 and progress is not None:
                            line.extend(block)
                            if len(line) > 8192:
                                overflow.set()
                                return
                            while b"\n" in line:
                                record, _, tail = line.partition(b"\n")
                                line[:] = tail
                                try:
                                    interval = progress(json.loads(record))
                                    if interval:
                                        bound = interval if type(interval) is int else 90
                                        require(0 < bound <= 90, "invalid_case_deadline")
                                        case_deadline[0] = min(deadline, self.clock() + bound)
                                except (ValueError, TypeError, KeyError):
                                    overflow.set()
                                    return
            except BaseException:
                # Fixed-size cross-thread signal only; never retain raw diagnostics.
                reader_failed.set()

        def write():
            try:
                process.stdin.write(data)
                process.stdin.close()
            except (OSError, ValueError):
                input_failed.set()

        threads = [threading.Thread(target=read, args=(i, pipe), daemon=True)
                   for i, pipe in enumerate((process.stdout, process.stderr))]
        threads.append(threading.Thread(target=write, daemon=True))
        for thread in threads:
            thread.start()
        error = None
        while process.poll() is None:
            if reader_failed.is_set() or overflow.is_set() or input_failed.is_set() or self.clock() >= case_deadline[0]:
                error = ("capture_read_failure" if reader_failed.is_set() else "output_limit" if overflow.is_set()
                         else "input_failure" if input_failed.is_set() else "command_timeout")
                process.kill()
                break
            time.sleep(0.005)
        try:
            process.wait(timeout=min(2, max(0.01, deadline - self.clock())))
        except subprocess.TimeoutExpired:
            error = "process_termination_unverified"
        for thread in threads:
            thread.join(timeout=min(0.1, max(0, deadline - self.clock())))
        if any(thread.is_alive() for thread in threads):
            error = error or "capture_termination_unverified"
        for pipe in (process.stdin, process.stdout, process.stderr):
            # Do not block closing a buffered pipe held by a still-live reader.
            if not any(thread.is_alive() for thread in threads):
                pipe.close()
        if overflow.is_set():
            error = error or "output_limit"
        if input_failed.is_set():
            error = error or "input_failure"
        if reader_failed.is_set():
            error = error or "capture_read_failure"
        if not all(event.is_set() for event in reader_eof):
            error = error or "capture_incomplete"
        if error:
            raise CommandFailure(error, uncertain=True)
        return Output(bytes(buffers[0]), bytes(buffers[1]), process.returncode)


def container_command(run, image, network):
    return ["container", "create", "--name", run.container_name, "--label", run.label,
            "--network", network, "--pull=never", "--read-only", "--log-driver=none",
            "--memory=768m", "--memory-swap=768m", "--cpus=2", "--pids-limit=128",
            "--shm-size=64m", "--cgroupns=private", "--ipc=private", "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,size=268435456",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=16777216",
            "--tmpfs", "/var/run/postgresql:rw,nosuid,nodev,size=16777216",
            "--publish", "127.0.0.1::5432", "--env", "POSTGRES_PASSWORD",
            "--env", "POSTGRES_USER=" + run.admin, "--env", "POSTGRES_DB=" + run.database,
            "--env", "PGDATA=/var/lib/postgresql/data", image, "postgres",
            "-c", "max_connections=12", "-c", "shared_buffers=32MB", "-c", "logging_collector=off"]


def grants(database, service):
    db, role = identifier(database), identifier(service)
    statements = [f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT CONNECTION LIMIT 2",
                  f"REVOKE ALL ON DATABASE {db} FROM PUBLIC, {role}", f"GRANT CONNECT ON DATABASE {db} TO {role}",
                  f"REVOKE ALL ON SCHEMA public FROM PUBLIC, {role}", f"GRANT USAGE ON SCHEMA public TO {role}"]
    for table in OWNED + LEGACY:
        statements.append(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {role}")
    # New target: assert no column ACLs before granting; no historical ACL assumptions.
    statements.append(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, {role}")
    for table in OWNED:
        statements.extend((f"GRANT SELECT, INSERT ON TABLE public.{table} TO {role}",
                           f"GRANT UPDATE ({', '.join(UPDATES[table])}) ON TABLE public.{table} TO {role}"))
    return tuple(statements)


def privilege_probes(service, admin, nonce):
    """All SQL is future-only; valid writable transactions, always rolled back."""
    role, bootstrap = identifier(service), identifier(admin)
    name = identifier("probe_" + nonce)
    probes = [("temp", f"CREATE TEMP TABLE {name} (n integer)"),
              ("schema", f"CREATE SCHEMA {name}"),
              ("table", f"CREATE TABLE public.{name} (n integer)"),
              ("role", f"CREATE ROLE {name}"), ("set_role", f"SET ROLE {bootstrap}"),
              ("truncate", "TRUNCATE public.research_artifacts")]
    for table in OWNED + LEGACY:
        probes.append(("delete_" + table, f"DELETE FROM public.{table} WHERE false"))
    columns = {"companies": ("name", "text"), "financial_facts": ("metric", "text"),
               "filing_chunks": ("text", "text"), "company_refresh_state": ("data_version", "bigint"),
               "filing_publications": ("chunk_count", "integer"), "refresh_attempts": ("status", "text"),
               "alembic_version": ("version_num", "text")}
    for table, (column, kind) in columns.items():
        probes.extend((("insert_" + table, f"INSERT INTO public.{table} ({column}) SELECT NULL::{kind} WHERE false"),
                       ("update_" + table, f"UPDATE public.{table} SET {column}=NULL::{kind} WHERE false")))
    probes.extend((("account_column", "UPDATE public.research_accounts SET enabled=false WHERE false"),
                   ("session_column", "UPDATE public.research_sessions SET request_key='denied' WHERE false"),
                   ("artifact_column", "UPDATE public.research_artifacts SET state='revoked' WHERE false")))
    return tuple(probes)


def hba(database, admin, service):
    for value in (database, admin, service):
        identifier(value)
    return (f"local {database} {admin} trust\nhost {database} {admin} all scram-sha-256\n"
            f"local {database} {service} scram-sha-256\nhost {database} {service} all scram-sha-256\n"
            "local all all reject\nhost all all all reject\n").encode()


def validate_mountinfo(raw):
    """Kernel interfaces are not disk stores; every writable storage mount bounded."""
    seen = set()
    for line in raw.decode("ascii").splitlines():
        fields = line.split()
        split = fields.index("-")
        path, flags, kind, superflags = fields[4], fields[5].split(","), fields[split + 1], fields[split + 3]
        if path in ("/", "/etc/hosts", "/etc/hostname", "/etc/resolv.conf"):
            require("ro" in flags, "writable_root_or_runtime_file")
            seen.add(path)
        if "rw" not in flags:
            continue
        if kind in {"proc", "devpts", "mqueue"}:
            continue
        require(kind == "tmpfs", "unexpected_writable_storage")
        options = dict(item.split("=", 1) for item in superflags.split(",") if "=" in item)
        size = options.get("size", "")
        match = re.fullmatch(r"([0-9]+)([kmg]?)", size)
        require(match is not None, "unbounded_tmpfs")
        amount = int(match[1]) * {"": 1, "k": 1024, "m": MIB, "g": 1024 * MIB}[match[2]]
        # Masked /proc character-device mounts share bounded /dev, never disk.
        bound = MOUNTS.get(path, 64 * MIB if path.startswith("/proc/") else 0)
        require(0 < amount <= bound, "tmpfs_bound_mismatch")
        seen.add(path)
    require(set(MOUNTS) | {"/", "/etc/hosts", "/etc/hostname", "/etc/resolv.conf"} <= seen,
            "required_mount_missing")


def validate_cgroup(raw):
    values = raw.decode("ascii").splitlines()
    require(len(values) == 4 and values[0] == str(768 * MIB) and values[1] == "0" and values[3] == "128",
            "kernel_memory_swap_or_pid_bounds_unverified")
    cpu = values[2].split()
    require(len(cpu) == 2 and all(x.isdecimal() for x in cpu) and int(cpu[1]) > 0
            and int(cpu[0]) == 2 * int(cpu[1]), "kernel_cpu_bound_unverified")


CONTAINER_FORMAT = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},'
                    '"labels":{{json .Config.Labels}},"host":{{json .HostConfig}},'
                    '"mounts":{{json .Mounts}},"networks":{{json .NetworkSettings.Networks}},'
                    '"ports":{{json .NetworkSettings.Ports}},"running":{{json .State.Running}}}')
NETWORK_FORMAT = ('{"id":{{json .Id}},"name":{{json .Name}},"labels":{{json .Labels}},'
                  '"containers":{{json .Containers}},"driver":{{json .Driver}}}')


class Run:
    def __init__(self, args, root, process, *, nonce=None, clock=time.monotonic):
        self.args, self.root, self.process, self.clock = args, root, process, clock
        self.nonce = nonce or uuid4().hex
        require(re.fullmatch(r"[0-9a-f]{32}", self.nonce), "invalid_run_nonce")
        self.container_name, self.network_name = "ucr_pg_" + self.nonce, "ucr_net_" + self.nonce
        self.admin, self.service, self.database = (prefix + self.nonce for prefix in ("ucr_admin_", "ucr_svc_", "ucr_db_"))
        self.label = "finlens.ucr.run=" + self.nonce
        self.ids, self.intents, self.pending = {}, {}, set()
        self.image_id, self.receipts = None, []
        self.started, self.deadline = clock(), clock() + 900
        self.cleanup_deadline = None
        self.directory = None
        self.migration_owned = False
        self.report_durable, self.evidence_overflow = True, False

    def receipt(self, **values):
        record = dict(values)
        encoded = json.dumps(self.receipts + [record], separators=(",", ":")).encode()
        if len(encoded) >= EVIDENCE_CAP - (4096 if self.cleanup_deadline is not None else 65536):
            self.evidence_overflow = True
            if self.cleanup_deadline is None:
                raise Refusal("evidence_limit")
            return  # Keep cleanup independent of an exhausted evidence sink.
        self.receipts.append(record)
        if self.directory is not None:
            # Fixed own file, no caller path; replace bounded sanitized receipt.
            try:
                (self.directory / "receipt.json").write_bytes(encoded)
            except OSError:
                self.report_durable = False

    def command(self, args, *, seconds=5, data=b"", extra_env=None, allow_failure=False):
        end = self.cleanup_deadline or self.deadline - 30
        remaining = end - self.clock()
        if remaining <= 0:
            raise CommandFailure("run_or_cleanup_deadline", uncertain=True)
        require(self.cleanup_deadline is not None or self.report_durable, "evidence_sink_unavailable")
        env = clean_environment()
        env.update(extra_env or {})
        result = self.process.run(["docker", "--context", self.args.docker_context, *args],
                                  seconds=min(seconds, remaining), data=data, env=env)
        self.receipt(command=args[0:2], returncode=result.returncode,
                     stdout_bytes=len(result.stdout), stderr_bytes=len(result.stderr))
        require(self.cleanup_deadline is not None or self.report_durable, "evidence_sink_unavailable")
        if result.returncode and not allow_failure:
            raise CommandFailure("docker_command_failed", uncertain=True)
        return result

    def inspect(self, kind, target):
        fmt = CONTAINER_FORMAT if kind == "container" else NETWORK_FORMAT
        return json.loads(self.command([kind, "inspect", "--format", fmt, target]).stdout)

    def owned(self, kind, record, *, bounds=True):
        require(record.get("name", "").lstrip("/") == getattr(self, kind + "_name")
                and record.get("labels", {}).get("finlens.ucr.run") == self.nonce
                and re.fullmatch(r"[0-9a-f]{64}", record.get("id", "")), "resource_ownership_unverified")
        require(kind in self.intents, "creation_intent_missing")
        if kind == "container":
            require(record.get("image") == self.image_id, "container_image_mismatch")
            nets = record.get("networks", {})
            require(set(nets) == {self.network_name} and nets[self.network_name]["NetworkID"] == self.ids.get("network"),
                    "unexpected_container_network")
            if not bounds:
                if kind in self.ids:
                    require(record["id"] == self.ids[kind], "resource_id_changed")
                return record["id"]
            host = record["host"]
            require(host.get("ReadonlyRootfs") is True and host.get("LogConfig", {}).get("Type") == "none"
                    and host.get("Memory") == 768 * MIB and host.get("MemorySwap") == 768 * MIB
                    and host.get("NanoCpus") == 2_000_000_000 and host.get("PidsLimit") == 128
                    and host.get("ShmSize") == 64 * MIB and not host.get("Privileged")
                    and host.get("IpcMode") == "private" and host.get("CgroupnsMode") == "private"
                    and not host.get("Binds"), "container_bounds_mismatch")
            require(set(host.get("Tmpfs", {})) == set(MOUNTS) - {"/dev", "/dev/shm"}, "unexpected_tmpfs")
            for path in set(MOUNTS) - {"/dev", "/dev/shm"}:
                require("size=" + str(MOUNTS[path]) in host["Tmpfs"][path].split(","), "tmpfs_config_mismatch")
            require(all(m.get("Type") == "tmpfs" and m.get("Destination") in MOUNTS
                        for m in record.get("mounts", [])), "unexpected_container_mount")
            bindings = host.get("PortBindings", {})
            require(set(bindings) == {"5432/tcp"} and len(bindings["5432/tcp"]) == 1
                    and bindings["5432/tcp"][0]["HostIp"] == "127.0.0.1", "unsafe_port_binding")
        else:
            require(record.get("driver") == "bridge" and set(record.get("containers") or {}) <= {self.ids.get("container")},
                    "network_has_unowned_members")
        if kind in self.ids:
            require(record["id"] == self.ids[kind], "resource_id_changed")
        return record["id"]

    def lookup(self, kind):
        name = getattr(self, kind + "_name")
        pattern = "^/" + name + "$" if kind == "container" else "^" + name + "$"
        raw = self.command([kind, "ls", *( ["--all"] if kind == "container" else []), "--no-trunc",
                            "--filter", "name=" + pattern, "--format", "{{.ID}}"])
        found = raw.stdout.decode("ascii").splitlines()
        require(len(found) <= 1, "ambiguous_resource_lookup")
        return found[0] if found else None

    def create(self, kind, command, *, extra_env=None):
        require(self.lookup(kind) is None and kind not in self.intents, "resource_name_already_exists")
        self.intents[kind] = getattr(self, kind + "_name")
        self.pending.add(kind)
        self.receipt(event="creation_intent", kind=kind, name=self.intents[kind], nonce=self.nonce)
        try:
            output = self.command(command, seconds=10, extra_env=extra_env)
            value = output.stdout.decode("ascii").strip()
            require(re.fullmatch(r"[0-9a-f]{64}", value), "creation_id_unverified")
            self.ids[kind] = value
            self.owned(kind, self.inspect(kind, value))
            self.pending.remove(kind)
            self.receipt(event="created", kind=kind, id=value)
        except BaseException:
            self.receipt(event="creation_indeterminate", kind=kind)
            raise

    def cleanup(self):
        self.cleanup_deadline = min(self.deadline, self.clock() + 30)
        complete = True
        container_removed = "container" not in self.intents
        for kind in ("container", "network"):
            if kind not in self.intents:
                continue
            try:
                require(kind != "network" or container_removed, "network_cleanup_blocked_by_container")
                if kind in self.pending:
                    recovered = self.lookup(kind)
                    if recovered is None:
                        raise Refusal("creation_still_unresolved")
                    record = self.inspect(kind, recovered)
                    self.ids[kind] = self.owned(kind, record, bounds=False)
                    # Positive inspect after create proves a concrete resource, not absence.
                    self.pending.remove(kind)
                    self.receipt(event="creation_reconciled", kind=kind, id=self.ids[kind])
                value = self.ids[kind]
                record = self.inspect(kind, value)
                self.owned(kind, record, bounds=False)
                if kind == "container" and record["running"]:
                    self.command([kind, "stop", "--time", "5", value], seconds=10)
                self.command([kind, "rm", value], seconds=5)
                require(self.lookup(kind) is None, "resource_removal_unverified")
                if kind == "container":
                    container_removed = True
                self.receipt(event="removed", kind=kind, id=value)
            except (Refusal, CommandFailure, KeyError, ValueError, OSError):
                complete = False
                self.receipt(event="cleanup_unverified", kind=kind, id=self.ids.get(kind),
                             name=self.intents[kind], creation_indeterminate=kind in self.pending)
        if self.migration_owned:
            try:
                folder = self.directory / "migration"
                source = folder / "env.py"
                require(not folder.is_symlink() and not source.is_symlink()
                        and source.read_bytes() == MIGRATION_ENV.encode(), "temporary_file_ownership_unverified")
                source.unlink()
                folder.rmdir()
                self.receipt(event="temporary_migration_removed")
            except (Refusal, OSError):
                complete = False
                self.receipt(event="temporary_migration_cleanup_unverified")
        return complete and not self.pending

    def execute(self):
        password = secrets.token_urlsafe(32)
        service_password = secrets.token_urlsafe(32)
        status, worker_result = "failed", None
        try:
            context = self.command(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}", self.args.docker_context])
            require(context.stdout.decode().strip() == self.args.expected_context_endpoint, "context_endpoint_changed")
            if self.args.allow_pull:
                self.command(["image", "pull", "--quiet", self.args.image], seconds=60)
            self.image_id = self.command(["image", "inspect", "--format", "{{.Id}}", self.args.image]).stdout.decode().strip()
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_id), "image_identity_unverified")
            self.create("network", ["network", "create", "--driver", "bridge", "--label", self.label, self.network_name])
            self.create("container", container_command(self, self.args.image, self.ids["network"]),
                        extra_env={"POSTGRES_PASSWORD": password})
            startup_end = min(self.deadline - 30, self.clock() + 60)
            self.command(["container", "start", self.ids["container"]], seconds=10)
            while True:
                require(self.clock() < startup_end, "postgres_startup_deadline")
                ready = self.command(["container", "exec", self.ids["container"], "pg_isready", "-U", self.admin,
                                      "-d", self.database], seconds=min(5, startup_end - self.clock()), allow_failure=True)
                if ready.returncode == 0:
                    break
                time.sleep(0.1)
            record = self.inspect("container", self.ids["container"])
            self.owned("container", record)
            ports = record["ports"]["5432/tcp"]
            require(len(ports) == 1 and ports[0]["HostIp"] == "127.0.0.1", "published_endpoint_unverified")
            port = int(ports[0]["HostPort"])
            require(1024 <= port <= 65535 and port != 5432, "unsafe_assigned_port")
            mountinfo = self.command(["container", "exec", self.ids["container"], "cat", "/proc/self/mountinfo"])
            validate_mountinfo(mountinfo.stdout)
            cgroup = self.command(["container", "exec", self.ids["container"], "cat", "/sys/fs/cgroup/memory.max",
                                   "/sys/fs/cgroup/memory.swap.max", "/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/pids.max"])
            validate_cgroup(cgroup.stdout)
            self.receipt(event="mount_and_kernel_bounds_verified", memory=768 * MIB, memory_swap=0, cpus=2, pids=128)
            write_probe = self.command(["container", "exec", self.ids["container"], "sh", "-c",
                                        "touch /ucr_readonly_probe"], allow_failure=True)
            require(write_probe.returncode != 0 and b"Read-only file system" in write_probe.stderr,
                    "root_readonly_probe_unverified")
            psql = ["container", "exec", "--interactive", self.ids["container"], "psql", "-X", "-qAt",
                    "-v", "ON_ERROR_STOP=1", "-U", self.admin, "-d", self.database]
            internal_id = self.command(psql, data=b"SELECT system_identifier FROM pg_control_system();\n").stdout.decode().strip()
            require(re.fullmatch(r"[0-9]+", internal_id), "internal_cluster_identity_unverified")
            self.command(["container", "exec", "--interactive", self.ids["container"], "sh", "-c",
                          'cat > "$PGDATA/pg_hba.conf"'], data=hba(self.database, self.admin, self.service))
            self.command(psql, data=b"SELECT pg_reload_conf();\n")
            folder = self.directory / "migration"
            folder.mkdir(exist_ok=False)
            self.migration_owned = True
            (folder / "env.py").write_bytes(MIGRATION_ENV.encode())
            payload = {"nonce": self.nonce, "port": port, "database": self.database, "admin": self.admin,
                       "service": self.service, "admin_password": password, "service_password": service_password,
                       "system_identifier": internal_id, "container_id": self.ids["container"],
                       "migration_directory": str(folder)}
            events, seen, passed_cases = [], set(), set()

            def progress(event):
                require(type(event) is dict and set(event) <= {"event", "case", "code", "passed", "transport_lost_ack", "detail"}
                        and len(events) < 256,
                        "invalid_worker_event")
                if event.get("event") == "case_start":
                    require(event.get("case") in CASE_NAMES and event["case"] not in seen
                            and event["case"] == CASE_NAMES[len(seen)],
                            "invalid_worker_schedule")
                    seen.add(event["case"])
                    events.append(event)
                    return 60 if event["case"] == "migration_and_provisioning" else 90
                if event.get("event") == "case_pass":
                    require(event.get("case") in seen and event["case"] not in passed_cases, "invalid_worker_case_pass")
                    passed_cases.add(event["case"])
                events.append(event)
                return False

            worker_code = ("import runpy,sys; m=runpy.run_path(sys.argv[1]); "
                           "raise SystemExit(m['worker_entry']())")
            try:
                result = self.process.run([sys.executable, "-I", "-S", "-B", "-c", worker_code,
                                           str(self.root / FILES[1])], seconds=min(660, self.deadline - 30 - self.clock()),
                                          cap=CHILD_CAP, data=json.dumps(payload).encode(), env=clean_environment(),
                                          cwd=str(self.root), progress=progress)
            finally:
                self.receipt(event="postgres_observations", outcomes=events)
            require(result.returncode == 0 and len(events) > 0 and events[-1].get("event") == "complete"
                    and events[-1].get("passed") == len(CASE_NAMES) and seen == passed_cases == set(CASE_NAMES),
                    "postgres_acceptance_failed")
            worker_result = events[-1]
            self.receipt(event="postgres_cases", outcomes=events, stdout_bytes=len(result.stdout),
                         stderr_bytes=len(result.stderr))
            status = "passed_pending_cleanup"
        except (Refusal, CommandFailure, OSError, ValueError, KeyError) as error:
            self.receipt(event="run_failed", code=error.code if isinstance(error, CommandFailure)
                         else str(error) if isinstance(error, Refusal) else type(error).__name__)
        finally:
            cleaned = self.cleanup()
        final = "passed" if status == "passed_pending_cleanup" and cleaned and self.report_durable and not self.evidence_overflow else "failed"
        self.receipt(event="final", status=final, cleanup="confirmed" if cleaned else "unverified",
                     actual_commit_ack_transport_loss="NOT_TESTED", postgres=worker_result)
        if not self.report_durable or self.evidence_overflow:
            final = "failed"
        print(json.dumps({"status": final, "cleanup": "confirmed" if cleaned else "unverified",
                          "receipt_durable": self.report_durable, "evidence_overflow": self.evidence_overflow,
                          "receipt": str(self.directory / "receipt.json")}))
        return 0 if final == "passed" else 1


def main(argv=None, *, process=None):
    try:
        args = parse(sys.argv[1:] if argv is None else argv)
        root = Path(__file__).resolve().parents[2]
        require(candidate_digest(root) == args.candidate_sha256, "candidate_digest_mismatch")
        process = process or BoundedProcess()
        admit_repository(args, root, process)
        expected_python = root / "backend/.venv/Scripts/python.exe"
        require(Path(sys.executable).resolve() == expected_python.resolve(), "established_interpreter_required")
        local = os.environ.get("LOCALAPPDATA", "")
        require(bool(local), "local_evidence_root_unavailable")
        run = Run(args, root, process)
        directory = Path(local) / "FinLens" / "ownership-acceptance" / run.nonce
        directory.mkdir(parents=True, exist_ok=False)
        run.directory = directory
        run.receipt(event="authorized_inputs", backend_baseline=BACKEND_BASELINE, execution_head=args.expected_head,
                    candidate_sha256=args.candidate_sha256,
                    context=args.docker_context, endpoint=args.expected_context_endpoint, image=args.image)
        return run.execute()
    except (Refusal, CommandFailure, OSError, ValueError) as error:
        print("REFUSED: " + (str(error) if isinstance(error, Refusal) else type(error).__name__))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
