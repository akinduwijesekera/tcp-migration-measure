"""
TCP echo server used as the migration target.

Each received line is echoed back immediately, prefixed with the server's
own receive timestamp, so the client can measure round-trip latency and
detect dropped/duplicate sequence numbers around a migration event.

Protocol (newline-delimited, one message per line):
    client -> server: "<seq> <client_send_ts>"
    server -> client: "<seq> <client_send_ts> <server_recv_ts>"
"""
import argparse
import socket
import sys
import time


def serve(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(5)
        print(f"[server] listening on {host}:{port}", flush=True)

        while True:
            conn, addr = s.accept()
            print(f"[server] client connected: {addr}", flush=True)
            buf = b""
            with conn:
                conn.settimeout(30)
                try:
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            if not line.strip():
                                continue
                            recv_ts = time.time()
                            reply = line.decode("utf-8").strip() + f" {recv_ts}\n"
                            conn.sendall(reply.encode("utf-8"))
                except (ConnectionResetError, BrokenPipeError, socket.timeout) as e:
                    print(f"[server] client disconnected ({e})", flush=True)
            print(f"[server] connection closed: {addr}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        sys.exit(0)
