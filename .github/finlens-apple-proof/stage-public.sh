#!/usr/bin/env bash
# Prepare publicly distributable executables/packages. This script never sees the SEC contact.
set -Eeuo pipefail
umask 077
[[ "${GITHUB_RUN_ATTEMPT:-}" == 1 && -n "${RUNNER_TEMP:-}" ]]
[[ ! -v FINLENS_SEC_CONTACT && ! -v OPENAI_API_KEY && ! -v GH_TOKEN && ! -v GITHUB_TOKEN ]]
readonly exact=cfd87915bc679e7f46570f9c8115371c14da1853
readonly pw_image='mcr.microsoft.com/playwright@sha256:06a9939e57531807f8d5fd76ce44b53165ffb7d7501d87ab10e285c20b1e971f'
readonly pw_config='sha256:847f71bbb3f17fc1032d50d75bf6fb3fdcf188b16dff81f24667fe9ae9409e01'
readonly pg_image='pgvector/pgvector@sha256:018b4a92e634c3a5715f613dd43497e3d8028ae051be7ba6fd127bcffb0e7957'
readonly pg_config='sha256:b0108689bf51bd54d3129130967d4adf7ba58b395a9ff6653aa598b5fe7d7ba3'
readonly owned="$RUNNER_TEMP/finlens-apple-owned"
readonly input="$RUNNER_TEMP/finlens-apple-runtime-input"
readonly proof="$(dirname "$(realpath "$0")")"
readonly source="$(realpath "${1:?candidate checkout required}")"
[[ "$(git -C "$source" rev-parse HEAD)" == "$exact" && -z "$(git -C "$source" status --porcelain)" ]]
[[ ! -e "$source/backend/.env" && ! -e "$source/frontend/.env" && ! -e "$source/frontend/.env.local" ]]
mkdir "$owned" "$input"
mkdir "$owned"/{app,test,wheels} "$input/hf"
trap 'printf "%s\n" "HOLD: fixed public runtime preparation failed" >&2' ERR
timeout 120s docker pull --platform linux/amd64 "$pw_image" >"$owned/pw-pull.log" 2>&1
test "$(docker image inspect "$pw_image" --format '{{.Id}} {{.Os}} {{.Architecture}}')" = "$pw_config linux amd64"
timeout 80s docker pull --platform linux/amd64 "$pg_image" >"$owned/pg-pull.log" 2>&1
test "$(docker image inspect "$pg_image" --format '{{.Id}} {{.Os}} {{.Architecture}}')" = "$pg_config linux amd64"
git -C "$source" archive --format=tar "$exact" backend frontend | tar -x -C "$owned/app"
# A fixed Python runtime and approved dependency list; no setup of live services here.
timeout 90s curl --fail --silent --show-error --retry 0 --location --max-redirs 1 \
    --proto '=https' --proto-redir '=https' --max-filesize 38000000 --output "$owned/python.tgz" \
    'https://github.com/astral-sh/python-build-standalone/releases/download/20260814/cpython-3.14.7%2B20260814-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz'
printf '%s  %s\n' cefba034445d2875408d1fd4d5700ae6731563aeb54dcb39fd8164ab5c457533 "$owned/python.tgz" | sha256sum --check --status
python3 -B "$proof/lock_wheel_urls.py" >"$owned/urls.lock"
# The native host interpreter is used only for downloading exact wheel bytes.
timeout 105s python3 -m pip --isolated download --disable-pip-version-check --no-input --no-index \
    --python-version 3.14.7 --platform manylinux_2_39_x86_64 --platform manylinux_2_34_x86_64 \
    --platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 --platform manylinux_2_17_x86_64 \
    --platform manylinux_2_5_x86_64 --platform manylinux2014_x86_64 --implementation cp --abi cp314 \
    --no-deps --only-binary=:all: --no-cache-dir --require-hashes --dest "$owned/wheels" \
    -r "$owned/urls.lock" >"$owned/wheel-prep.log" 2>&1
python3 -B "$proof/verify_acceptance_wheelhouse.py" "$owned/wheels"
timeout 100s python3 -B "$proof/stage_model.py" "$input/hf/hub"
for name in backend-acceptance-cpu.require-hashes.lock public-input-metadata.json sealed-runtime.sh \
    validate-inputs.py check_isolation.py check_database.py check_entrypoints.py ingest-retained-apple.py; do
    install -m 0644 "$proof/$name" "$owned/test/$name"
done
install -d -m 0755 "$owned/test/browser"
install -m 0644 "$proof/browser/"*.ts "$owned/test/browser/"
install -m 0644 "$proof/Dockerfile.proof" "$owned/Dockerfile"
# No model, actual filing, credentials, npm config or Git metadata are in the build context.
printf '%s\n' '*.log' 'urls.lock' 'app/backend/reports' >"$owned/.dockerignore"
timeout 270s docker build --pull=false --iidfile "$owned/app.iid" "$owned" >"$owned/build.log" 2>&1
[[ "$(cat "$owned/app.iid")" =~ ^sha256:[0-9a-f]{64}$ ]]
printf '%s\n' 'PASS: pinned public runtime preparation; no live source or application entered'
