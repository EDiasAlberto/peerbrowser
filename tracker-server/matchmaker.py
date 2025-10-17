#!/usr/bin/env python3
"""
UDP rendezvous server for NAT hole punching.

Protocol (JSON over UDP):

Client -> Server:
    {"type": "register"}
    {"type": "connect", "target_ip": "x.x.x.x"}   # no port supplied by requester

Server -> Client:
    {"type": "your_addr", "addr": ["ip", port]}
    {"type": "peer", "peer": ["peer_ip", peer_port]}
    {"type": "error", "msg": "description"}
"""

import argparse
import json
import socket
import threading
import time
import queue
from typing import Tuple, Dict

# Shared state
# map: ip_str -> ( (ip, port), last_seen_timestamp )
clients: Dict[str, Tuple[Tuple[str, int], float]] = {}
clients_lock = threading.Lock()

packet_queue = queue.Queue()

# Tunables
CLEANUP_INTERVAL = 30          # seconds between cleanup passes
CLIENT_TIMEOUT = 120           # consider client dead after 120s without re-register
RECV_BUFFER_SIZE = 1024 * 1024 # 1 MiB socket receive buffer
MAX_PACKET_SIZE = 4096         # recvfrom buffer

def _now():
    return time.time()

def handle_packet(data: bytes, addr: Tuple[str, int], sock: socket.socket):
    """
    Process one incoming packet (JSON).
    addr is the observed (ip, port) for the sender.
    """
    try:
        msg = json.loads(data.decode("utf-8"))
    except Exception as e:
        print(f"[decode] dropping non-JSON from {addr}: {e}")
        return

    mtype = msg.get("type")
    if mtype == "register":
        # record the observed address for this client IP
        ip = addr[0]
        now = _now()
        with clients_lock:
            clients[ip] = (addr, now)
        reply = {"type": "your_addr", "addr": [addr[0], addr[1]]}
        try:
            sock.sendto(json.dumps(reply).encode("utf-8"), addr)
        except Exception as e:
            print(f"[send] failed your_addr -> {addr}: {e}")
        # debug log
        print(f"[register] {addr} (stored as {ip})")

    elif mtype == "connect":
        target_ip = msg.get("target_ip")
        if not target_ip:
            err = {"type": "error", "msg": "missing target_ip"}
            try: sock.sendto(json.dumps(err).encode("utf-8"), addr)
            except Exception: pass
            return

        # look up the most recent registration for that IP
        with clients_lock:
            entry = clients.get(target_ip)

        if not entry:
            err = {"type": "error", "msg": f"target {target_ip} not found or offline"}
            try:
                sock.sendto(json.dumps(err).encode("utf-8"), addr)
            except Exception:
                pass
            print(f"[connect] {addr} -> {target_ip} (not found)")
            return

        target_addr, _last_seen = entry
        # Send peer info to both sides:
        # - Tell requester where target is (ip, port)
        # - Tell target where requester is (ip, port)
        msg_to_requester = {"type": "peer", "peer": [target_addr[0], target_addr[1]]}
        msg_to_target    = {"type": "peer", "peer": [addr[0], addr[1]]}

        try:
            sock.sendto(json.dumps(msg_to_requester).encode("utf-8"), addr)
        except Exception as e:
            print(f"[send] failed peer->requester {addr}: {e}")

        try:
            sock.sendto(json.dumps(msg_to_target).encode("utf-8"), target_addr)
        except Exception as e:
            print(f"[send] failed peer->target {target_addr}: {e}")

        print(f"[connect] linked requester {addr} <--> target {target_addr} (target_ip={target_ip})")

    else:
        # unknown message type -> respond with an error
        err = {"type": "error", "msg": "unknown message type"}
        try:
            sock.sendto(json.dumps(err).encode("utf-8"), addr)
        except Exception:
            pass
        print(f"[unknown] from {addr}: {mtype}")


def worker(sock: socket.socket):
    """Background worker that processes queued packets."""
    while True:
        item = packet_queue.get()
        if item is None:
            break  # shutdown signal
        data, addr = item
        try:
            handle_packet(data, addr, sock)
        except Exception as e:
            print(f"[worker] unhandled error processing packet from {addr}: {e}")


def cleanup_loop():
    """Periodically remove stale client registrations."""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        cutoff = _now() - CLIENT_TIMEOUT
        removed = []
        with clients_lock:
            for ip, (addr, last_seen) in list(clients.items()):
                if last_seen < cutoff:
                    removed.append(ip)
                    del clients[ip]
        if removed:
            print(f"[cleanup] removed stale clients: {removed}")


def run_server(host: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # reliability options
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        # optional: SO_REUSEPORT can cause distribution to multiple sockets; avoid unless intended
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUFFER_SIZE)
    except Exception:
        pass

    sock.bind((host, port))
    print(f"[server] listening on {host}:{port}")

    # start worker & cleanup threads
    threading.Thread(target=worker, args=(sock,), daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()

    try:
        while True:
            try:
                data, addr = sock.recvfrom(MAX_PACKET_SIZE)
            except InterruptedError:
                continue
            except Exception as e:
                print(f"[recv] socket error: {e}")
                break

            # quick sanity: update last_seen if this address was already registered
            with clients_lock:
                if addr[0] in clients:
                    # replace last_seen and port in case NAT changed mapping
                    clients[addr[0]] = (addr, _now())

            # queue packet for worker
            packet_queue.put((data, addr))

    except KeyboardInterrupt:
        print("[server] shutting down")
    finally:
        # signal worker to exit and close socket
        packet_queue.put(None)
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="bind host")
    parser.add_argument("--port", type=int, default=3478, help="bind UDP port")
    args = parser.parse_args()
    run_server(args.host, args.port)
