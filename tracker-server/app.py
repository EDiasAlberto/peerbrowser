from fastapi import FastAPI, Request
import redis
from datetime import datetime

app = FastAPI()
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

@app.get("/")
def get_status():
    return {"status": "ok"}

@app.get("/all_trackers")
def get_all_trackers():
    iterator = r.scan_iter(count=10)
    peers = []
    for _ in range(10):
        try:
            peers.append(next(iterator))
        except StopIteration:
            break
    return {"peers": peers}

@app.get("/peers")
def get_peers(filename: str):
    peers = r.smembers(f"file:{filename}")
    return {"filename": filename, "peers": list(peers)}

@app.post("/add")
def add_mapping(request: Request, filename: str):
    ip = request.client.host
    r.sadd(f"file:{filename}", ip)
    r.sadd(f"ip:{ip}", filename)
    r.hset("peer:lastseen", ip, datetime.utcnow().isoformat())
    return {"status": "ok"}

@app.post("/remove")
def remove_mapping(ip: str, filename: str):
    r.srem(f"file:{filename}", ip)
    r.srem(f"ip:{ip}", filename)
    return {"status": "ok"}

@app.post("/peer_offline")
def remove_peer(ip: str):
    files = r.smembers(f"ip:{ip}")
    for f in files:
        r.srem(f"file:{f}", ip)
    r.delete(f"ip:{ip}")
    r.hdel("peer:lastseen", ip)
    return {"status": "removed"}
