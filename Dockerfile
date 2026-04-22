FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY frp_monitor/ ./frp_monitor/
COPY cli/ ./cli/
COPY frp_monitor/web/static/index.html ./frp_monitor/web/static/

# Environment defaults
ENV FRP_MONITOR_PORT=8400
ENV FRP_MONITOR_HTTP_PORT=8401
ENV FRP_MONITOR_DB_PATH=/data/frp-monitor.db

# Create data directory and set permissions
RUN mkdir -p /data && useradd -u 1000 frp-monitor && chown -R frp-monitor:frp-monitor /data

USER frp-monitor

EXPOSE 8400 8401

# Default to server mode
CMD ["python", "-m", "cli.main", "server", "--port", "8400", "--http-port", "8401", "--db", "/data/frp-monitor.db"]
