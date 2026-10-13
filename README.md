# TCP Connection Migration — Measurement Harness

This is the application-side half of my UCL 3rd year project,
"Connection Migration in TCP/IP Networks" — measuring TCP connection
continuity during application-level live migration (Docker + CRIU
checkpoint/restore). **This repo is incomplete**: the original project
also evaluated hypervisor-level migration using VMware snapshots, which
isn't included here. The original project's code was lost, so this is a
fresh, self-contained reimplementation rather than the recovered original.

## What it measures

A client sends a numbered heartbeat to the server at a fixed interval and
logs, per message: send time, receive time, round-trip latency, and
whether it was lost. From that log, `scripts/measure.py` computes:

- **Downtime** — the largest gap between two successful round trips
- **Packet loss %** — heartbeats sent vs. successfully echoed
- **Latency** — mean / median / p95 round-trip time

## Status

- `app/server.py`, `app/client.py`, `scripts/measure.py`, and
  `scripts/run_experiment.py --mode local` are **written and tested** —
  verified end-to-end by running the server and client, killing and
  restarting the server mid-test to simulate a migration gap, and
  confirming the measured downtime/packet-loss/latency numbers matched
  what actually happened.
- `scripts/migrate_docker.sh` (real Docker checkpoint + CRIU
  restore) is **written but not run** — it needs a Linux host with CRIU
  installed and Docker's experimental checkpoint feature enabled, which
  this environment doesn't have. Review it before running it for real.

`--mode local` kills and restarts a plain OS process rather than
checkpointing and restoring one — it's there to validate the measurement
harness itself, not to produce real application-migration numbers. Real
numbers need the Docker/CRIU path.

## Running the local (no-Docker) harness

```bash
python3 scripts/run_experiment.py --mode local --trials 5 \
    --duration 15 --migrate-at 5 --kill-for 1
```

Writes one CSV log per trial plus `results/summary.csv` with the
aggregated metrics.

## Running a real Docker + CRIU migration

Requires a Linux host with CRIU installed and Docker experimental
checkpoint support enabled (`"experimental": true` in
`/etc/docker/daemon.json`, or `dockerd --experimental`).

```bash
# build and start the server container
docker build -t tcp-server app/
docker run -d --name test_server -p 8080:8080 tcp-server

# in another terminal, start the measurement client against it
python3 app/client.py --port 8080 --duration 30 --log results/client_log.csv

# partway through, trigger the migration
scripts/migrate_docker.sh single      # same-host demo, or
scripts/migrate_docker.sh send <user@target-host> /checkpoints   # two-host

# once the client finishes:
python3 scripts/measure.py results/client_log.csv
```

## Layout

```
app/
  server.py          TCP echo server (timestamps every reply)
  client.py          Heartbeat client with reconnect + CSV logging
  Dockerfile          Container image for the server
scripts/
  measure.py          Turns one client log into downtime/loss/latency
  run_experiment.py   Runs N trials and aggregates results
  migrate_docker.sh   Real docker checkpoint/CRIU migration commands
```
