#!/usr/bin/env python3
"""
UDP rendezvous server for NAT hole punching.
No client IDs, only IPs and ports are used.

Protocol:
Client -> Server:
    {"type": "register"}
    {"type": "connect", "target": ["ip", port]}

Server -> Client:
    {"type": "your_addr", "addr": ["ip", port]}
    {"type": "peer", "peer": ["ip", port]}
    {"type": "error", "msg": "description"}
"""

import argparse
import json
import socket
import threading
import time

clients = {}  # (ip, port) -> last_seen_time
lock = threading.Lock()


def handle_packet(data, addr, sock):
    try:
        msg = json.loads(data.decode())
    except Exception:
        return

    now = time.time()
    msg_type = msg.get("type")

    if msg_type == "register":
        with lock:
            clients[addr] = now
        reply = {"type": "your_addr", "addr": [addr[0], addr[1]]}
        sock.sendto(json.dumps(reply).encode(), addr)

    elif msg_type == "connect":
        target = msg.get("target")
        if not target or len(target) != 2:
            err = {"type": "error", "msg": "invalid target"}
            sock.sendto(json.dumps(err).encode(), addr)
            return

        target_ip, target_port = target
        target_addr = (target_ip, int(target_port))

        with lock:
            active_clients = list(clients.keys())

        if target_addr not in active_clients:
            err = {"type": "error", "msg": "target not found or inactive"}
            sock.sendto(json.dumps(err).encode(), addr)
            return

        msg_to_src = {"type": "peer", "peer": [target_ip, int(target_port)]}
        msg_to_dst = {"type": "peer", "peer": [addr[0], addr[1]]}

        sock.sendto(json.dumps(msg_to_src).encode(), addr)
        sock.sendto(json.dumps(msg_to_dst).encode(), target_addr)

        print(f"Linked {addr} <--> {target_addr}")

    else:
        err = {"type": "error", "msg": "unknown message type"}
        sock.sendto(json.dumps(err).encode(), addr)


def cleanup_loop():
    while True:
        time.sleep(30)
        cutoff = time.time() - 120
        with lock:
            inactive = [a for a, t in clients.items() if t < cutoff]
            for a in inactive:
                del clients[a]
        if inactive:
            print(f"Cleaned {len(inactive)} stale clients")


def run_server(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Server listening on {host}:{port}")

    threading.Thread(target=cleanup_loop, daemon=True).start()

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            threading.Thread(target=handle_packet, args=(data, addr, sock), daemon=True).start()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3478)
    args = parser.parse_args()
    run_server(args.host, args.port)
