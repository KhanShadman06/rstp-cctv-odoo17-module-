# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class CameraAPI(http.Controller):

    @http.route('/cctv/api/cameras', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_cameras(self, **kwargs):
        """
        API endpoint to get all active cameras for MediaMTX sync service

        Returns:
            JSON response with list of camera dictionaries
        """
        try:
            # Use sudo() to bypass access rights for API call
            Camera = request.env['cctv.camera'].sudo()
            cameras = Camera.search([('active', '=', True)])

            camera_list = []
            for camera in cameras:
                camera_list.append({
                    'id': camera.id,
                    'name': camera.name,
                    'mediamtx_path': camera.mediamtx_path,
                    'rtsp_url': camera.rtsp_url,
                    'transcoding_enabled': camera.transcoding_enabled,
                    'target_bitrate': camera.target_bitrate,
                })

            _logger.info(f"CCTV API: Returned {len(camera_list)} cameras")

            response_data = {
                'success': True,
                'cameras': camera_list,
                'count': len(camera_list),
            }

            return Response(
                json.dumps(response_data),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            _logger.error(f"CCTV API Error: {str(e)}", exc_info=True)
            error_data = {
                'success': False,
                'error': str(e),
                'cameras': [],
                'count': 0,
            }
            return Response(
                json.dumps(error_data),
                content_type='application/json',
                status=500
            )

    @http.route('/api/cctv/camera/<int:camera_id>', type='json', auth='public', methods=['GET'], csrf=False)
    def get_camera(self, camera_id, **kwargs):
        """Get single camera details"""
        try:
            Camera = request.env['cctv.camera'].sudo()
            camera = Camera.browse(camera_id)

            if not camera.exists():
                return {
                    'success': False,
                    'error': 'Camera not found',
                }

            return {
                'success': True,
                'camera': {
                    'id': camera.id,
                    'name': camera.name,
                    'mediamtx_path': camera.mediamtx_path,
                    'rtsp_url': camera.rtsp_url,
                    'webrtc_url': camera.webrtc_url,
                    'hls_url': camera.hls_url,
                    'transcoding_enabled': camera.transcoding_enabled,
                    'target_bitrate': camera.target_bitrate,
                    'status': camera.status,
                },
            }

        except Exception as e:
            _logger.error(f"Error getting camera {camera_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/api/cctv/webhook/sync', type='http', auth='public', methods=['POST'], csrf=False)
    def webhook_sync(self, **kwargs):
        """
        Webhook endpoint for MediaMTX sync service to trigger config reload
        This can be called when cameras are added/updated/deleted
        """
        try:
            _logger.info("MediaMTX sync webhook triggered")

            # You could add logic here to notify the sync service
            # For now, just acknowledge

            return json.dumps({
                'success': True,
                'message': 'Sync triggered',
            })

        except Exception as e:
            _logger.error(f"Error in sync webhook: {str(e)}")
            return json.dumps({
                'success': False,
                'error': str(e),
            })
