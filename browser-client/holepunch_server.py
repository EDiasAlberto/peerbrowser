#!/usr/bin/env python3
import argparse
import json
import socket
import threading
import time
import sys

KEEPALIVE_INTERVAL = 10.0

class UDPClient:
    def __init__(self, server_host: str, server_port: int):
        self.server_addr = (server_host, int(server_port))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))
        self.sock.settimeout(1.0)

        self.peer_addr = None
        self.peer_lock = threading.Lock()
        self.alive = threading.Event()
        self.alive.set()
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.punch_thread = None

    def start(self):
        self.listener_thread.start()
        self.register_with_server()

    def stop(self):
        self.alive.clear()
        if self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1)
        if self.punch_thread and self.punch_thread.is_alive():
            self.punch_thread.join(timeout=1)
        try:
            self.sock.close()
        except Exception:
            pass

    def register_with_server(self):
        msg = {"type": "register"}
        self.sock.sendto(json.dumps(msg).encode(), self.server_addr)
        print(f"[i] Sent register to {self.server_addr}")

    def request_connect(self, target_ip: str):
        msg = {"type": "connect", "target_ip": target_ip}
        self.sock.sendto(json.dumps(msg).encode(), self.server_addr)
        print(f"[i] Sent connect request for {target_ip} to server")

    def send_text_to_peer(self, text: str):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] No peer known.")
            return
        payload = {"type": "msg", "msg": text, "t": time.time()}
        self.sock.sendto(json.dumps(payload).encode(), peer)
        print(f"[->] {peer}: {text}")

    def _listen_loop(self):
        while self.alive.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception:
                break

            try:
                parsed = json.loads(data.decode("utf-8"))
            except Exception:
                parsed = None

            if parsed and addr == self.server_addr:
                t = parsed.get("type")
                if t == "your_addr":
                    print(f"[i] Your external address: {parsed['addr']}")
                elif t == "peer":
                    p = parsed.get("peer")
                    if p:
                        with self.peer_lock:
                            self.peer_addr = (p[0], int(p[1]))
                        print(f"[i] Connected to peer {self.peer_addr}")
                        self._start_punching()
                elif t == "error":
                    print(f"[server error] {parsed.get('msg')}")
                continue

            with self.peer_lock:
                peer = self.peer_addr
            if peer and addr == peer:
                try:
                    m = json.loads(data.decode("utf-8"))
                    if m.get("type") == "msg":
                        print(f"[<-] {m['msg']}")
                    else:
                        print(f"[<-] {m}")
                except Exception:
                    print(f"[<- RAW] {data!r}")
            else:
                print(f"[?] From {addr}: {data!r}")

    def _start_punching(self):
        if self.punch_thread and self.punch_thread.is_alive():
            return
        self.punch_thread = threading.Thread(target=self._punch_loop, daemon=True)
        self.punch_thread.start()

    def _punch_loop(self):
        while self.alive.is_set():
            with self.peer_lock:
                peer = self.peer_addr
            if not peer:
                time.sleep(1)
                continue
            try:
                payload = {"type": "punch", "t": time.time()}
                self.sock.sendto(json.dumps(payload).encode(), peer)
                self.sock.sendto(b"\x00", peer)
            except Exception as e:
                print("[!] Punch error:", e)
            time.sleep(KEEPALIVE_INTERVAL)


def repl(client):
    print("Commands:\n  connect <ip>\n  show\n  quit\n  help\n[Any other text sends to peer]")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[i] Exiting.")
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()
        if cmd == "connect" and len(parts) == 2:
            client.request_connect(parts[1])
        elif cmd == "show":
            with client.peer_lock:
                print(f"[i] Peer: {client.peer_addr}")
        elif cmd == "help":
            print("Commands:\n  connect <ip>\n  show\n  quit\n  help")
        elif cmd == "quit":
            break
        else:
            client.send_text_to_peer(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--port", type=int, default=3478)
    args = parser.parse_args()

    c = UDPClient(args.server, args.port)
    c.start()
    try:
        repl(c)
    finally:
        c.stop()
        sys.exit(0)
