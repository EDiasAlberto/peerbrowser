# PeerBrowser - Decentralized Peer-to-Peer Web Browser

A decentralized web browser implementation that allows users to publish and access websites through peer-to-peer connections, eliminating the need for traditional centralized web hosting.

## 🌐 Overview

PeerBrowser (also known as "Peernet") is a proof-of-concept decentralized web platform where:
- **Users host content** directly from their devices
- **NAT traversal** enables direct peer-to-peer connections
- **Distributed tracking** maintains a registry of available content without centralized storage
- **Content integrity** is verified through MD5 hashing

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PeerBrowser System                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐            ┌──────────────────────────────┐            ┌──────────────────┐
│  Browser Client  │            │    Tracker + Matchmaker      │            │  Browser Client  │
│      (Peer A)    │            │        (Server)              │            │      (Peer B)    │
│                  │            │                              │            │                  │
│  • Flask Web UI  │◄──HTTP────►│  • FastAPI Tracker (8000)    │◄──HTTP────►│  • Flask Web UI  │
│  • UDP P2P       │            │  • Redis Database            │            │  • UDP P2P       │
│  • File Transfer │◄──UDP─────►│  • UDP Matchmaker (12345)    │◄──UDP─────►│  • File Transfer │
│  • NAT Punch     │            │  • NAT Hole Punching         │            │  • NAT Punch     │
└──────────────────┘            └──────────────────────────────┘            └──────────────────┘
        ▲                                                                             ▲
        │                                                                             │
        └─────────────────────────────P2P Connection─────────────────────────────────-┘
                                   (direct UDP transfer)
                                  (after NAT traversal)
```

### Components

#### 1. **Browser Client** (`browser-client/`)
The user-facing application that runs locally on each participant's machine.

**Features:**
- **Web Interface**: Flask-based UI for browsing and publishing content
- **P2P File Transfer**: UDP-based chunked file transfer with integrity verification
- **NAT Traversal**: Automatic hole punching for direct peer connections
- **Content Publishing**: Upload and register local websites to the network

**Key Files:**
- `client.py` - Flask web server and HTTP endpoints
- `holepunch_server.py` - UDP client for P2P connections and NAT traversal
- `transfer_classes.py` - File transfer state management and chunking logic
- `utils.py` - Configuration and utility functions

#### 2. **Tracker Server** (`tracker-server/`)
Centralized coordination server (can be replicated for redundancy).

**Components:**
- **FastAPI Tracker** (Port 8000): HTTP API for peer and file registration
- **UDP Matchmaker** (Port 12345): Rendezvous server for NAT hole punching
- **Redis Database**: Persistent storage for peer-to-file mappings
- **Supervisor**: Process manager running all services in Docker

**Key Files:**
- `app.py` - FastAPI tracker REST API
- `matchmaker.py` - UDP rendezvous server for NAT traversal
- `docker-compose.yml` - Unified Docker deployment
- `Dockerfile` - Multi-service container image

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Docker & Docker Compose** (for server deployment)
- **Port Forwarding**: UDP port for P2P connections (if behind NAT)

### 1. Deploy the Tracker Server

```bash
cd tracker-server
docker-compose up -d
```

This starts:
- FastAPI tracker on port 8000
- UDP matchmaker on port 12345
- Redis database (internal)

### 2. Configure the Browser Client

Create a `.env` file in `browser-client/` directory:

```bash
cd browser-client
cp .env.example .env
```

Edit `.env` with your server details:
```properties
MATCHMAKER_HOST=your-server-ip
MATCHMAKER_PORT=12345
TRACKER_SERVER_URL=http://your-server-ip:8000
```

### 3. Run the Browser Client

**Option A: Using Docker**
```bash
cd browser-client
docker-compose up -d
```

**Option B: Local Development**
```bash
cd browser-client
pip install -r requirements.txt
python3 client.py
```

Access the browser at: `http://localhost:5000`

## 📖 Usage Guide

### Publishing a Website

1. Place your website files in `browser-client/media/{your-site-name}/`
   ```
   browser-client/media/
   └── my-website/
       ├── index.html
       ├── style.css
       └── script.js
   ```

2. Navigate to `http://localhost:5000/publish`

3. Enter your website name (e.g., `my-website`)

4. Click "Publish" to register your files with the tracker

5. Your client will now serve these files to requesting peers

### Browsing a Website

1. Navigate to `http://localhost:5000`

2. Enter the domain/site title (e.g., `my-website`)

3. Optionally specify a page path (default: `index.html`)

4. Click "Fetch Page" to download and view the content

### How It Works

1. **Discovery**: Client queries tracker for peers hosting the requested file
2. **Connection**: Matchmaker facilitates NAT traversal between peers
3. **Transfer**: Direct UDP file transfer with chunking and integrity checks
4. **Validation**: MD5 hash verification ensures content integrity
5. **Rendering**: Downloaded content is saved locally and can be viewed

