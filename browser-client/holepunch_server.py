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
        self.punch_alive = threading.Event()

    def start(self):
        self.listener_thread.start()
        self.register_with_server()

    def stop(self):
        self.alive.clear()
        self.punch_alive.clear()
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

    def _generate_nonce(length=8):
        return ''.join([str(random.randint(0, 9)) for i in range(length)])

    def send_file_request(self, filepath: str):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] No peer known.")
            return
        nonce = self._generate_nonce()
        payload = {"type": "file_request", "filepath": filepath, "nonce": nonce}
        self.sock.sendto(json.dumps(payload).encode(), peer)
        print(f"[->] Requested {file} from {peer}")

    def send_text_to_peer(self, text: str):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] No peer known.")
            return
        payload = {"type": "msg", "msg": text, "t": time.time()}
        self.sock.sendto(json.dumps(payload).encode(), peer)
        print(f"[->] {peer}: {text}")

    def disconnect_peer(self):
        """Gracefully disconnect from current peer"""
        with self.peer_lock:
            peer = self.peer_addr
            if not peer:
                print("[!] No active connection.")
                return
            payload = {"type": "disconnect"}
            self.sock.sendto(json.dumps(payload).encode(), peer)
            print(f"[i] Sent disconnect to {peer}")
            self._handle_disconnect()

    def _handle_disconnect(self):
        """Handle local disconnection logic"""
        with self.peer_lock:
            if self.peer_addr:
                print(f"[i] Disconnected from peer {self.peer_addr}")
            self.peer_addr = None
        self.punch_alive.clear()

    def _handle_file_request(self, request):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] No peer known.")
            return
        filepath = request.get("filepath")
        nonce = request.get("nonce")
        print(f"Received request for file {filepath}, nonce {nonce}, from peer {peer}")
        return

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

            # Messages from server
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

            # Messages from peer
            with self.peer_lock:
                peer = self.peer_addr
            if peer and addr == peer:
                t = parsed.get("type") if parsed else None
                if t == "msg":
                    print(f"[<-] {parsed['msg']}")
                elif t == "disconnect":
                    print("[i] Peer disconnected.")
                    self._handle_disconnect()
                elif t == "punch":
                    # silent heartbeat
                    pass
                elif t == "file_request":
                    self._handle_file_request(parsed)
                elif t == "file_response":
                    print("Received file!")
                elif t == "file_chunk":
                    print("RECEIVED FILE CHUNK")
                elif t == "file_ack":
                    print("PEER RECEIVED FILE")
                elif t== "file_done":
                    print("PEER COMPLETED TRANSFER, CHECK HASH")
                else:
                    print(f"[<-] {parsed}")
            else:
                # Ignore unrelated packets
                pass

    def _start_punching(self):
        if self.punch_thread and self.punch_thread.is_alive():
            self.punch_alive.set()
            return
        self.punch_alive.set()
        self.punch_thread = threading.Thread(target=self._punch_loop, daemon=True)
        self.punch_thread.start()

    def _punch_loop(self):
        while self.alive.is_set():
            self.punch_alive.wait()
            if not self.alive.is_set():
                break
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
    print(
        "Commands:\n"
        "  connect <ip>  — connect to a peer by IP\n"
        "  show          — show current peer\n"
        "  disconnect    — terminate current connection\n"
        "  quit          — exit\n"
        "[Any other text is sent to peer]"
    )
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
        elif cmd == "disconnect":
            client.disconnect_peer()
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
