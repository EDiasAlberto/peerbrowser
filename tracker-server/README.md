# Tracker Server (with Integrated Matchmaker)

This directory contains the unified server infrastructure for the peer-browser project, combining both the tracker server and matchmaker service.

## Components

### 1. FastAPI Tracker Server (`app.py`)
- **Port**: 8000 (HTTP)
- **Purpose**: Maintains a Redis-backed registry of peers and files
- **Endpoints**:
  - `GET /` - Health check
  - `GET /peers?filename={filename}` - Get peers hosting a file
  - `POST /add?filename={filename}&hash={hash}` - Register a file
  - `POST /remove` - Remove a file mapping
  - `POST /peer_offline` - Remove a peer from all registries
  - `GET /all_trackers` - List tracked files

### 2. UDP Matchmaker Server (`matchmaker.py`)
- **Port**: 12345 (UDP)
- **Purpose**: NAT hole-punching rendezvous server for P2P connections
- **Protocol**: JSON over UDP
  - Client sends `{"type": "register"}` to register with server
  - Client sends `{"type": "connect", "target_ip": "x.x.x.x"}` to connect to peer
  - Server responds with peer addresses to facilitate direct P2P connection

### 3. Redis Database
- **Port**: 6379 (internal only)
- **Purpose**: Persistent storage for peer and file mappings
- **Data directory**: `/data` (mounted as volume)

## Docker Setup

The entire stack runs in a single Docker container managed by Supervisor:

```yaml
services:
  tracker:
    build: .
    container_name: p2p-tracker
    ports:
      - "8000:8000"              # FastAPI tracker HTTP
      - "12345:12345/udp"        # Matchmaker UDP for NAT hole punching
    volumes:
      - redis-data:/data         # Persistent Redis storage
      - .:/app                   # Mount code (optional)
    restart: always
```

## Running the Server

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis
redis-server redis.conf &

# Start FastAPI tracker
uvicorn app:app --host 0.0.0.0 --port 8000 &

# Start matchmaker
python3 matchmaker.py --host 0.0.0.0 --port 12345 &
```

## Architecture Notes

### IP Address Handling
The tracker server correctly handles client IP addresses behind proxies/load balancers:
1. Checks `cf-connecting-ip` header (Cloudflare)
2. Falls back to `x-forwarded-for` header
3. Falls back to direct client IP

This ensures accurate peer registration regardless of network topology.

### UDP Packet Handling
The matchmaker uses:
- **Thread-safe packet queue** for handling concurrent requests
- **Background cleanup thread** to remove stale client registrations
- **1MB receive buffer** to handle burst traffic
- **Client timeout**: 120 seconds without re-registration

The UDP socket is bound to `0.0.0.0` to accept packets from any interface, preserving the observed client address for accurate NAT traversal.

## Monitoring

Supervisor logs are available at:
- `/var/log/supervisor/supervisord.log` (inside container)
- `docker-compose logs tracker` (from host)

Individual service logs:
- Redis: Managed by supervisor
- FastAPI: stdout/stderr via supervisor
- Matchmaker: stdout/stderr via supervisor

## Data Persistence

Redis data persists across container restarts via:
- RDB snapshots (triggered by save rules in `redis.conf`)
- AOF (Append-Only File) for durability
- Docker volume `redis-data` mounted to `/data`
