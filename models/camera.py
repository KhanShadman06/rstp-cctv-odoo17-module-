# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)


class CCTVCamera(models.Model):
    _name = 'cctv.camera'
    _description = 'CCTV Camera'
    _order = 'name'

    name = fields.Char(string='Camera Name', required=True, help='Friendly name for the camera')
    active = fields.Boolean(string='Active', default=True)

    # Connection Details
    rtsp_url = fields.Char(
        string='RTSP URL',
        required=True,
        help='Full RTSP URL: rtsp://username:password@ip:port/path'
    )
    ip_address = fields.Char(string='IP Address', compute='_compute_ip_from_url', store=True)
    port = fields.Integer(string='Port', default=554)
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    rtsp_path = fields.Char(string='RTSP Path', help='Path after IP:port, e.g., /Streaming/Channels/101')

    # Camera Type
    camera_brand = fields.Selection([
        ('hikvision', 'Hikvision'),
        ('dahua', 'Dahua'),
        ('uniview', 'Uniview'),
        ('amcrest', 'Amcrest'),
        ('reolink', 'Reolink'),
        ('tplink', 'TP-Link'),
        ('foscam', 'Foscam'),
        ('onvif', 'Generic ONVIF'),
        ('other', 'Other'),
    ], string='Camera Brand', default='hikvision')

    # Streaming Settings
    stream_quality = fields.Selection([
        ('main', 'Main Stream (High Quality)'),
        ('sub', 'Sub Stream (Low Quality)'),
    ], string='Stream Quality', default='main', help='Main stream for recording, sub stream for live viewing')

    transcoding_enabled = fields.Boolean(
        string='Enable Transcoding',
        default=True,
        help='Transcode H.265 to H.264 for browser compatibility'
    )

    target_bitrate = fields.Integer(
        string='Target Bitrate (kbps)',
        default=1000,
        help='Target bitrate for transcoding (e.g., 500, 1000, 2000)'
    )

    # MediaMTX Integration
    mediamtx_path = fields.Char(
        string='MediaMTX Path',
        compute='_compute_mediamtx_path',
        store=True,
        help='Path identifier in MediaMTX'
    )

    webrtc_url = fields.Char(
        string='WebRTC URL',
        compute='_compute_webrtc_url',
        help='WebRTC WHEP endpoint for browser playback'
    )

    hls_url = fields.Char(
        string='HLS URL',
        compute='_compute_hls_url',
        help='HLS playlist URL for fallback playback'
    )

    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ], string='Status', default='draft', help='Camera connection status')

    last_check = fields.Datetime(string='Last Status Check', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)

    # Metadata
    location = fields.Char(string='Location', help='Physical location of the camera')
    notes = fields.Text(string='Notes')

    @api.depends('rtsp_url')
    def _compute_ip_from_url(self):
        """Extract IP address from RTSP URL"""
        for camera in self:
            if camera.rtsp_url:
                # Parse RTSP URL: rtsp://user:pass@192.168.1.100:554/path
                match = re.search(r'@([\d\.]+):', camera.rtsp_url)
                if match:
                    camera.ip_address = match.group(1)
                else:
                    # Try without credentials: rtsp://192.168.1.100:554/path
                    match = re.search(r'rtsp://([^:/]+)', camera.rtsp_url)
                    camera.ip_address = match.group(1) if match else False
            else:
                camera.ip_address = False

    @api.depends('name')
    def _compute_mediamtx_path(self):
        """Generate MediaMTX path from camera name"""
        for camera in self:
            if camera.name:
                # Create URL-safe path: "Camera 1" -> "camera-1"
                safe_name = re.sub(r'[^a-zA-Z0-9]+', '-', camera.name.lower()).strip('-')
                camera.mediamtx_path = safe_name
            else:
                camera.mediamtx_path = False

    @api.depends('mediamtx_path')
    def _compute_webrtc_url(self):
        """Generate WebRTC WHEP endpoint URL"""
        for camera in self:
            if camera.mediamtx_path:
                # Use localhost for browser access
                camera.webrtc_url = f"http://localhost:8889/{camera.mediamtx_path}/whep"
            else:
                camera.webrtc_url = False

    @api.depends('mediamtx_path')
    def _compute_hls_url(self):
        """Generate HLS playlist URL"""
        for camera in self:
            if camera.mediamtx_path:
                camera.hls_url = f"http://localhost:8888/{camera.mediamtx_path}/index.m3u8"
            else:
                camera.hls_url = False

    @api.constrains('rtsp_url')
    def _check_rtsp_url(self):
        """Validate RTSP URL format"""
        for camera in self:
            if camera.rtsp_url and not camera.rtsp_url.startswith('rtsp://'):
                raise ValidationError('RTSP URL must start with rtsp://')

    @api.constrains('target_bitrate')
    def _check_bitrate(self):
        """Validate bitrate range"""
        for camera in self:
            if camera.target_bitrate and (camera.target_bitrate < 100 or camera.target_bitrate > 10000):
                raise ValidationError('Target bitrate must be between 100 and 10000 kbps')

    def action_test_connection(self):
        """Test camera connection (can be called from UI button)"""
        self.ensure_one()
        # This would typically use ffprobe or similar to test the connection
        # For now, we'll just log it
        _logger.info(f"Testing connection to camera: {self.name} ({self.rtsp_url})")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Connection Test',
                'message': f'Testing connection to {self.name}...',
                'type': 'info',
                'sticky': False,
            }
        }

    def action_trigger_mediamtx_sync(self):
        """Trigger MediaMTX configuration sync"""
        _logger.info("Triggering MediaMTX sync for all cameras")

        # This will be called by the sync service
        # For now, just notify
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'MediaMTX Sync',
                'message': 'MediaMTX configuration will be updated',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_live_feed(self):
        """Open live feed in new window"""
        self.ensure_one()

        if not self.mediamtx_path:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Stream Available',
                    'message': 'Please save the camera first and wait for sync (30 seconds)',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Open viewer with camera path pre-filled
        viewer_url = f"file:///home/shadman/docker/mediamtx/simple-viewer.html?camera={self.mediamtx_path}"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Open Camera Viewer',
                'message': f'Copy this URL and open in browser:\nfile:///home/shadman/docker/mediamtx/simple-viewer.html\n\nCamera path: {self.mediamtx_path}',
                'type': 'info',
                'sticky': True,
            }
        }

    @api.model
    def get_cameras_for_mediamtx(self):
        """API method to get all active cameras for MediaMTX config generation"""
        cameras = self.search([('active', '=', True)])
        result = []

        for camera in cameras:
            result.append({
                'id': camera.id,
                'name': camera.name,
                'mediamtx_path': camera.mediamtx_path,
                'rtsp_url': camera.rtsp_url,
                'transcoding_enabled': camera.transcoding_enabled,
                'target_bitrate': camera.target_bitrate,
            })

        return result
