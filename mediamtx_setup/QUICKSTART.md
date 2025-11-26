# Quick Start Guide

## TL;DR

Your H.265 camera streams can't play in browsers via WebRTC. This setup transcodes them to H.264 automatically using FFmpeg.

## 3 Steps to Get Working

### 1. Update Camera URLs

Edit `mediamtx.yml` lines 41 and 73:

```bash
nano mediamtx.yml
```

Change:
```yaml
source: rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101
```

To your actual camera IP, username, password, and RTSP path.

### 2. Start MediaMTX

```bash
./setup.sh
```

Or manually:
```bash
docker-compose down
docker-compose up -d
docker logs -f mediamtx
```

### 3. Test It

Open in browser:
```bash
file:///home/shadman/docker/mediamtx/test-player.html
```

Or test with ffprobe:
```bash
ffprobe rtsp://localhost:8554/camera-1 2>&1 | grep Video
```

Should show: `Video: h264` (not hevc/h265)

## What Changed?

**Before:**
- DVR → H.265 → MediaMTX → WebRTC → ❌ Browser can't decode

**After:**
- DVR → H.265 → MediaMTX → **FFmpeg transcodes** → H.264 → WebRTC → ✅ Browser plays

## For Your Odoo Module

Use these paths in your CCTV module:

```python
# Camera 1
webrtc_url = "http://mediamtx:8889/camera-1/whep"

# Camera 2
webrtc_url = "http://mediamtx:8889/camera-2/whep"
```

**Important:** Use `camera-1`, NOT `camera-1-raw`!

## Troubleshooting One-Liners

```bash
# Is mediamtx running?
docker ps | grep mediamtx

# Any errors?
docker logs mediamtx 2>&1 | grep ERR

# Is it transcoding to H.264?
ffprobe rtsp://localhost:8554/camera-1 2>&1 | grep -i codec

# Check if FFmpeg starts when you connect
docker logs -f mediamtx | grep ffmpeg

# Test camera connection directly
ffplay rtsp://admin:password@YOUR_CAMERA_IP:554/your/path
```

## Common Issues

### "ERR: json: unknown field"
- Fixed! The old config had `gstreamerProgram` which doesn't exist
- New config uses `runOnDemand` which is the correct field

### "Codecs not supported"
- You're connecting to `camera-1-raw` instead of `camera-1`
- Or FFmpeg isn't installed in the container
- Or transcoding failed (check logs)

### Takes forever to start
- Normal! First connection takes 5-15 seconds
- FFmpeg needs to start and stabilize the stream
- Subsequent connections are faster

### High CPU usage
- FFmpeg transcoding uses CPU
- To reduce: lower bitrate in mediamtx.yml (change `-b:v 1000k` to `-b:v 500k`)
- Or use hardware encoding (see README.md)

## What the Files Do

| File | Purpose |
|------|---------|
| mediamtx.yml | Main config with transcoding setup |
| docker-compose.yml | Runs the mediamtx container |
| setup.sh | Automated setup script |
| test-player.html | WebRTC test player |
| README.md | Full documentation |
| QUICKSTART.md | This file |

## Need More Help?

Read the full README.md for:
- Detailed troubleshooting
- Adding more cameras
- Audio configuration
- Hardware encoding
- Performance tuning

## Still Not Working?

MediaMTX might not be the right tool if:
1. Your DVR has proprietary protocols (not standard RTSP)
2. You need very low latency (<100ms)
3. You need audio and your codec is weird
4. CPU is too limited for transcoding

**Alternative solutions:**
1. Check if your DVR has H.264 profiles (substream/mainstream)
2. Use HLS instead of WebRTC (higher latency but works)
3. Use a hardware transcoder (e.g., NVIDIA GPU)
4. Consider different software (go2rtc, Frigate, etc.)

But try this first! It should work for standard RTSP H.265 cameras.
