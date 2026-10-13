"""
Measurement client for the TCP connection-migration test.

Sends a numbered heartbeat every `--interval` seconds and logs, for every
sequence number: when it was sent, whether/when a reply came back, and the
round-trip latency. On a connection drop (e.g. the server being migrated)
it keeps retrying with a short backoff and keeps counting sequence numbers,
so the resulting log captures exactly the gap a migration causes.

Log format (CSV): seq,send_ts,recv_ts,rtt_ms,status
  status is one of: ok, lost, reconnecting
"""
import argparse
import csv
import socket
import sys
import time


def run_client(host: str, port: int, duration: float, interval: float, log_path: str) -> None:
    seq = 0
    t_end = time.time() + duration
    sock = None

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seq", "send_ts", "recv_ts", "rtt_ms", "status"])
        f.flush()

        while time.time() < t_end:
            if sock is None:
                try:
                    sock = socket.create_connection((host, port), timeout=2)
                    sock.settimeout(interval * 3)
                    print(f"[client] connected to {host}:{port}", flush=True)
                except OSError as e:
                    writer.writerow([seq, time.time(), "", "", "reconnecting"])
                    f.flush()
                    time.sleep(0.2)
                    continue

            seq += 1
            send_ts = time.time()
            msg = f"{seq} {send_ts}\n"
            try:
                sock.sendall(msg.encode("utf-8"))
                reply = sock.recv(4096).decode("utf-8").strip()
                recv_ts = time.time()
                if not reply:
                    raise ConnectionError("empty reply")
                rtt_ms = (recv_ts - send_ts) * 1000
                writer.writerow([seq, send_ts, recv_ts, f"{rtt_ms:.2f}", "ok"])
            except (OSError, ConnectionError) as e:
                writer.writerow([seq, send_ts, "", "", "lost"])
                print(f"[client] seq={seq} lost ({e}), reconnecting...", flush=True)
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None
            f.flush()
            time.sleep(interval)

    if sock is not None:
        sock.close()
    print(f"[client] done, log written to {log_path}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--duration", type=float, default=20.0, help="seconds to run")
    p.add_argument("--interval", type=float, default=0.1, help="seconds between heartbeats")
    p.add_argument("--log", default="results/client_log.csv")
    args = p.parse_args()
    try:
        run_client(args.host, args.port, args.duration, args.interval, args.log)
    except KeyboardInterrupt:
        sys.exit(0)
