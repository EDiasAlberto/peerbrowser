#!/usr/bin/env python3
"""
UDP Hole-Punching Client (Serverless after peer discovery)

- Contacts matchmaking server once to get peer info.
- Maintains a keepalive/punch loop with the peer.
- Allows external control for sending messages or stopping threads.
"""

import os
import json
import socket
import threading
import time

KEEPALIVE_INTERVAL = 10

class UDPPeerClient:
    def __init__(self, listen_host='0.0.0.0', listen_port=0, room='default', client_id=None):
        """
        Initialize the UDP client.

        Args:
            listen_host (str): Local interface to bind.
            listen_port (int): Local port. Use 0 for any available port.
            room (str): Room name for matchmaking.
            client_id (str): Optional client identifier.
        """
        self.server_host = os.environ.get("MATCHMAKER_HOST")
        self.server_port = int(os.environ.get("MATCHMAKER_PORT", 12345))
        if not self.server_host:
            raise ValueError("Environment variable MATCHMAKER_HOST must be set.")

        self.server_addr = (self.server_host, self.server_port)
        self.room = room
        self.client_id = client_id
        self.shared = {"peer": None}

        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.first_packet_event = threading.Event()
        self.keep_running = threading.Event()
        self.keep_running.set()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((listen_host, listen_port))
        print(f"Local socket bound to {self.sock.getsockname()}")

        # Threads
        self.recv_thread = None
        self.punch_thread = None

    def start(self):
        """Start client: register with server and launch threads."""
        self._register_with_server()
        self._start_threads()

    def stop(self):
        """Stop all threads and close the socket."""
        self.stop_event.set()
        self.keep_running.clear()
        self.sock.close()
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join()
        if self.punch_thread and self.punch_thread.is_alive():
            self.punch_thread.join()
        print("Client stopped.")

    def send_message(self, message: dict):
        """Send a JSON message to the peer."""
        with self.lock:
            peer = self.shared.get("peer")
        if peer:
            try:
                self.sock.sendto(json.dumps(message).encode("utf-8"), peer)
            except Exception as e:
                print("Error sending message:", e)
        else:
            print("No peer known yet.")

    def _register_with_server(self):
        """Register with the matchmaking server and retrieve peer info."""
        regmsg = {"type": "register", "room": self.room}
        if self.client_id:
            regmsg["client_id"] = self.client_id

        self.sock.sendto(json.dumps(regmsg).encode("utf-8"), self.server_addr)
        print(f"Sent registration to server {self.server_addr}")

        self.sock.settimeout(10.0)
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                if addr != self.server_addr:
                    continue
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "peer":
                    peer = tuple(msg.get("peer"))
                    with self.lock:
                        self.shared['peer'] = peer
                    print("Server provided peer:", peer)
                    break
            except socket.timeout:
                raise TimeoutError("Timed out waiting for server response")
            except Exception:
                continue

    def _start_threads(self):
        """Launch receive and punch threads."""
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.punch_thread = threading.Thread(target=self._punch_loop, daemon=True)
        self.recv_thread.start()
        self.punch_thread.start()

    def _recv_loop(self):
        """Receive packets from peer or other hosts."""
        self.sock.settimeout(1.0)
        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception as e:
                if not self.stop_event.is_set():
                    print("Receive loop error:", e)
                break

            with self.lock:
                peer = self.shared.get("peer")

            if peer and addr == peer:
                try:
                    parsed = json.loads(data.decode("utf-8"))
                    print(f"Peer -> {addr}: {parsed}")
                except Exception:
                    print(f"Peer -> {addr}: RAW {data!r}")

                if not self.first_packet_event.is_set():
                    self.first_packet_event.set()
                    print("=== Direct connection established ===")
            else:
                print(f"Received UDP from {addr}: {data!r}")

    def _punch_loop(self):
        """Send keepalive/punch packets to the peer."""
        while self.keep_running.is_set():
            with self.lock:
                peer = self.shared.get("peer")
            if peer:
                try:
                    payload = json.dumps({"type": "punch", "t": time.time()})
                    self.sock.sendto(payload.encode("utf-8"), peer)
                    self.sock.sendto(b'\x00', peer)
                except Exception as e:
                    print("Error punching peer:", e)
            time.sleep(KEEPALIVE_INTERVAL)

    def wait_for_peer(self, timeout=None):
        """
        Wait until the first packet from peer is received.
        
        Args:
            timeout (float): Maximum seconds to wait. None = infinite.
        """
        return self.first_packet_event.wait(timeout=timeout)
