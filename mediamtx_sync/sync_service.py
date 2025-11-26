#!/usr/bin/env python3
"""
MediaMTX Sync Service
=====================

This service automatically generates mediamtx.yml configuration
from cameras defined in Odoo CCTV module.

It polls the Odoo API and regenerates the config when cameras change.
"""

import requests
import yaml
import time
import hashlib
import logging
import os
import signal
import sys
from datetime import datetime

# Configuration
ODOO_URL = os.getenv('ODOO_URL', 'http://docker-odoo-1:8069')
ODOO_DB = os.getenv('ODOO_DB')  # optional database name
MEDIAMTX_CONFIG_PATH = os.getenv('MEDIAMTX_CONFIG_PATH', '/mediamtx/mediamtx.yml')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '30'))  # seconds
MEDIAMTX_API_URL = os.getenv('MEDIAMTX_API_URL', 'http://localhost:9997')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    global running
    logger.info("Shutdown signal received, stopping...")
    running = False


def _build_odoo_url(path: str) -> str:
    """Compose the full Odoo URL including optional db parameter."""
    base = ODOO_URL.rstrip('/')
    url = f"{base}{path}"
    if ODOO_DB:
        separator = '&' if '?' in url else '?'
        url = f"{url}{separator}db={ODOO_DB}"
    return url


