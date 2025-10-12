FROM debian:bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip redis-server supervisor && \
    rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency list and install into venv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app and configs
COPY app.py .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY redis.conf /etc/redis/redis.conf

# Persistent Redis data directory
RUN mkdir -p /data && chown redis:redis /data

EXPOSE 8000

# Run both Redis and FastAPI via Supervisor
CMD ["/usr/bin/supervisord"]
