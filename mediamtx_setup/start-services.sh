#!/bin/bash

set -e

echo "Starting MediaMTX Dynamic CCTV Services..."
echo ""

# Start sync service first
echo "1. Starting MediaMTX Sync Service..."
docker compose up -d mediamtx-sync

# Wait for sync to create initial config
echo "2. Waiting for sync service to generate config (15 seconds)..."
sleep 15

# Check if config exists
if docker exec mediamtx-sync test -f /mediamtx/mediamtx.yml; then
    echo "✓ Config file generated successfully"
else
    echo "✗ Config file not found, waiting more..."
    sleep 10
fi

# Start MediaMTX manually (avoiding docker-compose command parsing issues)
echo "3. Starting MediaMTX server..."
docker run -d \
  --name mediamtx \
  --network docker_default \
  --restart unless-stopped \
  -p 8554:8554 -p 8554:8554/udp \
  -p 1935:1935 \
  -p 8888:8888 \
  -p 8889:8889 \
  -p 8189:8189/udp -p 8189:8189/tcp \
  -p 9997:9997 \
  -v mediamtx_shared-config:/config:ro \
  bluenviron/mediamtx:latest \
  /config/mediamtx.yml

echo ""
echo "4. Waiting for MediaMTX to start..."
sleep 5

# Check if services are running
echo ""
echo "Service Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "mediamtx|NAMES"

echo ""
echo "✓ Services started successfully!"
echo ""
echo "Next steps:"
echo "1. Install Odoo module: http://localhost:8069"
echo "   - Apps → Update Apps List → Install 'CCTV Monitoring'"
echo ""
echo "2. Add cameras:"
echo "   - CCTV → Cameras → Create"
echo ""
echo "3. Watch logs:"
echo "   docker logs -f mediamtx-sync"
echo "   docker logs -f mediamtx"
echo ""