def get_cameras_from_odoo():
    """Fetch active cameras from Odoo API"""
    try:
        url = _build_odoo_url('/api/cctv/cameras')
        logger.debug(f"Fetching cameras from {url}")

        response = requests.post(
            url,
            json={},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                cameras = data.get('cameras', [])
                logger.info(f"Retrieved {len(cameras)} cameras from Odoo")
                return cameras
            else:
                logger.error(f"Odoo API error: {data.get('error')}")
                return []
        else:
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            return []

    except requests.exceptions.ConnectionError:
        logger.warning("Cannot connect to Odoo (may not be ready yet)")
        return []
    except Exception as e:
        logger.error(f"Error fetching cameras from Odoo: {e}")
        return []


def generate_mediamtx_config(cameras):
    """Generate MediaMTX configuration from camera list"""

    # Base configuration
    config = {
        'logLevel': 'info',
        'logDestinations': ['stdout'],
        'api': True,
        'apiAddress': ':9997',

        # RTSP
        'rtspAddress': ':8554',
        'rtspsAddress': ':8322',

        # RTMP
        'rtmpAddress': ':1935',
        'rtmpEncryption': 'no',

        # HLS
        'hlsAddress': ':8888',
        'hlsAlwaysRemux': False,
        'hlsVariant': 'lowLatency',
        'hlsSegmentCount': 7,
        'hlsSegmentDuration': '1s',
        'hlsPartDuration': '200ms',

        # WebRTC
        'webrtcAddress': ':8889',
        'webrtcAllowOrigins': ['*'],
        'webrtcLocalUDPAddress': ':8189',
        'webrtcLocalTCPAddress': ':8189',
        'webrtcIPsFromInterfaces': True,
        'webrtcIPsFromInterfacesList': [],
        'webrtcICEServers2': [],

        # Paths
        'paths': {}
    }

    # Add each camera with transcoding
    for camera in cameras:
        camera_name = camera.get('mediamtx_path')
        rtsp_url = camera.get('rtsp_url')
        transcoding = camera.get('transcoding_enabled', True)
        bitrate = camera.get('target_bitrate', 1000)

        if not camera_name or not rtsp_url:
            logger.warning(f"Skipping camera {camera.get('id')} - missing name or URL")
            continue

        # Raw camera path (H.265 input)
        raw_path = f"{camera_name}-raw"
        config['paths'][raw_path] = {
            'source': rtsp_url,
            'rtspTransport': 'tcp',
            'sourceOnDemand': True,
            'sourceOnDemandStartTimeout': '10s',
            'sourceOnDemandCloseAfter': '10s',
        }

        # Transcoded path (H.264 output) - if transcoding is enabled
        if transcoding:
            config['paths'][camera_name] = {
                'runOnDemand': (
                    f'ffmpeg -rtsp_transport tcp '
                    f'-i rtsp://localhost:8554/{raw_path} '
                    f'-map 0:v:0 '
                    f'-c:v libx264 '
                    f'-preset ultrafast '
                    f'-tune zerolatency '
                    f'-profile:v baseline '
                    f'-level 3.1 '
                    f'-pix_fmt yuv420p '
                    f'-b:v {bitrate}k '
                    f'-maxrate {int(bitrate * 1.5)}k '
                    f'-bufsize {int(bitrate * 2)}k '
                    f'-g 30 '
                    f'-keyint_min 30 '
                    f'-sc_threshold 0 '
                    f'-an '
                    f'-max_muxing_queue_size 1024 '
                    f'-f rtsp '
                    f'rtsp://localhost:8554/$MTX_PATH'
                ),
                'runOnDemandRestart': True,
                'runOnDemandStartTimeout': '15s',
                'runOnDemandCloseAfter': '10s',
            }
        else:
            # No transcoding - just proxy the stream
            config['paths'][camera_name] = {
                'source': f'rtsp://localhost:8554/{raw_path}',
                'sourceOnDemand': True,
            }

        logger.info(f"Added camera: {camera_name} (transcoding={'ON' if transcoding else 'OFF'})")

    # Add catch-all for undefined paths
    config['paths']['all_others'] = {
        'sourceOnDemand': False
    }

    return config


def write_config(config, path):
    """Write MediaMTX configuration to file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Write config
        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Configuration written to {path}")
        return True

    except Exception as e:
        logger.error(f"Error writing configuration: {e}")
        return False


def calculate_config_hash(config):
    """Calculate hash of configuration for change detection"""
    config_str = yaml.dump(config, default_flow_style=False, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()


def reload_mediamtx():
    """Signal MediaMTX to reload configuration"""
    try:
        # MediaMTX reloads config automatically when the file changes
        # But we can also call the API to force reload
        url = f"{MEDIAMTX_API_URL}/v3/config/global/patch"
        response = requests.patch(url, json={}, timeout=5)

        if response.status_code in [200, 204]:
            logger.info("MediaMTX configuration reloaded via API")
            return True
        else:
            logger.warning(f"MediaMTX API returned {response.status_code}, relying on auto-reload")
            return False

    except Exception as e:
        logger.debug(f"Could not reload via API (this is OK): {e}")
        logger.info("MediaMTX will auto-reload when it detects config file change")
        return False


def sync_once():
    """Perform one sync operation"""
    try:
        # Fetch cameras from Odoo
        cameras = get_cameras_from_odoo()

        # Generate new config
        new_config = generate_mediamtx_config(cameras)
        new_hash = calculate_config_hash(new_config)

        # Check if config has changed
        try:
            with open(MEDIAMTX_CONFIG_PATH, 'r') as f:
                old_config = yaml.safe_load(f)
                old_hash = calculate_config_hash(old_config)
        except FileNotFoundError:
            old_hash = None
            logger.info("No existing config found, will create new one")

        # Write config if changed
        if new_hash != old_hash:
            logger.info(f"Configuration changed (cameras: {len(cameras)})")
            if write_config(new_config, MEDIAMTX_CONFIG_PATH):
                reload_mediamtx()
                return True
        else:
            logger.debug("Configuration unchanged, skipping write")
            return False

    except Exception as e:
        logger.error(f"Error in sync: {e}")
        return False


def main():
    """Main sync loop"""
    global running

    logger.info("=" * 60)
    logger.info("MediaMTX Sync Service Starting")
    logger.info("=" * 60)
    logger.info(f"Odoo URL: {ODOO_URL}")
    logger.info(f"Odoo DB: {ODOO_DB or '(default)'}")
    logger.info(f"Config Path: {MEDIAMTX_CONFIG_PATH}")
    logger.info(f"Poll Interval: {POLL_INTERVAL}s")
    logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initial sync with retry
    logger.info("Performing initial sync...")
    retry_count = 0
    max_retries = 10

    while retry_count < max_retries and running:
        if sync_once():
            logger.info("Initial sync successful")
            break
        else:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Initial sync failed, retrying in 10s ({retry_count}/{max_retries})")
                time.sleep(10)
            else:
                logger.error("Initial sync failed after max retries, continuing with polling...")

    # Main polling loop
    logger.info(f"Starting polling loop (interval: {POLL_INTERVAL}s)")
    while running:
        try:
            time.sleep(POLL_INTERVAL)
            if running:  # Check again in case we were interrupted during sleep
                sync_once()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(5)  # Brief pause before retrying

    logger.info("Sync service stopped")


if __name__ == '__main__':
    main()
