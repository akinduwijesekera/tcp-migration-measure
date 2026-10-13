"""
Orchestrates repeated migration trials and aggregates the results, the way
the original report's Table 12-14 results were produced (N runs per
approach, then averaged).

--mode local
    Runs entirely on this machine with no Docker/CRIU: starts the plain
    Python server, runs the client against it, and at the migration point
    kills and restarts the server process. This does NOT exercise real
    checkpoint/restore (no process state is preserved) -- it only tests
    the measurement harness itself and gives a lower-bound/sanity-check
    "downtime" number (process restart time, not a real stateful
    migration). Use this to verify the harness works before touching
    Docker/CRIU.

--mode docker
    Prints the real migration commands (see scripts/migrate_docker.sh)
    instead of running them, because a real checkpoint/restore migration
    needs CRIU + Docker experimental checkpoint support and (per the
    original report) two separate hosts reachable over the network. This
    script does not attempt that automatically -- run migrate_docker.sh
    yourself at the point in the test window where you want the
    migration to happen, following the setup in README.md.
"""
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import analyse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def run_local_trial(trial_no: int, port: int, duration: float, interval: float,
                     migrate_at: float, kill_for: float, results_dir: Path) -> dict:
    log_path = results_dir / f"client_log_trial{trial_no}.csv"
    server = subprocess.Popen(
        [sys.executable, str(ROOT / "app/server.py"), "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)

    client = subprocess.Popen([
        sys.executable, str(ROOT / "app/client.py"),
        "--port", str(port), "--duration", str(duration),
        "--interval", str(interval), "--log", str(log_path),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(migrate_at)
    server.terminate()
    server.wait()
    time.sleep(kill_for)
    server = subprocess.Popen(
        [sys.executable, str(ROOT / "app/server.py"), "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    client.wait()
    server.terminate()
    server.wait()

    result = analyse(str(log_path))
    result["trial"] = trial_no
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["local", "docker"], default="local")
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--duration", type=float, default=15.0)
    p.add_argument("--interval", type=float, default=0.1)
    p.add_argument("--migrate-at", type=float, default=5.0,
                    help="seconds into the run to trigger the migration")
    p.add_argument("--kill-for", type=float, default=1.0,
                    help="(local mode only) seconds the server is down for")
    p.add_argument("--results-dir", default="results")
    args = p.parse_args()

    results_dir = ROOT / args.results_dir
    results_dir.mkdir(exist_ok=True)

    if args.mode == "docker":
        print(
            "Docker/CRIU mode is not automated by this script -- it needs a real "
            "checkpoint/restore across hosts. See scripts/migrate_docker.sh and "
            "README.md for the manual steps: start app/server.py's container, "
            "start the client against it, then run migrate_docker.sh at the "
            "point you want to measure, then run scripts/measure.py on the "
            "resulting client log yourself."
        )
        return

    rows = []
    for i in range(1, args.trials + 1):
        print(f"[run_experiment] trial {i}/{args.trials}...")
        rows.append(run_local_trial(
            i, args.port, args.duration, args.interval,
            args.migrate_at, args.kill_for, results_dir,
        ))

    out_path = results_dir / "summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} trial(s) to {out_path}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
