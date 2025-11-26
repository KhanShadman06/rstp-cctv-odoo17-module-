#!/bin/bash

# MediaMTX Setup Script
# This script helps you configure and start MediaMTX with H.264 transcoding

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "MediaMTX H.265 to H.264 Transcoding Setup"
echo "=================================================="
echo ""

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Error: docker-compose is not installed"
    exit 1
fi

# Function to check if a camera URL is configured
check_camera_config() {
    if grep -q "rtsp://admin:password@192.168.1." mediamtx.yml; then
        return 1  # Placeholder still exists
    fi
    return 0  # URLs have been updated
}

# Check if camera URLs have been configured
if ! check_camera_config; then
    echo "⚠️  WARNING: Camera URLs are still using placeholder values!"
    echo ""
    echo "Please edit mediamtx.yml and update the following lines:"
    echo "  - Line 41: camera-1-raw source URL"
    echo "  - Line 73: camera-2-raw source URL"
    echo ""
    echo "Replace with your actual:"
    echo "  - DVR IP address"
    echo "  - Username and password"
    echo "  - RTSP path"
    echo ""
    read -p "Have you updated the camera URLs? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Please update the camera URLs in mediamtx.yml first, then run this script again."
        echo "Example:"
        echo "  vi mediamtx.yml"
        echo "or"
        echo "  nano mediamtx.yml"
        exit 1
    fi
fi

echo "✓ Configuration looks good!"
echo ""

# Stop old containers
echo "Stopping old MediaMTX containers..."
docker stop mediamtx mediamtx2 2>/dev/null || true
docker rm mediamtx mediamtx2 2>/dev/null || true

echo "✓ Old containers removed"
echo ""

# Start new container
echo "Starting MediaMTX with transcoding support..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

echo ""
echo "✓ MediaMTX is starting..."
echo ""

# Wait for container to be ready
echo "Waiting for MediaMTX to start (5 seconds)..."
sleep 5

# Check if container is running
if docker ps | grep -q mediamtx; then
    echo "✓ MediaMTX is running!"
else
    echo "❌ Error: MediaMTX failed to start"
    echo ""
    echo "Check logs with:"
    echo "  docker logs mediamtx"
    exit 1
fi

echo ""
echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "📊 View logs:"
echo "  docker logs -f mediamtx"
echo ""
echo "🧪 Test transcoding:"
echo "  ffprobe rtsp://localhost:8554/camera-1"
echo ""
echo "🌐 WebRTC endpoints:"
echo "  Camera 1: http://localhost:8889/camera-1/whep"
echo "  Camera 2: http://localhost:8889/camera-2/whep"
echo ""
echo "📖 Full documentation:"
echo "  cat README.md"
echo ""
echo "=================================================="

# Show last few log lines
echo ""
echo "Recent logs:"
echo "---"
docker logs --tail 20 mediamtx 2>&1
echo ""
