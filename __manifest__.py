# -*- coding: utf-8 -*-
{
    'name': 'CCTV Monitoring',
    'version': '17.0.1.0.0',
    'category': 'Operations',
    'summary': 'Manage CCTV cameras with WebRTC streaming via MediaMTX',
    'description': """
        CCTV Camera Monitoring System
        ==============================

        Features:
        ---------
        * Manage multiple CCTV cameras
        * Support for various camera brands (Hikvision, Dahua, Uniview, etc.)
        * WebRTC live streaming via MediaMTX
        * Automatic H.265 to H.264 transcoding
        * RESTful API for MediaMTX integration
        * Real-time camera status monitoring
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/camera_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
