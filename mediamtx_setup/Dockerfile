FROM alpine:3.19

# Install MediaMTX and FFmpeg
RUN apk add --no-cache wget ffmpeg ca-certificates && \
    wget https://github.com/bluenviron/mediamtx/releases/download/v1.15.4/mediamtx_v1.15.4_linux_amd64.tar.gz && \
    tar -xzf mediamtx_v1.15.4_linux_amd64.tar.gz && \
    mv mediamtx /usr/local/bin/ && \
    rm mediamtx_v1.15.4_linux_amd64.tar.gz && \
    chmod +x /usr/local/bin/mediamtx

EXPOSE 8554 1935 8888 8889 8189/udp 9997

ENTRYPOINT ["/usr/local/bin/mediamtx"]
