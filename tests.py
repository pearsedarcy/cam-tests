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

        DURATION=10   # seconds to record
        RES="1920x1080"
        FPS=30
        OUTDIR="./results"
        mkdir -p "$OUTDIR"

        declare -A FORMATS
        FORMATS["mjpeg"]="mjpeg"
        FORMATS["yuyv"]="yuyv422"

        declare -A ENCODERS
        ENCODERS["copy"]="-c:v copy"
        ENCODERS["v4l2m2m"]="-c:v h264_v4l2m2m -b:v 5M"
        ENCODERS["libx264"]="-c:v libx264 -preset ultrafast -crf 23"

        # Detect video devices
        VDEVICES=($(v4l2-ctl --list-devices | grep -A1 'Card' | grep '/dev/video' | awk '{$1=$1};1'))

        for VDEV in "${VDEVICES[@]}"; do
          for FMT in "${!FORMATS[@]}"; do
            for ENC in "${!ENCODERS[@]}"; do
              TS=$(date +%Y%m%d_%H%M%S)
              OUTFILE="${OUTDIR}/$(basename $VDEV)_${FMT}_${ENC}_${TS}.mp4"
              LOGFILE="${OUTDIR}/$(basename $VDEV)_${FMT}_${ENC}_${TS}.log"
              echo "Recording $VDEV at $RES $FPS using ${FORMATS[$FMT]} -> $ENC..."
              ./monitor_metrics.sh "$DURATION" "$LOGFILE" &
              PID=$!
              ffmpeg -f v4l2 -framerate $FPS -video_size $RES -input_format ${FORMATS[$FMT]} -i $VDEV ${ENCODERS[$ENC]} -t $DURATION "$OUTFILE" < /dev/null
              kill $PID
              sleep 2
            done
          done
        done
        echo "All tests completed. Run summarize_results.py for analysis."
    """),

    "monitor_metrics.sh": dedent("""\
        #!/bin/bash
        # Usage: ./monitor_metrics.sh duration output.log

        DURATION=$1
        OUTFILE=$2

        echo "timestamp,cpu_percent,mem_used_mb,disk_write_kbps" > "$OUTFILE"

        END=$((SECONDS+DURATION))
        while [ $SECONDS -lt $END ]; do
          TS=$(date +%s)
          CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}')
          MEM=$(free -m | awk '/Mem:/ {print $3}')
          DISK=$(iostat -d 1 2 | awk '/sda/ {print $3}' | tail -n1)
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

                video_file = log_file.replace(".log", ".mp4")
                size_mb = os.path.getsize(video_file) / (1024 * 1024) if os.path.exists(video_file) else 0

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
    """)
}

# Create the script files
for filename, content in scripts.items():
    file_path = os.path.join(base_path, filename)
    with open(file_path, "w", newline='\n') as f:
        f.write(content)
    print(f"Created: {file_path}")

# Make shell scripts executable (Unix-style permissions)
shell_scripts = ["test_video_capture.sh", "monitor_metrics.sh"]
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
print("- results/ (output directory)")
print("\nTo run the tests, execute: ./test_video_capture.sh")
