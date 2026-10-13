"""
Turns a client CSV log into the metrics the report measured on the
application-migration side: downtime, packet loss, and latency.

Downtime is computed as the largest gap between an "ok" row's send_ts and
the next "ok" row's send_ts — i.e. how long the service was unreachable
from the client's point of view, which is the same definition the original
report used (client reconnection time).
"""
import argparse
import csv
import statistics as stats


def analyse(log_path: str) -> dict:
    rows = []
    with open(log_path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    total = len(rows)
    ok_rows = [r for r in rows if r["status"] == "ok"]
    lost = total - len(ok_rows)
    packet_loss_pct = (lost / total * 100) if total else 0.0

    rtts = [float(r["rtt_ms"]) for r in ok_rows if r["rtt_ms"]]
    latency = {
        "mean_ms": stats.mean(rtts) if rtts else None,
        "median_ms": stats.median(rtts) if rtts else None,
        "p95_ms": stats.quantiles(rtts, n=20)[18] if len(rtts) >= 20 else (max(rtts) if rtts else None),
    }

    # Downtime: largest gap between consecutive successful round trips.
    ok_times = sorted(float(r["send_ts"]) for r in ok_rows)
    downtime_s = 0.0
    for a, b in zip(ok_times, ok_times[1:]):
        downtime_s = max(downtime_s, b - a)

    return {
        "total_messages": total,
        "successful": len(ok_rows),
        "lost": lost,
        "packet_loss_pct": round(packet_loss_pct, 2),
        "downtime_s": round(downtime_s, 3),
        **{k: (round(v, 2) if v is not None else None) for k, v in latency.items()},
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("log_path")
    args = p.parse_args()
    result = analyse(args.log_path)
    for k, v in result.items():
        print(f"{k:>16}: {v}")
