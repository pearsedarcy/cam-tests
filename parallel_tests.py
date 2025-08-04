# We'll update the `test_video_capture.sh` to include parallel recording support.
# Each combination of (device x format x encoder) will run in the background, and logs/results will be saved per job.

parallel_test_script = dedent("""\
    #!/bin/bash
    # Parallel version: test multiple devices simultaneously

    DURATION=10   # seconds
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

    PIDS=()

    for VDEV in "${VDEVICES[@]}"; do
      for FMT in "${!FORMATS[@]}"; do
        for ENC in "${!ENCODERS[@]}"; do
          TS=$(date +%Y%m%d_%H%M%S)
          OUTFILE="${OUTDIR}/$(basename $VDEV)_${FMT}_${ENC}_${TS}.mp4"
          LOGFILE="${OUTDIR}/$(basename $VDEV)_${FMT}_${ENC}_${TS}.log"
          echo "Starting background job for $VDEV at $RES $FPS using ${FORMATS[$FMT]} -> $ENC"
          ./monitor_metrics.sh "$DURATION" "$LOGFILE" &
          MPID=$!
          ffmpeg -f v4l2 -framerate $FPS -video_size $RES -input_format ${FORMATS[$FMT]} -i $VDEV ${ENCODERS[$ENC]} -t $DURATION "$OUTFILE" < /dev/null &
          FPID=$!
          PIDS+=($MPID $FPID)
          sleep 1  # small delay between starts
        done
      done
    done

    # Wait for all jobs to finish
    for pid in "${PIDS[@]}"; do
      wait $pid
    done

    echo "All parallel tests completed. Run summarize_results.py for analysis."
""")

with open("/mnt/data/pi_video_test_suite/test_video_capture_parallel.sh", "w") as f:
    f.write(parallel_test_script)

os.chmod("/mnt/data/pi_video_test_suite/test_video_capture_parallel.sh", 0o755)
