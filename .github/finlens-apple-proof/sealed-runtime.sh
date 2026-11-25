#!/usr/bin/env bash
# Intended only for a network-none disposable Linux proof container.
set -Eeuo pipefail
umask 077
cd /proof
export PATH="/opt/proof-python/bin:/usr/local/bin:/usr/bin:/bin"
export PYTHONNOUSERSITE=1 HF_HOME=/input/hf HF_HUB_CACHE=/input/hf/hub HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export NEXT_TELEMETRY_DISABLED=1 FINLENS_APPLE_INPUT_DIRECTORY=/input/sec
if [[ -v OPENAI_API_KEY || -v GH_TOKEN || -v GITHUB_TOKEN || -v FINLENS_SEC_CONTACT ]]; then
    printf '%s\n' 'HOLD: forbidden runtime credential' >&2
    exit 2
fi
[[ ! -e /var/run/docker.sock && ! -e app/backend/.env && ! -e app/frontend/.env && ! -e app/frontend/.env.local ]]
export FINLENS_APPLE_ADMITTED=one-use-network-none FINLENS_SERVER_PROFILE=development
export FINLENS_API_BASE_URL=http://127.0.0.1:8000
export DATABASE_URL='postgresql+psycopg://finlens@127.0.0.1:15432/finlens_apple_proof?connect_timeout=5'
export PYTHONPATH=/proof/app/backend
backend='' frontend=''
cleanup() {
    local status=$?
    trap - EXIT
    for pid in "$frontend" "$backend"; do
        if [[ -n "$pid" ]]; then kill -TERM "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    done
    if (( status != 0 )); then printf '%s\n' 'HOLD: no end-to-end admission receipt' >&2; fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
scratch="$(mktemp -d)"
gate() {
    local stage=$1 limit=$2
    shift 2
    if timeout --kill-after=5s "$limit" "$@" >"$scratch/$stage" 2>&1; then
        printf 'PASS: %s\n' "$stage"
    else
        status=$?
        printf 'HOLD: %s (exit %d)\n' "$stage" "$status" >&2
        return "$status"
    fi
}
gate isolation 10s python3.14 -B -I /proof/test/check_isolation.py
gate application_payloads 15s python3.14 -B -I /proof/test/validate-inputs.py /input/sec
gate linked_runtimes 20s python3.14 -B -c '
import platform, sys
import psycopg, torch
from importlib.metadata import version
assert sys.version_info[:3] == (3,14,7) and platform.machine() == "x86_64"
assert torch.version.cuda is None and version("sentence-transformers") == "5.6.0"
'
gate empty_postgres 35s python3.14 -B -I /proof/test/check_database.py empty
gate migrations 65s bash -c 'cd /proof/app/backend && exec python3.14 -B -m alembic upgrade head'
gate migrated_postgres 12s python3.14 -B -I /proof/test/check_database.py migrated
gate real_ingest_and_reopen 185s python3.14 -B /proof/test/ingest-retained-apple.py
gate build_next 240s bash -c 'cd /proof/app/frontend && exec ./node_modules/.bin/next build'
(cd /proof/app/backend && exec python3.14 -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000) >"$scratch/uvicorn" 2>&1 &
backend=$!
(cd /proof/app/frontend && exec ./node_modules/.bin/next start --hostname 127.0.0.1 --port 3000) >"$scratch/next" 2>&1 &
frontend=$!
gate started_entrypoints 35s python3.14 -B -I /proof/test/check_entrypoints.py
gate chromium_normal_home 75s bash -c 'cd /proof/app/frontend && exec ./node_modules/.bin/playwright test -c .proof/playwright.config.ts'
printf '%s\n' 'PASS: normal Home used a clean PostgreSQL database and real no-key MiniLM-backed Apple filing evidence.'
