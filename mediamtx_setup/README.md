# MediaMTX H.265 to H.264 Transcoding Setup

This setup solves the WebRTC codec compatibility issue by transcoding H.265 (HEVC) camera streams to H.264 on-demand.

## The Problem

Your DVR cameras stream H.265 video + MPEG-4 audio, which browsers cannot decode via WebRTC. Even though the WHEP connection succeeds, playback fails with "codecs not supported" error.

## The Solution

MediaMTX with FFmpeg transcoding pipeline:
1. Camera streams H.265 → MediaMTX receives on `camera-X-raw` paths
2. When WebRTC client requests `camera-X`, FFmpeg transcodes to H.264
3. Browser receives compatible H.264 stream and plays successfully

## Setup Instructions

### 1. Update Camera URLs

Edit `mediamtx.yml` and replace the placeholder RTSP URLs with your actual camera credentials:

```yaml
# Line 41 - Camera 1
source: rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101

# Line 73 - Camera 2
source: rtsp://admin:password@192.168.1.101:554/Streaming/Channels/101
```

Replace:
- `admin:password` with your actual DVR username and password
- `192.168.1.100` and `192.168.1.101` with your camera IP addresses
- `/Streaming/Channels/101` with the correct RTSP path for your DVR model

### 2. Start MediaMTX

```bash
cd /home/shadman/docker/mediamtx
docker-compose down  # Stop any old containers
docker-compose up -d  # Start fresh
```

### 3. Verify It's Working

Check the logs:
```bash
docker logs -f mediamtx
```

You should see:
- `INF [RTSP] listener opened on :8554`
- `INF [WebRTC] listener opened on :8889`
- No more `ERR: json: unknown field` errors

### 4. Test Transcoding

Test if FFmpeg transcoding works:
```bash
# This should trigger on-demand transcoding
ffprobe rtsp://localhost:8554/camera-1
```

Look for:
- `Video: h264` (NOT h265/hevc)
- Stream info showing it's transcoding

### 5. Test WebRTC in Browser

Create a simple HTML test file or use a WebRTC player like:
- https://webrtc.github.io/samples/src/content/peerconnection/pc1/

WebRTC WHEP endpoint:
```
http://localhost:8889/camera-1/whep
```

## How to Use in Your Odoo Module

Update your Odoo CCTV module to use these paths:

**For Camera 1:**
- Path: `camera-1` (NOT `camera-1-raw`)
- WebRTC WHEP URL: `http://mediamtx:8889/camera-1/whep`
- Or HLS URL: `http://mediamtx:8888/camera-1/index.m3u8`

**For Camera 2:**
- Path: `camera-2` (NOT `camera-2-raw`)
- WebRTC WHEP URL: `http://mediamtx:8889/camera-2/whep`
- Or HLS URL: `http://mediamtx:8888/camera-2/index.m3u8`

## Architecture

```
DVR Camera (H.265)
       ↓
[camera-X-raw] ← RTSP input path
       ↓
   FFmpeg (runOnDemand) ← Transcodes on first viewer request
       ↓
[camera-X] ← H.264 output path
       ↓
WebRTC WHEP → Browser plays successfully
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker logs mediamtx
```

Common issues:
- Invalid YAML syntax in mediamtx.yml
- Port conflicts (8554, 8889, 8888 already in use)

### Transcoding not working

1. Check if FFmpeg is installed in the container:
```bash
docker exec mediamtx ffmpeg -version
```

2. Test the raw stream:
```bash
ffprobe rtsp://localhost:8554/camera-1-raw
```

3. Check if transcoding starts:
```bash
docker logs -f mediamtx | grep ffmpeg
```

### WebRTC still shows "codecs not supported"

1. Verify you're using `camera-1`, NOT `camera-1-raw`
2. Check browser console for detailed codec errors
3. Verify FFmpeg transcoded to H.264:
```bash
ffprobe rtsp://localhost:8554/camera-1 2>&1 | grep Video
```
Should show: `Video: h264`

### High CPU usage

The current config uses `-preset ultrafast` which prioritizes low latency over compression efficiency. If CPU is too high:

1. Reduce bitrate: Change `-b:v 1000k` to `-b:v 500k`
2. Lower resolution: Add `-s 1280x720` before `-c:v libx264`
3. Use hardware encoding if available: Replace `-c:v libx264` with `-c:v h264_nvenc` (NVIDIA) or `-c:v h264_qsv` (Intel QuickSync)

## Port Reference

| Port | Protocol | Purpose |
|------|----------|---------|
| 8554 | RTSP | Camera input and transcoded output |
| 8889 | HTTP/WebRTC | WebRTC playback (WHEP) |
| 8888 | HTTP/HLS | HLS playback (alternative) |
| 8189 | UDP/TCP | WebRTC ICE candidates |
| 9997 | HTTP | MediaMTX API |

## Adding More Cameras

To add camera-3:

1. Add to mediamtx.yml:
```yaml
  camera-3-raw:
    source: rtsp://admin:password@192.168.1.102:554/Streaming/Channels/101
    sourceProtocol: tcp
    sourceOnDemand: yes

  camera-3:
    runOnDemand: >
      ffmpeg -rtsp_transport tcp
      -i rtsp://localhost:8554/camera-3-raw
      -map 0:v:0 -c:v libx264 -preset ultrafast
      -tune zerolatency -profile:v baseline -level 3.1
      -pix_fmt yuv420p -b:v 1000k -an
      -max_muxing_queue_size 1024 -f rtsp
      rtsp://localhost:8554/$MTX_PATH
    runOnDemandRestart: yes
```

2. Restart mediamtx:
```bash
docker-compose restart
```

## Performance Notes

- **On-Demand Transcoding**: FFmpeg only runs when someone is viewing the stream
- **Auto-Cleanup**: Transcoding stops 10 seconds after the last viewer disconnects
- **First Connection Delay**: Expect 5-15 seconds for FFmpeg to start and stabilize
- **Audio Removed**: The `-an` flag removes audio because your DVR's MPEG-4 audio isn't WebRTC compatible

## Alternative: If You Need Audio

If you need audio and can sacrifice some compatibility:

1. Check what audio codec your camera uses:
```bash
ffprobe rtsp://admin:password@CAMERA_IP:554/...
```

2. If it's AAC, you can transcode audio too. Replace `-an` with:
```
-c:a aac -b:a 64k -ar 48000 -ac 1
```

3. If it's not AAC, transcode it:
```
-c:a libopus -b:a 64k -ar 48000 -ac 1
```

Note: This increases CPU usage significantly.

## Next Steps

1. Update camera URLs in mediamtx.yml
2. Start mediamtx: `docker-compose up -d`
3. Verify logs: `docker logs -f mediamtx`
4. Update your Odoo CCTV module to use `camera-1` and `camera-2` paths
5. Test WebRTC playback in browser

The transcoding should now work, and you'll see `Video: h264` instead of `Video: hevc` when inspecting the streams!
