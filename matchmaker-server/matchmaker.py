#!/usr/bin/env python3
"""
Simple UDP matchmaking server for hole punching.

Protocol (JSON over UDP):
- Client -> Server: {"type":"register","room":"room-name","client_id":"optional-id"}
- Server -> Client: {"type":"your_addr","addr":["ip", port]}
- Server -> Both clients when a pair is available:
    {"type":"peer","peer":["peer_ip", peer_port]}

Run:
    python3 server.py --host 0.0.0.0 --port 3478
"""
import argparse
import json
import socket
import threading
import time

rooms = {}  # room -> list of (addr, client_id, last_seen_time)
lock = threading.Lock()

def handle_packet(data, addr, sock):
    try:
        msg = json.loads(data.decode('utf-8'))
    except Exception:
        print("Received non-json from", addr)
        return

    now = time.time()

    if msg.get('type') == 'register':
        room = msg.get('room', 'default')
        client_id = msg.get('client_id')
        with lock:
            lst = rooms.setdefault(room, [])
            # update existing entry for same addr if present
            updated = False
            for i, (a, cid, _t) in enumerate(lst):
                if a == addr:
                    lst[i] = (addr, client_id, now)
                    updated = True
                    break
            if not updated:
                lst.append((addr, client_id, now))
            # keep only last 10 to avoid unbounded growth
            if len(lst) > 10:
                lst = lst[-10:]
                rooms[room] = lst

            # send back observed address (as server sees it)
            your_msg = {"type": "your_addr", "addr": [addr[0], addr[1]]}
            sock.sendto(json.dumps(your_msg).encode('utf-8'), addr)

            # if at least two clients in room, pair the oldest two that are distinct
            if len(lst) >= 2:
                # choose first two distinct addresses
                pair = None
                for i in range(len(lst)):
                    for j in range(i+1, len(lst)):
                        if lst[i][0] != lst[j][0]:
                            pair = (lst[i][0], lst[j][0])
                            break
                    if pair:
                        break
                if pair:
                    a_addr, b_addr = pair
                    # send peer info to both
                    msg_to_a = {"type":"peer", "peer":[b_addr[0], b_addr[1]]}
                    msg_to_b = {"type":"peer", "peer":[a_addr[0], a_addr[1]]}
                    sock.sendto(json.dumps(msg_to_a).encode('utf-8'), a_addr)
                    sock.sendto(json.dumps(msg_to_b).encode('utf-8'), b_addr)
                    print(f"Paired {a_addr} <--> {b_addr} in room '{room}'")
    else:
        # unknown message types: ignore or optionally echo
        print("Unknown message type from", addr, msg.get('type'))

def cleanup_loop():
    while True:
        time.sleep(30)
        cutoff = time.time() - 120  # 2 minutes
        changed = False
        with lock:
            for room in list(rooms.keys()):
                lst = rooms[room]
                newlst = [x for x in lst if x[2] >= cutoff]
                if len(newlst) != len(lst):
                    rooms[room] = newlst
                    changed = True
            # drop empty rooms
            for room in list(rooms.keys()):
                if not rooms[room]:
                    del rooms[room]
                    changed = True
        if changed:
            print("Cleaned up old entries; current rooms:", {r: len(v) for r, v in rooms.items()})

def run_server(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Server listening on {host}:{port}")
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    try:
        while True:
            data, addr = sock.recvfrom(4096)
            # handle in thread so server remains responsive
            threading.Thread(target=handle_packet, args=(data, addr, sock), daemon=True).start()
    except KeyboardInterrupt:
        print("Shutting down server.")
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="bind host")
    parser.add_argument("--port", type=int, default=3478, help="bind port")
    args = parser.parse_args()
    run_server(args.host, args.port)
