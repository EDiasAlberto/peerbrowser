import threading
import time
import base64
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
import os

from utils import generate_hash, MEDIA_DOWNLOAD_DIR, TEMPFILE_LOC

# Global dictionaries (thread-safe via locks)
inbound_transfers: Dict[str, "InboundTransfer"] = {}
outbound_transfers: Dict[str, "OutboundTransfer"] = {}

inbound_lock = threading.Lock()   # protects inbound_transfers mapping
outbound_lock = threading.Lock()  # protects outbound_transfers mapping

# Constants for cleanup/timeouts
TRANSFER_STALE_SECONDS = 300     # 5 minutes
CHUNK_RETRANSMIT_TIMEOUT = 1.0
CHUNK_MAX_RETRIES = 6

@dataclass
class InboundTransfer:
    """
    State for a transfer we are RECEIVING (peer -> us).
    Access to members must be protected by self.lock.
    """
    nonce: str
    hash: str
    expected_chunks: Optional[int] = None   # None until last chunk informs
    chunks: Dict[int, bytes] = field(default_factory=dict) # maps seq to data
    received: Set[int] = field(default_factory=set)
    last_activity: float = field(default_factory=time.time)
    filename: Optional[str] = None
    state: str = "receiving"  # "receiving", "done", "cancelled", "error"
    lock: threading.RLock = field(default_factory=threading.RLock) # used to add to dict of transfers

    def is_complete(self):
        with self.lock:
            return self.state == "done"

    def touch(self):
        with self.lock:
            self.last_activity = time.time()

    def add_chunk(self, seq: int, data: bytes, is_last: bool):
        #store received chunk, and keep track of seq nums
        with self.lock:
            if self.state != "receiving":
                return
            self.chunks[seq] = data
            self.received.add(seq)
            if is_last:
                # upon receiving last packet, total=index+1
                self.expected_chunks = seq + 1
            self.last_activity = time.time()

    def has_all_chunks(self) -> bool:
        # does not validate integrity/validity
        # does a quick check of number of packets
        with self.lock:
            if self.expected_chunks is None:
                return False
            return len(self.received) >= self.expected_chunks

    def assemble(self) -> bytes:
        # loops over received chunks, forms list
        # joins elements in list in binary string
        with self.lock:
            if not self.is_complete():
                raise RuntimeError("Transfer not complete")
            parts = []
            for i in range(self.expected_chunks):
                parts.append(bytes.fromhex(self.chunks[i]))
            return b"".join(parts)

    def validate_hash(self, data: bytes) -> bool:
        with open(TEMPFILE_LOC, "wb") as bFile:
            bFile.write(data)
        new_hash = generate_hash(TEMPFILE_LOC)
        with self.lock:
            return new_hash == self.hash


@dataclass
class OutboundTransfer:
    """
    State for a transfer we are SENDING (us -> peer).
    Access to members must be protected by self.lock.
    """
    nonce: str
    filepath: str
    hash: str 
    chunk_size: int
    chunks: Dict[int, bytes] = field(default_factory=dict)   # seq -> bytes
    total_chunks: int = 0
    acks: Set[int] = field(default_factory=set)   # seqs acknowledged by peer
    base: int = 0     # lowest unacked sequence
    last_sent: Dict[int, float] = field(default_factory=dict) # time each packet was last sent
    retries: Dict[int, int] = field(default_factory=dict) 
    last_activity: float = field(default_factory=time.time)
    state: str = "sending"  # "sending", "finished", "cancelled", "error"
    lock: threading.RLock = field(default_factory=threading.RLock) # used to add to dict of transfers

    def __post_init__(self):
        self._generate_chunks()

    def _generate_chunks(self):
        seq = 0
        with open(os.path.join(MEDIA_DOWNLOAD_DIR, self.filepath), "rb") as file:
            while (chunk := file.read(self.chunk_size)):
                self.chunks[seq] = chunk
                seq += 1
        self.total_chunks = seq 
        self.chunks[seq-1] = self.chunks[seq-1].strip()

    def touch(self):
        with self.lock:
            self.last_activity = time.time()

    def mark_acked(self, seq: int):
        # note when peer received packets
        with self.lock:
            self.acks.add(seq)
            while self.base in self.acks:
                self.base += 1
            self.last_activity = time.time()

    def should_retransmit(self, seq: int, now: float, timeout: float, max_retries: int):
        # whether packet should be resent
        # or if it was alr ack'd, sent too recently, or sent too much
        with self.lock:
            if seq in self.acks:
                return False
            last = self.last_sent.get(seq, 0)
            if now - last > timeout:
                if self.retries.get(seq, 0) >= max_retries:
                    return False  # signal too many retries
                return True
            return False


        

def create_inbound(nonce: str, hash: str, filename: Optional[str] = None) -> InboundTransfer:
    # create transfer obj and add to dict
    t = InboundTransfer(nonce=nonce, hash=hash, filename=filename)
    with inbound_lock:
        inbound_transfers[nonce] = t
    return t

def get_inbound(nonce: str) -> Optional[InboundTransfer]:
    # return transfer data for given session
    with inbound_lock:
        return inbound_transfers.get(nonce)

def remove_inbound(nonce: str):
    # remove transfer tracker
    with inbound_lock:
        inbound_transfers.pop(nonce, None)

def create_outbound(nonce: str, filepath: str, hash: str, chunk_size: int = 1200) -> OutboundTransfer:
    t = OutboundTransfer(nonce=nonce, filepath=filepath, hash=hash, chunk_size=chunk_size)
    with outbound_lock:
        outbound_transfers[nonce] = t
    return t

def get_outbound(nonce: str) -> Optional[OutboundTransfer]:
    with outbound_lock:
        return outbound_transfers.get(nonce)

def remove_outbound(nonce: str):
    with outbound_lock:
        outbound_transfers.pop(nonce, None)
