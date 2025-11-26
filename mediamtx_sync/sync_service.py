#!/usr/bin/env python3
"""
MediaMTX Sync Service
=====================

This service automatically generates mediamtx.yml configuration
from cameras defined in Odoo CCTV module using XML-RPC.

It polls the Odoo database and regenerates the config when cameras change.
"""

import xmlrpc.client
import yaml
import time
import hashlib
import logging
import os
import signal
import sys
import subprocess
from datetime import datetime

# Configuration
ODOO_URL = os.getenv('ODOO_URL', 'http://docker-odoo-1:8069')
ODOO_DB = os.getenv('ODOO_DB', 'odoo2')
ODOO_USER = os.getenv('ODOO_USER', 'admin')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD', 'admin')
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


def authenticate_odoo():
    """Authenticate with Odoo and return UID"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})

        if uid:
            logger.info(f"Successfully authenticated with Odoo as user ID: {uid}")
            return uid
        else:
            logger.error("Authentication failed - check credentials")
            return None

    except Exception as e:
        logger.error(f"Error authenticating with Odoo: {e}")
        return None


def get_cameras_from_odoo(uid):
    """Fetch active cameras from Odoo using XML-RPC"""
    try:
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

        # Search for active cameras
        camera_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'cctv.camera', 'search',
            [[['active', '=', True]]]
        )

        if not camera_ids:
            logger.info("No active cameras found in Odoo")
            return []

        # Read camera data
        cameras = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'cctv.camera', 'read',
            [camera_ids],
            {'fields': ['id', 'name', 'mediamtx_path', 'rtsp_url', 'transcoding_enabled', 'target_bitrate']}
        )

        logger.info(f"Retrieved {len(cameras)} cameras from Odoo")
        return cameras

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
    """Trigger MediaMTX container restart to reload configuration"""
    try:
        # Try to restart MediaMTX container via docker socket
        result = subprocess.run(
            ['docker', 'restart', 'mediamtx'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info("✓ MediaMTX container restarted successfully")
            return True
        else:
            logger.warning(f"Failed to restart MediaMTX: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Timeout while restarting MediaMTX")
        return False
    except Exception as e:
        logger.warning(f"Could not restart MediaMTX (this is OK if running without Docker access): {e}")
        logger.info("💡 Please restart MediaMTX manually or mount Docker socket")
        return False


def sync_once(uid):
    """Perform one sync operation"""
    try:
        # Fetch cameras from Odoo
        cameras = get_cameras_from_odoo(uid)

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
                logger.info("✓ MediaMTX config updated successfully")
                # Restart MediaMTX to reload config
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
    logger.info("MediaMTX Sync Service Starting (XML-RPC)")
    logger.info("=" * 60)
    logger.info(f"Odoo URL: {ODOO_URL}")
    logger.info(f"Odoo DB: {ODOO_DB}")
    logger.info(f"Odoo User: {ODOO_USER}")
    logger.info(f"Config Path: {MEDIAMTX_CONFIG_PATH}")
    logger.info(f"Poll Interval: {POLL_INTERVAL}s")
    logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Authenticate with Odoo
    logger.info("Authenticating with Odoo...")
    uid = None
    retry_count = 0
    max_auth_retries = 10

    while retry_count < max_auth_retries and running:
        uid = authenticate_odoo()
        if uid:
            break
        retry_count += 1
        if retry_count < max_auth_retries:
            logger.warning(f"Authentication failed, retrying in 10s ({retry_count}/{max_auth_retries})")
            time.sleep(10)
        else:
            logger.error("Could not authenticate with Odoo after max retries")
            return

    # Initial sync
    logger.info("Performing initial sync...")
    sync_once(uid)

    # Main polling loop
    logger.info(f"Starting polling loop (interval: {POLL_INTERVAL}s)")
    while running:
        try:
            time.sleep(POLL_INTERVAL)
            if running:  # Check again in case we were interrupted during sleep
                sync_once(uid)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            # Try to re-authenticate if needed
            uid = authenticate_odoo()
            time.sleep(5)

    logger.info("Sync service stopped")


if __name__ == '__main__':
    main()
