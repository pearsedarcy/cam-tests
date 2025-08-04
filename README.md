# HDMI Capture Test Suite for Raspberry Pi

A comprehensive testing framework for evaluating HDMI capture card performance on Raspberry Pi systems. This suite tests multiple capture devices, input formats, and encoding methods while monitoring system performance metrics.

## 🎯 Purpose

This test suite is designed to:
- Benchmark HDMI capture cards (Cam Link 4K, USB UVC dongles, etc.)
- Compare different capture formats (MJPEG, YUYV)
- Evaluate encoding performance (hardware vs software)
- Monitor system resource usage during capture
- Generate detailed performance reports

## 📋 Requirements

### Hardware
- Raspberry Pi 5 (recommended) or Pi 4
- HDMI capture device(s) (e.g., Elgato Cam Link 4K, generic USB UVC dongles)
- HDMI source (camera, computer, etc.)
- Fast SD card or USB storage (for video output)

### Software Dependencies
```bash
# Required packages
sudo apt update
sudo apt install -y \
    ffmpeg \
    v4l-utils \
    sysstat \
    python3 \
    python3-pip \
    python3-pandas

# Optional: For HTML reports
pip3 install pandas
```

## 📁 Project Structure

```
cam-tests/
├── README.md                    # This file
├── tests.py                     # Test suite generator
├── test_video_capture.sh        # Main test script
├── monitor_metrics.sh           # System monitoring helper
├── summarize_results.py         # Results analysis
├── parallel_tests.py            # Parallel testing version
├── output.py                    # HTML report generator
└── results/                     # Test output directory
    ├── *.mp4                    # Captured video files
    ├── *.log                    # Performance logs
    └── summary_report.html      # HTML report (if generated)
```

## 🚀 Quick Start

### 1. Generate Test Scripts
```bash
# Run the generator to create test scripts
python3 tests.py
```

### 2. Run Basic Tests
```bash
# Make scripts executable (if needed)
chmod +x test_video_capture.sh monitor_metrics.sh

# Run the test suite
./test_video_capture.sh
```

### 3. Analyze Results
```bash
# Generate summary report
python3 summarize_results.py

# Or generate HTML report
python3 output.py
```

## 🔧 Configuration

### Test Parameters

Edit `test_video_capture.sh` to modify test settings:

```bash
DURATION=10          # Recording duration in seconds
RES="1920x1080"      # Video resolution
FPS=30               # Frame rate
OUTDIR="./results"   # Output directory
```

### Supported Formats

The test suite evaluates these input formats:
- **MJPEG**: Compressed format, lower bandwidth
- **YUYV**: Uncompressed format, higher bandwidth

### Encoding Methods

Tests three encoding approaches:
1. **Copy (`-c:v copy`)**: Direct stream copy, minimal CPU usage
2. **Hardware (`h264_v4l2m2m`)**: Hardware-accelerated H.264 encoding
3. **Software (`libx264`)**: Software H.264 encoding with ultrafast preset

## 📊 Test Matrix

For each detected video device, the suite runs:
```
Device × Format × Encoder = Test Combinations
  2    ×   2     ×    3    = 12 tests per run
```

Example test combinations:
- `/dev/video0` + MJPEG + Copy
- `/dev/video0` + MJPEG + Hardware H.264
- `/dev/video0` + MJPEG + Software H.264
- `/dev/video0` + YUYV + Copy
- etc.

## 📈 Monitoring Metrics

Each test captures:
- **CPU Usage**: Percentage utilization during capture
- **Memory Usage**: RAM consumption in MB
- **Disk I/O**: Write speed in KB/s
- **File Size**: Output video file size
- **Timestamps**: For temporal analysis

## 📋 Output Files

### Video Files
- **Naming**: `{device}_{format}_{encoder}_{timestamp}.mp4`
- **Example**: `video0_mjpeg_v4l2m2m_20250804_143022.mp4`

### Log Files
- **Format**: CSV with columns: `timestamp,cpu_percent,mem_used_mb,disk_write_kbps`
- **Example**: `video0_mjpeg_v4l2m2m_20250804_143022.log`

### Summary Report
```
                    test  avg_cpu_percent  max_mem_mb  avg_disk_kbps  video_size_mb
   video0_mjpeg_copy          15.2           1250           5420          125.4
   video0_yuyv_v4l2m2m        28.7           1180           8950           89.2
   video0_mjpeg_libx264       65.4           1420          12300           67.8
```

## 🔄 Advanced Usage

### Parallel Testing

For stress testing multiple devices simultaneously:
```bash
python3 parallel_tests.py
```

This creates `test_video_capture_parallel.sh` which runs all combinations in parallel.

### Custom Test Scenarios

#### Test Specific Device
```bash
# Edit test_video_capture.sh to specify device
VDEVICES=("/dev/video0")  # Test only video0
```

#### Different Resolutions
```bash
# Test multiple resolutions
for RES in "1920x1080" "1280x720" "640x480"; do
    # ... test loop
done
```

#### Extended Duration
```bash
DURATION=60  # 1-minute tests for stability testing
```

## 🛠️ Troubleshooting

### Common Issues

1. **No devices detected**
   ```bash
   # Check available devices
   v4l2-ctl --list-devices
   ls /dev/video*
   ```

2. **Permission errors**
   ```bash
   # Add user to video group
   sudo usermod -a -G video $USER
   # Logout and login again
   ```

3. **FFmpeg errors**
   ```bash
   # Test device capabilities
   ffmpeg -f v4l2 -list_formats all -i /dev/video0
   ```

4. **Missing dependencies**
   ```bash
   # Check if tools are available
   which ffmpeg v4l2-ctl iostat
   ```

### Hardware-Specific Notes

#### Raspberry Pi 5
- Hardware H.264 encoding via `h264_v4l2m2m`
- Best performance with fast SD card (Class 10, U3)
- Consider USB 3.0 storage for high bitrate tests

#### Raspberry Pi 4
- Limited hardware encoding support
- May need to rely on software encoding
- USB 3.0 bandwidth limitations

## 📊 Performance Expectations

### Typical Results (Pi 5 + Cam Link 4K)

| Format | Encoder | CPU % | File Size | Notes |
|--------|---------|-------|-----------|-------|
| MJPEG | Copy | ~15% | 125MB | Best efficiency |
| MJPEG | HW H.264 | ~25% | 89MB | Good balance |
| YUYV | Copy | ~35% | 600MB | Highest quality |
| YUYV | SW H.264 | ~85% | 67MB | CPU intensive |

## 🤝 Contributing

Suggestions for improvements:
- Additional capture formats
- More encoding presets
- Frame drop detection
- Audio capture testing
- Real-time streaming tests

## 📄 License

This project is open source. Feel free to modify and distribute.

## 🔗 Related Resources

- [Raspberry Pi Camera Documentation](https://www.raspberrypi.org/documentation/accessories/camera.html)
- [FFmpeg Video4Linux Documentation](https://ffmpeg.org/ffmpeg-devices.html#video4linux2_002c-v4l2)
- [V4L2 Utils Documentation](https://git.linuxtv.org/v4l-utils.git/)