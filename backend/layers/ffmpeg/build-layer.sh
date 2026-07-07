#!/bin/bash
# Downloads a pre-built static FFmpeg binary and packages it as a Lambda layer.
# No Docker required. The binary is compiled for x86_64 Linux (Amazon Linux 2023 compatible).
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/layer"
FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

echo "Building FFmpeg Lambda layer (no Docker required)..."

# Clean previous build
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/bin"

# Download static FFmpeg build
echo "  Downloading FFmpeg static binary (~40MB)..."
curl -L --progress-bar "$FFMPEG_URL" -o /tmp/ffmpeg-static.tar.xz

# Extract just ffmpeg and ffprobe
echo "  Extracting binaries..."
tar -xf /tmp/ffmpeg-static.tar.xz -C /tmp
cp /tmp/ffmpeg-*-amd64-static/ffmpeg "$OUTPUT_DIR/bin/ffmpeg"
cp /tmp/ffmpeg-*-amd64-static/ffprobe "$OUTPUT_DIR/bin/ffprobe"
chmod +x "$OUTPUT_DIR/bin/ffmpeg" "$OUTPUT_DIR/bin/ffprobe"

# Cleanup
rm -rf /tmp/ffmpeg-static.tar.xz /tmp/ffmpeg-*-amd64-static

echo "  Layer built at: $OUTPUT_DIR"
echo "  Contents:"
ls -lh "$OUTPUT_DIR/bin/"
