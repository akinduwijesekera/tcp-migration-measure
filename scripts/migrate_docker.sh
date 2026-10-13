#!/usr/bin/env bash
# Real application-level live migration using Docker checkpoint + CRIU.
#
# NOT automated or tested by run_experiment.py -- this needs a Linux host
# (or two) with CRIU installed and Docker's experimental checkpoint feature
# enabled (dockerd --experimental, or "experimental": true in
# /etc/docker/daemon.json). Run this manually, at the point in your test
# window where you want the migration to happen, while scripts/client.py
# is running against the container.
#
# Single-host demo (checkpoint + restore on the same machine):
#   ./migrate_docker.sh single
#
# Two-host migration (matches the original report's VM1 -> VM2 setup):
#   ./migrate_docker.sh send  <target-user@target-host> <checkpoint-dir>
#   # then, on the target host:
#   ./migrate_docker.sh restore <checkpoint-dir>
set -euo pipefail

IMAGE=tcp-server
CONTAINER=test_server
PORT=8080

build() {
    docker build -t "$IMAGE" "$(dirname "$0")/../app"
}

run() {
    docker run -d --name "$CONTAINER" -p "${PORT}:${PORT}" "$IMAGE"
}

checkpoint() {
    local dir=$1
    docker checkpoint create \
        --checkpoint-dir="$dir" \
        --leave-running \
        --tcp-established \
        "$CONTAINER" checkpoint1
}

case "${1:-}" in
    single)
        build
        run
        echo "Container running. Let the client connect, then press enter to checkpoint+restore locally..."
        read -r
        checkpoint /checkpoints
        docker stop "$CONTAINER"
        docker rm "$CONTAINER"
        docker create --name "$CONTAINER" -p "${PORT}:${PORT}" "$IMAGE"
        docker start --checkpoint-dir=/checkpoints --checkpoint=checkpoint1 "$CONTAINER"
        ;;
    send)
        target=${2:?usage: migrate_docker.sh send <user@host> <checkpoint-dir>}
        dir=${3:?usage: migrate_docker.sh send <user@host> <checkpoint-dir>}
        checkpoint "$dir"
        scp -r "$dir/checkpoint1" "${target}:${dir}/"
        ;;
    restore)
        dir=${2:?usage: migrate_docker.sh restore <checkpoint-dir>}
        build
        docker create --name "$CONTAINER" -p "${PORT}:${PORT}" "$IMAGE"
        docker start --checkpoint-dir="$dir" --checkpoint=checkpoint1 "$CONTAINER"
        ;;
    *)
        echo "usage: $0 {single|send <user@host> <dir>|restore <dir>}" >&2
        exit 1
        ;;
esac
