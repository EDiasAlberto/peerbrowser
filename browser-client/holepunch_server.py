#!/usr/bin/env python3
import os
import json
import socket
import threading
import time

KEEPALIVE_INTERVAL = 10

class UDPPeerClient:
    def __init__(self, listen_host='0.0.0.0', listen_port=0, room='default', client_id=None):
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

        self.recv_thread = None
        self.punch_thread = None
        self.server_thread = None

    def start(self):
        """Register with the matchmaking server and begin listening for assignments."""
        self._register_with_server()
        self.server_thread = threading.Thread(target=self._server_listener, daemon=True)
        self.server_thread.start()

    def stop(self):
        """Stop all threads and close the socket."""
        self.stop_event.set()
        self.keep_running.clear()
        self.sock.close()
        for thread in [self.recv_thread, self.punch_thread, self.server_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=1)
        print("Client stopped.")

    def send_message(self, message: dict):
        """Send a JSON message to the connected peer."""
        with self.lock:
            peer = self.shared.get("peer")
        if peer:
            try:
                self.sock.sendto(json.dumps(message).encode("utf-8"), peer)
            except Exception as e:
                print("Error sending message:", e)
        else:
            print("No peer known yet.")

    def request_connection(self, target_id: str):
        """Ask the server to connect this client with another by ID."""
        msg = {"type": "connect", "target": target_id}
        try:
            self.sock.sendto(json.dumps(msg).encode("utf-8"), self.server_addr)
            print(f"Requested connection with {target_id}")
        except Exception as e:
            print("Error requesting connection:", e)

    def wait_for_peer(self, timeout=None):
        """Block until a direct connection is established."""
        return self.first_packet_event.wait(timeout=timeout)

    # Internal methods --------------------------------------------------

    def _register_with_server(self):
        msg = {"type": "register", "room": self.room}
        if self.client_id:
            msg["client_id"] = self.client_id
        self.sock.sendto(json.dumps(msg).encode("utf-8"), self.server_addr)
        print(f"Registered with server {self.server_addr} in room '{self.room}'")

    def _server_listener(self):
        """Wait for peer assignment or control messages from the server."""
        self.sock.settimeout(1.0)
        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            if addr != self.server_addr:
                # May be a packet from the peer
                with self.lock:
                    peer = self.shared.get("peer")
                if peer and addr == peer:
                    self._handle_peer_data(data, addr)
                continue

            # Message from server
            try:
                msg = json.loads(data.decode("utf-8"))
            except Exception:
                continue

            mtype = msg.get("type")

            if mtype == "peer":
                peer = tuple(msg.get("peer"))
                with self.lock:
                    self.shared["peer"] = peer
                print(f"Received peer info from server: {peer}")
                self._start_peer_threads()

            elif mtype == "wait":
                print("Server: waiting for another client...")

            elif mtype == "info":
                print("Server message:", msg.get("msg"))

    def _start_peer_threads(self):
        """Start peer communication threads once peer info is known."""
        if self.recv_thread and self.recv_thread.is_alive():
            return
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.punch_thread = threading.Thread(target=self._punch_loop, daemon=True)
        self.recv_thread.start()
        self.punch_thread.start()

    def _recv_loop(self):
        """Handle incoming UDP packets."""
        self.sock.settimeout(1.0)
        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            with self.lock:
                peer = self.shared.get("peer")

            if peer and addr == peer:
                self._handle_peer_data(data, addr)
            else:
                continue

    def _handle_peer_data(self, data, addr):
        """Process peer data."""
        try:
            parsed = json.loads(data.decode("utf-8"))
            print(f"Peer -> {addr}: {parsed}")
        except Exception:
            print(f"Peer -> {addr}: RAW {data!r}")

        if not self.first_packet_event.is_set():
            self.first_packet_event.set()
            print("=== Direct connection established ===")

    def _punch_loop(self):
        """Maintain NAT mapping with periodic UDP packets."""
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