## 🔧 Configuration

### Browser Client Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MATCHMAKER_HOST` | IP/hostname of matchmaker server | Required |
| `MATCHMAKER_PORT` | UDP port for matchmaker | `12345` |
| `TRACKER_SERVER_URL` | HTTP URL of tracker API | `http://localhost:8000` |

### Tracker Server Configuration

Edit `tracker-server/docker-compose.yml` to customize:
- **Ports**: Change exposed ports for tracker and matchmaker
- **Volumes**: Configure Redis data persistence location
- **Environment**: Add custom environment variables

## 🛠️ Development

### Project Structure

```
peer-browser/
├── browser-client/          # Client application
│   ├── client.py           # Flask web server
│   ├── holepunch_server.py # UDP P2P client
│   ├── transfer_classes.py # File transfer logic
│   ├── utils.py            # Configuration
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # Client container
│   └── media/              # Published content (gitignored)
│
├── tracker-server/         # Server infrastructure
│   ├── app.py             # FastAPI tracker
│   ├── matchmaker.py      # UDP rendezvous server
│   ├── redis.conf         # Redis configuration
│   ├── supervisord.conf   # Process manager config
│   ├── requirements.txt   # Python dependencies
│   ├── Dockerfile         # Multi-service container
│   ├── docker-compose.yml # Deployment configuration
│   └── README.md          # Server documentation
│
└── README.md              # This file
```

### Running Tests

```bash
# Test the tracker API
curl http://localhost:8000/

# Test peer registration
curl -X POST "http://localhost:8000/add?filename=test.html&hash=abc123"

# Query for peers
curl "http://localhost:8000/peers?filename=test.html"
```

### Local Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd browser-client
pip install -r requirements.txt

# Run in development mode
python3 client.py
```

## 🔒 Security Considerations

### Current Implementation
- **Content Integrity**: MD5 hash verification (consider SHA-256 for production)
- **Path Traversal Protection**: Blocks `..` and root access attempts
- **IP Address Validation**: Proper handling of proxy headers

### Recommendations for Production
- [ ] Implement content signing for publisher authentication
- [ ] Add encryption for P2P file transfers (TLS over UDP)
- [ ] Rate limiting on tracker endpoints
- [ ] Peer reputation system to prevent malicious nodes
- [ ] Use stronger hashing algorithms (SHA-256/SHA-3)
- [ ] Implement access control lists for private content

## 🌍 Network Requirements

### Ports
- **Client**: 
  - TCP 5000 (Flask web UI)
  - UDP dynamic (ephemeral port for P2P)
- **Server**:
  - TCP 8000 (Tracker API)
  - UDP 12345 (Matchmaker)

### NAT Traversal
The system uses UDP hole punching for NAT traversal:
1. Clients register with matchmaker to discover their external address
2. When connecting, matchmaker provides peer addresses to both parties
3. Both peers send UDP packets to punch through their respective NATs
4. Direct P2P communication is established

**Note**: Symmetric NAT configurations may prevent successful connections.

## 📊 Protocol Specifications

### Matchmaker Protocol (UDP, JSON)

**Client Registration:**
```json
{"type": "register"}
```

**Connection Request:**
```json
{"type": "connect", "target_ip": "x.x.x.x"}
```

**Server Responses:**
```json
{"type": "your_addr", "addr": ["ip", port]}
{"type": "peer", "peer": ["peer_ip", peer_port]}
{"type": "error", "msg": "description"}
```

### File Transfer Protocol (UDP, JSON)

**Request File:**
```json
{"type": "file_request", "filepath": "site/page.html", "nonce": "12345678"}
```

**File Response:**
```json
{
  "type": "file_response",
  "hash": "md5_hash",
  "data": "hex_encoded_chunk",
  "nonce": "12345678",
  "filename": "site/page.html",
  "is_last": false,
  "seq": 0
}
```

**Acknowledgment:**
```json
{"type": "file_ack", "seq": 0, "nonce": "12345678"}
```

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- **Performance**: Optimize chunking and transfer algorithms
- **Reliability**: Implement retry logic and error recovery
- **Security**: Enhance encryption and authentication
- **Features**: Add content search, caching, and CDN-like distribution
- **UI/UX**: Improve web interface and user experience

## 📄 License

This project is provided as-is for educational and research purposes.

## 🔗 Related Technologies

- **IPFS**: InterPlanetary File System
- **BitTorrent**: Peer-to-peer file sharing protocol
- **WebRTC**: Real-time P2P communication (alternative approach)
- **Freenet**: Anonymous P2P network

## 📞 Support

For issues and questions:
- Check the server logs: `docker-compose logs -f` 
- Review the `tracker-server/README.md` for server-specific documentation
- Ensure proper network configuration and port forwarding

---

**Built with ❤️ for a decentralized web**
