#!/usr/bin/env python3
import argparse
import json
import socket
import threading
import time
import random
import sys

from utils import generate_hash, MEDIA_DOWNLOAD_DIR
from transfer_classes import create_inbound, create_outbound, get_inbound, get_outbound, remove_inbound, remove_outbound

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

    def _generate_nonce(self, length=8):
        return ''.join([str(random.randint(0, 9)) for i in range(length)])

    def send_file_request(self, filepath: str):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] No peer known.")
            return
        nonce = self._generate_nonce()
        payload = {"type": "file_request", "filepath": filepath, "nonce": nonce}
        self.sock.sendto(json.dumps(payload).encode("utf-8"), peer)
        print(f"[->] Requested {filepath} from {peer}")

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
        # outline of process
        # 1) send "file_response" with hash of file, and initial chunk 
        # 2) send chunk + seq of file, await ack
        # 3) repeat for all chunks 
        # 4) send "file_done" with final chunk and seq number
        # 5) wait for "file_accepted"
        # 6) close connection
        hash = generate_hash(filepath)
        transfer = create_outbound(nonce=nonce, filepath=filepath, hash=hash)
        with transfer.lock:
            chunk_data = transfer.chunks[0]
        response_payload = {"type": "file_response", "hash": filehash, "chunk": chunk_data, "nonce": nonce, "filename": filepath, "single_chunk": False}
        self.sock.sendto(json.dumps(payload).encode(), peer)
        return

    def _handle_file_response(self, request):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] Error, no peer known")
            return  

        hash = request.get("filehash")
        initial_chunk = request.get("chunk_data")
        nonce = request.get("nonce")
        filename = request.get("filename")
        is_last = request.get("single_chunk")
        transfer = create_inbound(nonce=nonce, filename=filename, hash=hash)
        with transfer.lock:
            transfer.add_chunk(seq=0, data=initial_chunk, is_last=is_last)
        response_payload = {"type": "file_ack", "seq": 0, "nonce": nonce }
        self.sock.sendto(json.dumps(payload).encode(), peer)
        return

    def _handle_file_chunk(self, request):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] Error, peer not known")
            return
        seq = request.get(seq)
        nonce = request.get(nonce)
        data = request.get(data)
        transfer = get_inbound(nonce=nonce)

        with transfer.lock:
            transfer.add_chunk(seq=seq, data=data, is_last=False)
        response_payload = {"type": "file_ack", "seq": seq, "nonce": nonce} 
        self.sock.sendto(json.dumps(response_payload).encode(), peer)
        return
        
    def _handle_file_ack(self, request):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] Error, peer not known")
            return

        seq = request.get(seq)
        nonce = request.get(nonce)
        transfer = get_outbound(nonce=nonce)
        transfer.mark_acked(seq)
        with transfer.lock:
            data = transfer.chunks[seq+1]
            total_chunks = transfer.total_chunks
        is_last = (seq+2 == total_chunks)
        #index of last chunk == length of chunks list
        payload_type = "file_done" if is_last else "file_chunk"
        transfer_payload = {"type": payload_type, "seq": seq+1, "nonce": nonce, "data": data, "is_last": is_last}
        self.sock.sendto(json.dumps(payload).encode(), peer)
        return

    def _handle_file_done(self, request):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] Error, peer not known")
            return
    
        # needs to append latest chunk
        # needs to assemble file
        # needs to validate file hash
        # needs to re-request corrupted/missing chunks
        # if valid, send "file_complete" to peer, and save file
        seq = request.get(seq)
        nonce = request.get(nonce)
        data = request.get(data)
        is_last = request.get(is_last)
        transfer = get_inbound(nonce=nonce)
        bytes = b""
        with transfer.lock:
            filepath = transfer.filename
            transfer.add_chunk(seq=seq, data=data, is_last=is_last)
            bytes = transfer.assemble()

            if not transfer.has_all_chunks():
                print("[!] DOES NOT HAVE ALL CHUNKS")
                # re-request missing chunks
                return

            if not transfer.validate_hash(bytes):
                print("[!] ERROR WITH FILE INTEGRITY")
                # re-attempt file transfer
                return
        payload = {"type": "file_complete", "nonce": nonce}
        self.sock.sendto(json.dumps(payload).encode(), peer)
        #write bytes buffer to file
        targetFilepath = os.path.join(MEDIA_DOWNLOAD_DIR, filepath)
        with open(targetFilepath, "wb") as target:
            target.write(bytes)
        # remove transfer tracker object
        remove_inbound(nonce=nonce)
        return
    
    def _handle_file_complete(self, request):
        with self.peer_lock:
            peer = self.peer_addr
        if not peer:
            print("[!] Error, peer not known")
            return
        # reomve transfer from list
        # close udp connection with peer
        nonce = request.get("nonce")
        remove_outbound(nonce=nonce)
        self.disconnect_peer()


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
                    self._handle_file_response(parsed)
                elif t == "file_chunk":
                    self._handle_file_chunk(parsed)
                elif t == "file_ack":
                    self._handle_file_ack(parsed)
                elif t== "file_done":
                    self._handle_file_done(parsed)
                elif t=="file_complete":
                    self._handle_file_complete(parsed)
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
