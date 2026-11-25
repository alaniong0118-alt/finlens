#!/usr/bin/env bash
# Test-only launch. Never download, re-run, expose a port, or touch an existing service.
set -Eeuo pipefail
umask 077
[[ "${GITHUB_RUN_ATTEMPT:-}" == 1 && "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ && -n "${RUNNER_TEMP:-}" ]]
[[ ! -v FINLENS_SEC_CONTACT && ! -v OPENAI_API_KEY && ! -v GH_TOKEN && ! -v GITHUB_TOKEN ]]
readonly pg_image='pgvector/pgvector@sha256:018b4a92e634c3a5715f613dd43497e3d8028ae051be7ba6fd127bcffb0e7957'
readonly pg_config='sha256:b0108689bf51bd54d3129130967d4adf7ba58b395a9ff6653aa598b5fe7d7ba3'
readonly app_image="${1:?expected previously built image ID}"
readonly input="${2:?expected checked input mount}"
[[ "$app_image" =~ ^sha256:[a-f0-9]{64}$ && "$app_image" != "$pg_config" ]]
[[ "$(realpath "$input")" == "$input" && "$input" == "$RUNNER_TEMP/finlens-apple-runtime-input" ]]
[[ -d "$input/sec" && -d "$input/hf/hub" ]]
[[ "$(docker image inspect "$pg_image" --format '{{.Id}}')" == "$pg_config" ]]
[[ "$(docker image inspect "$app_image" --format '{{.Id}}')" == "$app_image" ]]
[[ "$(docker image inspect "$app_image" --format '{{json .Config.Volumes}}')" == null ]]
marker="finlens-apple-one-use:$GITHUB_RUN_ID"
name="finlens-apple-$GITHUB_RUN_ID"
pg='' app=''
cleanup() {
    local rc=$?
    trap - EXIT
    for id in "$app" "$pg"; do
        if [[ "$id" =~ ^[a-f0-9]{64}$ ]]; then
            if [[ "$(docker inspect "$id" --format '{{index .Config.Labels "finlens.apple.owner"}}' 2>/dev/null)" == "$marker" ]]; then
                docker rm -fv "$id" >/dev/null 2>&1 || rc=1
                if docker container inspect "$id" >/dev/null 2>&1; then rc=1; fi
            else
                rc=1
            fi
        fi
    done
    if (( rc != 0 )); then printf '%s\n' 'HOLD: sealed job or owned-container cleanup failed' >&2; fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
pg=$(docker create --pull=never --name "$name-pg" --label "finlens.apple.owner=$marker" \
    --network none --restart no --security-opt no-new-privileges \
    --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev --tmpfs /var/run/postgresql:rw,nosuid,nodev \
    --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_USER=finlens --env POSTGRES_DB=finlens_apple_proof \
    "$pg_image" -c listen_addresses=127.0.0.1 -c port=15432)
[[ "$pg" =~ ^[a-f0-9]{64}$ ]]
[[ "$(docker inspect "$pg" --format '{{.HostConfig.NetworkMode}} {{.HostConfig.Privileged}} {{len .HostConfig.PortBindings}} {{.Image}}')" == "none false 0 $pg_config" ]]
[[ "$(docker inspect "$pg" --format '{{len .HostConfig.Binds}}')" == 0 ]]
docker start "$pg" >/dev/null
app=$(docker create --pull=never --name "$name-app" --label "finlens.apple.owner=$marker" \
    --network "container:$pg" --restart no --init --security-opt no-new-privileges \
    --cap-drop ALL --shm-size 512m --pids-limit 600 \
    --mount "type=bind,source=$input,target=/input,readonly" \
    --entrypoint /bin/bash "$app_image" -c 'exec /bin/sleep 1200')
[[ "$app" =~ ^[a-f0-9]{64}$ ]]
[[ "$(docker inspect "$app" --format '{{.HostConfig.NetworkMode}} {{.HostConfig.Privileged}} {{len .HostConfig.PortBindings}} {{.Image}}')" == "container:$pg false 0 $app_image" ]]
[[ "$(docker inspect "$app" --format '{{range .Mounts}}{{.Type}} {{.Destination}} {{.RW}}{{end}}')" == "bind /input false" ]]
docker start "$app" >/dev/null
pg_pid="$(docker inspect "$pg" --format '{{.State.Pid}}')"
app_pid="$(docker inspect "$app" --format '{{.State.Pid}}')"
[[ "$pg_pid" =~ ^[1-9][0-9]*$ && "$app_pid" =~ ^[1-9][0-9]*$ ]]
pg_ns="$(sudo -n readlink "/proc/$pg_pid/ns/net")"
app_ns="$(sudo -n readlink "/proc/$app_pid/ns/net")"
[[ "$pg_ns" == "$app_ns" && "$pg_ns" != "$(readlink /proc/self/ns/net)" && "$pg_ns" =~ ^net:\[[0-9]+\]$ ]]
printf '%s\n' 'PASS: one private shared network namespace, no published ports, exact images'
timeout --signal=TERM --kill-after=15s 12m docker exec "$app" /bin/bash /proof/test/sealed-runtime.sh
