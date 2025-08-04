#!/bin/bash

# Dependencies check
command -v ffmpeg >/dev/null 2>&1 || { echo >&2 "❌ ffmpeg is not installed. Install it with: sudo apt install ffmpeg"; exit 1; }
command -v v4l2-ctl >/dev/null 2>&1 || { echo >&2 "❌ v4l2-ctl is not installed. Install it with: sudo apt install v4l-utils"; exit 1; }

echo "🔍 Scanning for video capture devices..."

# List available /dev/video* devices
video_devices=()
for dev in /dev/video*; do
    if v4l2-ctl --device="$dev" --all 2>/dev/null | grep -qi "usb\|hdmi"; then
        video_devices+=("$dev")
    fi
done

if [ ${#video_devices[@]} -eq 0 ]; then
    echo "❌ No HDMI-to-USB capture devices found."
    exit 1
fi

# Display device list
echo "🎥 Available HDMI-to-USB capture devices:"
for i in "${!video_devices[@]}"; do
    name=$(v4l2-ctl --device="${video_devices[$i]}" --all | grep "Card type" | cut -d: -f2-)
    echo "  [$i] ${video_devices[$i]} - $name"
done

# Ask user to choose a device
read -p "➡️  Select device index to record from: " index
device="${video_devices[$index]}"

# Set output filename
timestamp=$(date +"%Y%m%d_%H%M%S")
output="capture_$timestamp.mp4"

# Record with ffmpeg
echo "⏺️  Recording from $device to $output"
ffmpeg -f v4l2 -framerate 30 -video_size 1920x1080 -i "$device" -c:v libx264 -preset ultrafast "$output"
