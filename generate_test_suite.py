#!/usr/bin/env python3
"""
Generator script to create a Bash-based test suite for Raspberry Pi HDMI capture testing.
The suite will:
1. Test multiple input devices (Cam Link 4K, USB UVC dongle).
2. Record using raw (YUYV), MJPEG, and hardware-accelerated (h264_v4l2m2m) modes.
3. Log CPU usage, disk write speeds, and resulting file sizes.
4. Provide a summary log for later review.

This script creates:
- test_video_capture.sh  (main test script)
- monitor_metrics.sh     (helper for system usage logging)
- summarize_results.py   (Python summarizer)
- results/               (output logs and videos)
"""

import os
import stat
from textwrap import dedent

# Use current directory instead of hardcoded path
base_path = os.path.dirname(os.path.abspath(__file__))
results_path = os.path.join(base_path, "results")

# Create results directory if it doesn't exist
os.makedirs(results_path, exist_ok=True)

scripts = {
    "test_video_capture.sh": dedent("""\
        #!/bin/bash
        # Automated test suite for Raspberry Pi 5 HDMI ingest

        set -e  # Exit on any error

        DURATION=10   # seconds to record
        RES="1920x1080"
        FPS=30
        OUTDIR="./results"
        mkdir -p "$OUTDIR"

        # Check dependencies
        echo "Checking dependencies..."
        for cmd in ffmpeg v4l2-ctl iostat; do
            if ! command -v "$cmd" &> /dev/null; then
                echo "ERROR: $cmd is not installed. Please install it first."
                echo "Run: sudo apt install ffmpeg v4l-utils sysstat"
                exit 1
            fi
        done

        # Fixed format mappings using actual V4L2 format names
        declare -A FORMATS
        FORMATS["mjpeg"]="MJPG"
        FORMATS["yuyv"]="YUYV"
        FORMATS["nv12"]="NV12"

        # FFmpeg input format mappings
        declare -A FFMPEG_FORMATS
        FFMPEG_FORMATS["MJPG"]="mjpeg"
        FFMPEG_FORMATS["YUYV"]="yuyv422"
        FFMPEG_FORMATS["NV12"]="nv12"

        declare -A ENCODERS
        ENCODERS["copy"]="-c:v copy"
        ENCODERS["v4l2m2m"]="-c:v h264_v4l2m2m -b:v 5M"
        ENCODERS["libx264"]="-c:v libx264 -preset ultrafast -crf 23"

        # Container format based on source format
        declare -A CONTAINERS
        CONTAINERS["MJPG"]="avi"  # MJPEG copy works better with AVI
        CONTAINERS["YUYV"]="mp4"  # YUYV needs encoding for MP4
        CONTAINERS["NV12"]="mp4"

        # Smart device detection - using exact logic from record_hdmi_usb.sh
        echo "Detecting HDMI capture devices..."
        VDEVICES=()
        for dev in /dev/video*; do
            if v4l2-ctl --device="$dev" --all 2>/dev/null | grep -qi "usb\|hdmi"; then
                # Check if device has actual supported formats (filters out duplicate/non-functional devices)
                DEVICE_FORMATS=$(v4l2-ctl -d "$dev" --list-formats-ext 2>/dev/null | grep -oE "'[A-Z0-9]{3,4}'" | tr -d "'" | sort -u)
                
                if [ -n "$DEVICE_FORMATS" ]; then
                    DEVICE_NAME=$(v4l2-ctl --device="$dev" --all 2>/dev/null | grep "Card type" | cut -d: -f2- | xargs || echo "Unknown Device")
                    echo "Found working capture device: $dev - $DEVICE_NAME (formats: $DEVICE_FORMATS)"
                    VDEVICES+=("$dev")
                else
                    DEVICE_NAME=$(v4l2-ctl --device="$dev" --all 2>/dev/null | grep "Card type" | cut -d: -f2- | xargs || echo "Unknown Device")
                    echo "Skipping non-functional device: $dev - $DEVICE_NAME (no supported formats)"
                fi
            fi
        done

        if [ ${#VDEVICES[@]} -eq 0 ]; then
            echo "ERROR: No HDMI capture devices found!"
            echo "Please check:"
            echo "1. HDMI capture device is connected and powered"
            echo "2. Device drivers are loaded (try: lsusb | grep -i video)"
            echo "3. User has permissions: sudo usermod -a -G video $USER"
            echo ""
            echo "Available video devices:"
            ls -la /dev/video* 2>/dev/null || echo "No /dev/video* devices found"
            echo ""
            echo "To debug, try: v4l2-ctl --list-devices"
            exit 1
        fi

        echo "Testing ${#VDEVICES[@]} capture devices: ${VDEVICES[*]}"

        # Test each device's capabilities and show supported formats
        for VDEV in "${VDEVICES[@]}"; do
            DEVICE_NAME=$(v4l2-ctl -d "$VDEV" --info 2>/dev/null | grep "Card type" | cut -d: -f2 | xargs || echo "Unknown Device")
            echo ""
            echo "=== Testing capabilities for $VDEV ($DEVICE_NAME) ==="
            
            if ! v4l2-ctl -d "$VDEV" --list-formats-ext &>/dev/null; then
                echo "WARNING: Cannot access $VDEV, skipping..."
                continue
            fi

            # Get and display supported formats
            SUPPORTED_FORMATS=$(v4l2-ctl -d "$VDEV" --list-formats-ext 2>/dev/null | grep -oE "'[A-Z0-9]{3,4}'" | tr -d "'" | sort -u)
            echo "Supported formats: $SUPPORTED_FORMATS"
            
            # Show detailed format info for first few formats
            echo "Format details:"
            v4l2-ctl -d "$VDEV" --list-formats-ext 2>/dev/null | grep -E "^\\s*\\[[0-9]+\\]:" | head -3
        done

        # Make monitor script executable
        chmod +x ./monitor_metrics.sh 2>/dev/null || true

        TOTAL_TESTS=0
        SUCCESSFUL_TESTS=0

        for VDEV in "${VDEVICES[@]}"; do
            # Skip if device not accessible
            if ! v4l2-ctl -d "$VDEV" --list-formats-ext &>/dev/null; then
                echo "Skipping inaccessible device: $VDEV"
                continue
            fi

            DEVICE_NAME=$(v4l2-ctl -d "$VDEV" --info 2>/dev/null | grep "Card type" | cut -d: -f2 | xargs || echo "Unknown Device")
            echo ""
            echo "========================================="
            echo "Testing device: $VDEV ($DEVICE_NAME)"
            echo "========================================="
            
            # Get actual supported formats for this device
            SUPPORTED_FORMATS=$(v4l2-ctl -d "$VDEV" --list-formats-ext 2>/dev/null | grep -oE "'[A-Z0-9]{3,4}'" | tr -d "'" | sort -u)
            
            if [ -z "$SUPPORTED_FORMATS" ]; then
                echo "  ❌ No supported formats found for $VDEV, skipping..."
                continue
            fi
            
            echo "Device supported formats: $SUPPORTED_FORMATS"
            
            # Quick connectivity test - try to read one frame
            echo "  🔍 Testing device connectivity..."
            if timeout 5 ffmpeg -f v4l2 -i "$VDEV" -frames:v 1 -y /tmp/test_frame_${VDEV##*/}.jpg >/dev/null 2>&1; then
                echo "  ✅ Device is providing video data"
                rm -f /tmp/test_frame_${VDEV##*/}.jpg
            else
                echo "  ⚠️  Device may not be connected or providing video data, but continuing tests..."
            fi
            
            # Test only formats that this device actually supports
            for DEVICE_FORMAT in $SUPPORTED_FORMATS; do
                # Check if we have a test mapping for this format
                TEST_FORMAT=""
                for FMT in "${!FORMATS[@]}"; do
                    if [ "${FORMATS[$FMT]}" = "$DEVICE_FORMAT" ]; then
                        TEST_FORMAT="$FMT"
                        break
                    fi
                done
                
                if [ -z "$TEST_FORMAT" ]; then
                    echo "  Skipping unsupported test format: $DEVICE_FORMAT"
                    continue
                fi
                
                echo "  Testing format: $TEST_FORMAT ($DEVICE_FORMAT)"
                
                for ENC in "${!ENCODERS[@]}"; do
                    TOTAL_TESTS=$((TOTAL_TESTS + 1))
                    TS=$(date +%Y%m%d_%H%M%S)
                    
                    # Choose appropriate container format
                    CONTAINER="${CONTAINERS[$DEVICE_FORMAT]:-mp4}"
                    OUTFILE="${OUTDIR}/$(basename $VDEV)_${TEST_FORMAT}_${ENC}_${TS}.${CONTAINER}"
                    LOGFILE="${OUTDIR}/$(basename $VDEV)_${TEST_FORMAT}_${ENC}_${TS}.log"

                    echo "    [$TOTAL_TESTS] Testing $TEST_FORMAT -> $ENC (${CONTAINER})..."

                    # Start monitoring in background
                    if [ -x "./monitor_metrics.sh" ]; then
                        ./monitor_metrics.sh "$DURATION" "$LOGFILE" &
                        MONITOR_PID=$!
                    else
                        echo "    Warning: monitor_metrics.sh not executable, skipping monitoring"
                        MONITOR_PID=""
                    fi

                    # Use the correct FFmpeg input format
                    FFMPEG_INPUT_FORMAT="${FFMPEG_FORMATS[$DEVICE_FORMAT]:-$DEVICE_FORMAT}"
                    
                    # Skip combinations known to fail
                    if [ "$TEST_FORMAT" = "yuyv" ] && [ "$ENC" = "copy" ]; then
                        echo "    ⏭️  Skipping YUYV copy (raw YUYV not supported in MP4)"
                        [ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null || true
                        continue
                    fi

                    # Run ffmpeg with improved error handling
                    if timeout $((DURATION + 10)) ffmpeg -y -f v4l2 -framerate $FPS -video_size $RES -input_format $FFMPEG_INPUT_FORMAT -i $VDEV ${ENCODERS[$ENC]} -t $DURATION "$OUTFILE" < /dev/null 2>"${OUTFILE}.error.log"; then
                        FILE_SIZE=$(du -h "$OUTFILE" | cut -f1)
                        echo "    ✅ SUCCESS: $OUTFILE created ($FILE_SIZE)"
                        SUCCESSFUL_TESTS=$((SUCCESSFUL_TESTS + 1))
                        # Remove error log if successful
                        rm -f "${OUTFILE}.error.log"
                    else
                        echo "    ❌ FAILED: Check ${OUTFILE}.error.log for details"
                        # Show brief error preview
                        if [ -f "${OUTFILE}.error.log" ]; then
                            echo "    Error preview:"
                            head -3 "${OUTFILE}.error.log" | sed 's/^/      /'
                        fi
                    fi

                    # Stop monitoring
                    [ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null || true

                    sleep 1
                done
            done
        done

        echo ""
        echo "========================================="
        echo "📊 TEST RESULTS SUMMARY"
        echo "========================================="
        echo "Total tests attempted: $TOTAL_TESTS"
        echo "Successful captures: $SUCCESSFUL_TESTS"
        echo "Failed attempts: $((TOTAL_TESTS - SUCCESSFUL_TESTS))"
        if [ $TOTAL_TESTS -gt 0 ]; then
            SUCCESS_RATE=$(( SUCCESSFUL_TESTS * 100 / TOTAL_TESTS ))
            echo "Success rate: ${SUCCESS_RATE}%"
        else
            echo "Success rate: N/A (no tests run)"
        fi
        echo "========================================="
        echo ""
        echo "📁 Results saved to: $OUTDIR"
        if [ $SUCCESSFUL_TESTS -gt 0 ]; then
            echo "✅ Run 'python3 summarize_results.py' for detailed analysis."
            echo "✅ Check individual video files in $OUTDIR"
        else
            echo "❌ No successful captures. Check device connections and permissions."
        fi
    """),

    "monitor_metrics.sh": dedent("""\
        #!/bin/bash
        # Usage: ./monitor_metrics.sh duration output.log

        if [ $# -ne 2 ]; then
            echo "Usage: $0 <duration_seconds> <output_file>"
            exit 1
        fi

        DURATION=$1
        OUTFILE=$2

        # Check if required tools are available
        if ! command -v iostat &> /dev/null; then
            echo "Warning: iostat not found, disk metrics will be 0"
            IOSTAT_AVAILABLE=false
        else
            IOSTAT_AVAILABLE=true
        fi

        echo "timestamp,cpu_percent,mem_used_mb,disk_write_kbps" > "$OUTFILE"

        END=$((SECONDS+DURATION))
        while [ $SECONDS -lt $END ]; do
          TS=$(date +%s)
          
          # Get CPU usage (fallback method if top format differs)
          CPU=$(top -bn1 | grep -E "Cpu\\(s\\)|%Cpu" | head -1 | awk '{for(i=1;i<=NF;i++) if($i ~ /[0-9.]+%.*id/) {sub(/%.*/, "", $i); print 100-$i; break}}' || echo "0")
          
          # Get memory usage
          MEM=$(free -m | awk '/^Mem:/ {print $3}' || echo "0")
          
          # Get disk write speed
          if [ "$IOSTAT_AVAILABLE" = true ]; then
              # Try different iostat formats
              DISK=$(iostat -d 1 2 2>/dev/null | awk 'END {for(i=1;i<=NF;i++) if($i ~ /[0-9.]+/ && $(i-1) ~ /w/) {print $i; exit}} END {print "0"}' || echo "0")
          else
              DISK=0
          fi
          
          # Ensure we have numeric values
          CPU=${CPU:-0}
          MEM=${MEM:-0}
          DISK=${DISK:-0}
          
          echo "$TS,$CPU,$MEM,$DISK" >> "$OUTFILE"
          sleep 1
        done
    """),

    "summarize_results.py": dedent("""\
        #!/usr/bin/env python3
        import os
        import pandas as pd
        from glob import glob

        result_dir = "./results"
        logs = glob(os.path.join(result_dir, "*.log"))

        if not logs:
            print("No log files found in results directory.")
            exit(1)

        summary = []

        for log_file in logs:
            try:
                df = pd.read_csv(log_file)
                avg_cpu = df['cpu_percent'].mean()
                max_mem = df['mem_used_mb'].max()
                avg_disk = df['disk_write_kbps'].mean()

                # Check for both mp4 and avi files
                video_file_mp4 = log_file.replace(".log", ".mp4")
                video_file_avi = log_file.replace(".log", ".avi")
                
                video_file = None
                if os.path.exists(video_file_mp4):
                    video_file = video_file_mp4
                elif os.path.exists(video_file_avi):
                    video_file = video_file_avi
                
                size_mb = os.path.getsize(video_file) / (1024 * 1024) if video_file else 0

                summary.append({
                    "test": os.path.basename(log_file).replace(".log", ""),
                    "avg_cpu_percent": round(avg_cpu, 1),
                    "max_mem_mb": max_mem,
                    "avg_disk_kbps": round(avg_disk, 1),
                    "video_size_mb": round(size_mb, 2)
                })
            except Exception as e:
                print(f"Error processing {log_file}: {e}")

        if summary:
            df_summary = pd.DataFrame(summary)
            df_summary.sort_values("avg_cpu_percent", inplace=True)
            print(df_summary.to_string(index=False))
        else:
            print("No valid data found in log files.")
    """),

    "diagnose.sh": dedent("""\
        #!/bin/bash
        # Diagnostic script for HDMI capture setup

        echo "========================================="
        echo "HDMI Capture Diagnostic Tool"
        echo "========================================="
        echo ""

        # Check system info
        echo "System Information:"
        echo "- OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"')"
        echo "- Kernel: $(uname -r)"
        echo "- Architecture: $(uname -m)"
        echo ""

        # Check dependencies
        echo "Dependencies Check:"
        for cmd in ffmpeg v4l2-ctl iostat; do
            if command -v "$cmd" &> /dev/null; then
                echo "OK $cmd: $(which $cmd)"
            else
                echo "X $cmd: NOT FOUND"
            fi
        done
        echo ""

        # Check video devices
        echo "Video Devices:"
        if ls /dev/video* &>/dev/null; then
            for dev in /dev/video*; do
                if [ -c "$dev" ]; then
                    echo "Found: $dev"
                    if v4l2-ctl -d "$dev" --info &>/dev/null; then
                        echo "  - Driver: $(v4l2-ctl -d "$dev" --info | grep "Driver name" | cut -d: -f2 | xargs)"
                        echo "  - Card: $(v4l2-ctl -d "$dev" --info | grep "Card type" | cut -d: -f2 | xargs)"
                    fi
                fi
            done
        else
            echo "x No video devices found"
        fi
        echo ""

        # Check permissions
        echo "Permissions Check:"
        if groups | grep -q video; then
            echo "OK User is in video group"
        else
            echo "x User NOT in video group - run: sudo usermod -a -G video $$USER"
        fi
        echo ""

        # Check USB devices
        echo "USB Devices (potential capture cards):"
        if command -v lsusb &> /dev/null; then
            lsusb | grep -i -E "(video|capture|cam|elgato|aver|haup)" || echo "No obvious capture devices found"
        else
            echo "lsusb not available"
        fi
        echo ""

        # Test simple capture
        echo "Testing simple capture..."
        if ls /dev/video* &>/dev/null; then
            TESTDEV=$(ls /dev/video* | head -1)
            echo "Testing with $TESTDEV..."
            
            if timeout 3 ffmpeg -f v4l2 -i "$TESTDEV" -frames:v 1 -f null - &>/dev/null; then
                echo "OK Basic capture test PASSED"
            else
                echo "X Basic capture test FAILED"
                echo "Detailed error:"
                timeout 3 ffmpeg -f v4l2 -i "$TESTDEV" -frames:v 1 -f null - 2>&1 | tail -5
            fi
        fi
        echo ""

        echo "========================================="
        echo "If issues persist:"
        echo "1. Reboot and try again"
        echo "2. Check dmesg for USB/device errors"
        echo "3. Try different USB ports"
        echo "4. Update system: sudo apt update && sudo apt upgrade"
        echo "========================================="
    """)
}

# Create the script files
for filename, content in scripts.items():
    file_path = os.path.join(base_path, filename)
    with open(file_path, "w", newline='\n', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {file_path}")

# Make shell scripts executable (Unix-style permissions)
shell_scripts = ["test_video_capture.sh", "monitor_metrics.sh", "diagnose.sh"]
for script in shell_scripts:
    script_path = os.path.join(base_path, script)
    if os.path.exists(script_path):
        # Add execute permissions for owner, group, and others
        current_permissions = os.stat(script_path).st_mode
        os.chmod(script_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Made executable: {script_path}")

print(f"\nTest suite created successfully in: {base_path}")
print("Files created:")
print("- test_video_capture.sh (main test script)")
print("- monitor_metrics.sh (system monitoring)")
print("- summarize_results.py (results analysis)")
print("- diagnose.sh (diagnostic tool)")
print("- results/ (output directory)")
print("\nTo diagnose issues, run: ./diagnose.sh")
print("To run the tests, execute: ./test_video_capture.sh")
