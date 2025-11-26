# RTSP CCTV Odoo 17 Module

Complete CCTV camera management system for Odoo 17 with MediaMTX streaming server integration.

## Features

### Odoo Module
- 📹 Manage unlimited CCTV cameras through Odoo UI
- 🎥 Support for major camera brands (Hikvision, Dahua, Uniview, etc.)
- 🔄 Auto-generation of MediaMTX streaming paths
- 🌐 WebRTC and HLS URL computation
- ⚙️ Per-camera transcoding settings (H.265 → H.264)
- 📊 Kanban, tree, and form views
- 🔌 REST API for external integration

### MediaMTX Streaming
- 🎬 On-demand H.265 to H.264 transcoding via FFmpeg
- ⚡ Low-latency WebRTC streaming (WHEP protocol)
- 📡 HLS fallback support
- 🔧 Custom Docker image with FFmpeg built-in
- 📱 Browser-compatible live viewing

### Sync Service (Optional)
- 🔄 Auto-generates MediaMTX config from Odoo database
- ⏱️ Polls Odoo API every 30 seconds
- 🔁 Dynamic camera addition/removal
- 🐳 Dockerized Python service

## Repository Structure

```
.
├── __init__.py                 # Odoo module init
├── __manifest__.py             # Module manifest
├── models/
│   └── camera.py              # Camera model
├── controllers/
│   └── camera_api.py          # REST API
├── views/
│   ├── camera_views.xml       # UI views
│   └── menu_views.xml         # Menu structure
├── security/
│   └── ir.model.access.csv    # Access rights
├── mediamtx_setup/            # MediaMTX configuration
│   ├── Dockerfile             # Custom image with FFmpeg
│   ├── static-config.yml      # Camera configuration
│   ├── simple-viewer.html     # WebRTC viewer
│   ├── test-player.html       # Advanced player
│   └── README.md              # Setup guide
└── mediamtx_sync/             # Sync service (optional)
    ├── sync_service.py        # Python sync script
    ├── Dockerfile             # Service container
    └── requirements.txt       # Dependencies
```

## Quick Start

### 1. Install Odoo Module

```bash
# Copy to Odoo addons directory
cp -r . /path/to/odoo/addons/cctv_monitoring

# Restart Odoo
docker restart odoo

# In Odoo UI:
# Apps → Update Apps List → Search "CCTV" → Install
```

### 2. Setup MediaMTX

```bash
cd mediamtx_setup

# Build custom image with FFmpeg
docker build -t mediamtx-ffmpeg:latest .

# Edit static-config.yml with your camera details
nano static-config.yml

# Run MediaMTX
docker run -d \
  --name mediamtx \
  --network bridge \
  -p 8554:8554 -p 8889:8889 -p 9997:9997 \
  -v $(pwd)/static-config.yml:/mediamtx.yml:ro \
  mediamtx-ffmpeg:latest \
  /mediamtx.yml
```

### 3. Add Cameras in Odoo

1. Go to **CCTV** → **Cameras** → **Create**
2. Fill in camera details:
   - **Name**: Front Door Camera
   - **RTSP URL**: `rtsp://admin:password@192.168.1.100:554/...`
   - **Brand**: Select your camera brand
   - **Enable Transcoding**: ✓
3. **Save**

### 4. View Live Feed

Open the WebRTC viewer:
```
file:///path/to/mediamtx_setup/simple-viewer.html
```

Or access directly:
```
http://localhost:8889/{camera-path}/whep
```

## Camera URL Examples

### Hikvision
```
rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101
```

### Dahua
```
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
```

### Uniview
```
rtsp://admin:password@192.168.1.100:554/unicast/c1/s0/live
```

See `mediamtx_setup/camera-urls.example` for more formats.

## API Endpoints

### Get All Cameras
```bash
curl http://localhost:8069/api/cctv/cameras
```

Response:
```json
{
  "success": true,
  "cameras": [
    {
      "id": 1,
      "name": "Front Door",
      "mediamtx_path": "front-door",
      "rtsp_url": "rtsp://...",
      "transcoding_enabled": true,
      "target_bitrate": 1000
    }
  ],
  "count": 1
}
```

## Configuration

### Camera Fields

| Field | Description | Example |
|-------|-------------|---------|
| Name | Camera display name | `Front Door Camera` |
| RTSP URL | Full RTSP stream URL | `rtsp://admin:pass@ip:554/path` |
| Brand | Camera manufacturer | `Hikvision` |
| Location | Physical location | `Building A, Floor 1` |
| Enable Transcoding | H.265 → H.264 conversion | `True` |
| Target Bitrate | Transcoding bitrate (kbps) | `1000` |

### Computed Fields

- **MediaMTX Path**: Auto-generated from name (`Front Door Camera` → `front-door-camera`)
- **WebRTC URL**: `http://localhost:8889/{path}/whep`
- **HLS URL**: `http://localhost:8888/{path}/index.m3u8`

## Architecture

```
┌─────────────────┐
│  Odoo UI        │  ← Manage cameras
└────────┬────────┘
         │
         ↓ PostgreSQL
         │
┌────────────────┐
│  MediaMTX      │  ← Stream transcoding
│  + FFmpeg      │     H.265 → H.264
└────────┬───────┘
         │
         ↓ WebRTC/HLS
         │
    Browser 📹
```

## Requirements

- **Odoo**: 17.0
- **Python**: 3.11+
- **Docker**: 20.10+
- **PostgreSQL**: 13+

### MediaMTX Container Requirements
- FFmpeg (included in custom Dockerfile)
- Ports: 8554 (RTSP), 8889 (WebRTC), 9997 (API)

## Troubleshooting

### Module Not Appearing in Odoo
```bash
# Check file permissions
chmod -R 755 /path/to/cctv_monitoring

# Restart Odoo
docker restart odoo

# Update apps list in Odoo UI
```

### Stream Not Playing
```bash
# Check MediaMTX logs
docker logs mediamtx

# Verify FFmpeg is working
docker exec mediamtx ffmpeg -version

# Test RTSP stream
ffprobe rtsp://localhost:8554/camera-path
```

### "FFmpeg not found" Error
Use the custom Dockerfile in `mediamtx_setup/` which includes FFmpeg.

## Development

### Upgrade Module
```bash
# In Odoo container
odoo -u cctv_monitoring -d your_database --stop-after-init

# Or via Odoo UI
# Apps → CCTV Monitoring → Upgrade
```

### Add New Camera Brand
Edit `models/camera.py`:
```python
camera_brand = fields.Selection([
    # ... existing brands
    ('your_brand', 'Your Brand Name'),
])
```

## License

LGPL-3

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/KhanShadman06/rstp-cctv-odoo17-module-/issues

## Credits

Built with Claude Code 🤖

## Changelog

### v1.0.0 (2025-11-26)
- Initial release
- Odoo 17 camera management module
- MediaMTX integration with FFmpeg transcoding
- WebRTC and HLS streaming support
- REST API for camera data
