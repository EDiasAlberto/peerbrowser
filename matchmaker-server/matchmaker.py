#!/usr/bin/env python3
"""
Simple UDP matchmaking server for peer-to-peer hole punching.

Protocol (JSON over UDP):

Client -> Server:
    {"type": "register", "client_id": "unique-id"}
    {"type": "connect", "target_id": "peer-id"}

Server -> Client:
    {"type": "your_addr", "addr": ["ip", port]}
    {"type": "peer", "peer": ["peer_ip", peer_port], "peer_id": "peer-id"}
    {"type": "error", "msg": "description"}
"""

import argparse
import json
import socket
import threading
import time

clients = {}  # client_id -> (addr, last_seen)
lock = threading.Lock()

def handle_packet(data, addr, sock):
    try:
        msg = json.loads(data.decode('utf-8'))
    except Exception:
        return

    now = time.time()
    msg_type = msg.get("type")

    if msg_type == "register":
        client_id = msg.get("client_id")
        if not client_id:
            return
        with lock:
            clients[client_id] = (addr, now)
        your_msg = {"type": "your_addr", "addr": [addr[0], addr[1]]}
        sock.sendto(json.dumps(your_msg).encode(), addr)

    elif msg_type == "connect":
        target_id = msg.get("target_id")
        client_id = msg.get("client_id")
        if not target_id or not client_id:
            return

        with lock:
            src = clients.get(client_id)
            dst = clients.get(target_id)

        if not dst:
            err = {"type": "error", "msg": "target not found or offline"}
            sock.sendto(json.dumps(err).encode(), addr)
            return

        src_addr, _ = src
        dst_addr, _ = dst

        msg_to_src = {"type": "peer", "peer": [dst_addr[0], dst_addr[1]], "peer_id": target_id}
        msg_to_dst = {"type": "peer", "peer": [src_addr[0], src_addr[1]], "peer_id": client_id}

        sock.sendto(json.dumps(msg_to_src).encode(), src_addr)
        sock.sendto(json.dumps(msg_to_dst).encode(), dst_addr)

        print(f"Connected {client_id} ({src_addr}) <--> {target_id} ({dst_addr})")

    else:
        err = {"type": "error", "msg": "unknown message type"}
        sock.sendto(json.dumps(err).encode(), addr)


def cleanup_loop():
    while True:
        time.sleep(30)
        cutoff = time.time() - 120
        with lock:
            to_delete = [cid for cid, (_, t) in clients.items() if t < cutoff]
            for cid in to_delete:
                del clients[cid]
        if to_delete:
            print(f"Cleaned up {len(to_delete)} inactive clients.")


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
        print("Shutting down server.")
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3478)
    args = parser.parse_args()
    run_server(args.host, args.port)
