"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Raw streaming to disk with live downsampled display — PicoScope 6000E

Description:
  Streams full-resolution raw ADC samples to a binary file while simultaneously
  displaying a downsampled live preview in a PyQtGraph plot window.

  The hardware runs in RAW mode: every ADC sample is transferred to the host
  and written to disk. A PC-side stride decimation (every DISPLAY_DOWNSAMPLE-th
  sample) feeds the ring buffer that drives the plot. This is cheaper than
  alternating get_streaming_latest_values() calls for different ratio modes and
  guaranteed to work without undocumented driver behaviour.

  Disk bandwidth requirement: sample_rate_MS/s ≈ MB/s (INT8, 1 byte/sample).
  An NVMe SSD is recommended for rates above ~300 MB/s. The plot adds negligible
  overhead — PyQtGraph updates happen on the main thread via QTimer, decoupled
  from the acquisition and write threads.

  Architecture — three threads plus Qt:
    acquisition_thread : polls hardware; copies full-resolution chunk to the
                         write queue; stride-decimates chunk into ring buffer
    write_thread       : drains the queue and writes chunks to disk
    main thread        : runs the Qt event loop; QTimer fires update_plot()

  Output:
    <OUTPUT_FILE>            — raw binary INT8 samples (load with np.fromfile)
    <OUTPUT_FILE_metadata>   — JSON sidecar: sample rate, dtype, sample count

Key Concepts:
  - Raw mode: RATIO_MODE.RAW, ratio=0 — every ADC sample delivered to host
  - PC-side decimation: chunk[::DISPLAY_DOWNSAMPLE] feeds the plot ring buffer;
    the full chunk is always written to disk unchanged
  - Double buffering: two hardware buffers alternate so data is never lost
  - Producer-consumer: acquisition thread enqueues; write thread flushes to disk
  - Ring buffer: fixed-size circular array for the rolling display window
  - No lock between acquisition and write threads: acquisition owns hardware
    buffers, write thread owns the file, main thread reads monotonic counters
  - data_lock guards the ring buffer shared between acquisition_thread (writer)
    and update_plot() on the main thread (reader)

Performance notes:
  - If [WARNING] Hardware buffer overflow: the acquisition thread is too slow.
    Try reducing POLL_INTERVAL or lowering SAMPLE_INTERVAL_NS.
  - If [QUEUE GROWING]: disk cannot keep up. The queue grows until QUEUE_MAXSIZE,
    then samples are dropped. Lower the ADC rate or use a faster disk.
  - POLL_INTERVAL = 0 (busy-wait) reduces latency at the cost of a full CPU core.
  - DISPLAY_DOWNSAMPLE controls the display resolution. At 312 MS/s, a ratio of
    640 yields ~487 kS/s display rate. Increase the ratio to reduce ring buffer
    fill speed and show a wider time window in the plot.

Requirements:
  - PicoScope 6000E
  - NVMe SSD recommended for rates above ~300 MS/s
  - Python packages: (pip install) numpy pyqtgraph PyQt5 pypicosdk

Setup:
  - Connect a signal to Channel A (or leave open / use the AWG)
  - Close the plot window to end the capture (or Ctrl+C)
"""
import time
import threading
import queue
import json
from datetime import datetime
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
import pypicosdk as psdk


# ============================================================================
# CONFIGURATION
# ============================================================================

# --- Disk capture ---

# Raw mode: no hardware downsampling — every ADC sample is delivered to host
RATIO_MODE = psdk.RATIO_MODE.RAW

# ADC data type for raw mode (8-bit signed integer, range -128 to +127).
# INT8 is essential at high rates: 300 MS/s × 1 byte = 300 MB/s.
ADC_DATA_TYPE = psdk.DATA_TYPE.INT8_T
NUMPY_DTYPE = np.int8

# Requested ADC sample interval in nanoseconds.
# 3.2 ns → ~312 MS/s (hardware rounds to nearest achievable timebase).
SAMPLE_INTERVAL_NS = 400

# Size of each hardware double-buffer registered with the driver.
# At 312 MS/s with 0.5 ms polls: ~156 k samples/poll → 10 M gives ~64× headroom.
SAMPLES_PER_BUFFER = 10_000_000

# How often the acquisition thread polls the hardware (seconds).
# 0 = busy-wait (lower latency, higher CPU). 0.0005 s is a good default.
POLL_INTERVAL = 0.0005

# Desired capture duration in seconds. 0 = run until the plot window is closed.
# If > 0: a software counter stops the capture once the sample target is reached
# (auto_stop=1 is not used — it would fail with PICO_TOO_MANY_SAMPLES for
# captures longer than ~6 s at 312 MS/s due to device onboard memory limits).
CAPTURE_DURATION_S = 0

# Output binary file. A JSON metadata sidecar is written alongside it.
OUTPUT_FILE = "streaming_capture.bin"

# Write queue sizing. Each item is one poll's worth of raw samples.
# If the queue fills, samples are dropped and a warning is printed.
QUEUE_MAXSIZE = 500
QUEUE_WARN_DEPTH = 100

# How often (seconds) the console rate line is printed
RATE_PRINT_INTERVAL = 1.0

# --- Display ---

# Keep every DISPLAY_DOWNSAMPLE-th raw sample for the plot ring buffer.
# At 312 MS/s, ratio 640 → ~487 kS/s display rate, ~4 ms visible window.
# Increase this ratio to show a longer time window at lower display resolution.
DISPLAY_DOWNSAMPLE = 640

# Number of decimated display samples held in the rolling ring buffer.
# Total raw time window shown = RING_BUFFER_SIZE × DISPLAY_DOWNSAMPLE / sample_rate.
RING_BUFFER_SIZE = 2_000

# Plot refresh interval in milliseconds (~30 FPS)
REFRESH_MS = 33


# ============================================================================
# HARDWARE SETUP
# ============================================================================

scope = psdk.ps6000a()
scope.open_unit()
print(f"Connected to PicoScope: {scope.get_unit_serial()}")
print(f"Hardware buffers: {SAMPLES_PER_BUFFER:,} samples each (× 2)")

# Enable Channel A with ±2 V range and DC coupling
scope.set_channel(
    channel=psdk.CHANNEL.A,
    range=psdk.RANGE.V2,
    coupling=psdk.COUPLING.DC
)

# Optionally drive a test signal via the built-in AWG
scope.set_siggen(frequency=1e6, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)


# ============================================================================
# DOUBLE BUFFER SETUP
# ============================================================================

# Two hardware buffers alternate: while the driver fills one, we read the other.
buffer_0 = np.zeros(SAMPLES_PER_BUFFER, dtype=NUMPY_DTYPE)
buffer_1 = np.zeros(SAMPLES_PER_BUFFER, dtype=NUMPY_DTYPE)

scope.set_data_buffer(psdk.CHANNEL.A, 0, action=psdk.ACTION.CLEAR_ALL)
for buf in [buffer_0, buffer_1]:
    scope.set_data_buffer(
        psdk.CHANNEL.A, SAMPLES_PER_BUFFER, buffer=buf,
        action=psdk.ACTION.ADD, datatype=ADC_DATA_TYPE,
        ratio_mode=RATIO_MODE
    )


# ============================================================================
# START STREAMING
# ============================================================================

# Query the actual hardware-achievable interval before starting streaming.
# Channels must be configured first (done above). This lets us pre-compute
# capture_samples (if CAPTURE_DURATION_S > 0) before run_streaming() is called.
_nearest = scope.get_nearest_sampling_interval(SAMPLE_INTERVAL_NS * 1e-9)
sample_rate = 1 / _nearest['actual_sample_interval']
actual_interval_ns = _nearest['actual_sample_interval'] * 1e9
disk_mbps = sample_rate * np.dtype(NUMPY_DTYPE).itemsize / 1e6
capture_samples = int(CAPTURE_DURATION_S * sample_rate) if CAPTURE_DURATION_S > 0 else 0

display_rate = sample_rate / DISPLAY_DOWNSAMPLE
window_ms = RING_BUFFER_SIZE / display_rate * 1e3

print(f"Actual sample interval : {actual_interval_ns:.4g} ns")
print(f"ADC sample rate        : {sample_rate / 1e6:.2f} MS/s")
print(f"Disk write requirement : {disk_mbps:.0f} MB/s  (INT8, 1 byte/sample)")
print(f"Display downsample     : ÷{DISPLAY_DOWNSAMPLE:,}  →  {display_rate:,.0f} S/s")
print(f"Plot window            : {RING_BUFFER_SIZE:,} display samples  ({window_ms:.1f} ms raw time)")
if capture_samples > 0:
    estimated_gb = capture_samples * np.dtype(NUMPY_DTYPE).itemsize / 1e9
    print(f"Capture target         : {capture_samples:,} samples  ({CAPTURE_DURATION_S} s)")
    print(f"Estimated file size    : {estimated_gb:.2f} GB")
print()

# auto_stop=0: driver streams until scope.stop() is called. Device-memory
# validation (which would reject large captures) is skipped. The acquisition
# thread stops by software counter or when the plot window is closed.
actual_interval = scope.run_streaming(
    sample_interval=SAMPLE_INTERVAL_NS,
    time_units=psdk.TIME_UNIT.NS,
    max_pre_trigger_samples=0,
    max_post_trigger_samples=SAMPLES_PER_BUFFER,
    auto_stop=0,
    ratio=0,
    ratio_mode=RATIO_MODE
)


# ============================================================================
# SHARED STATE
# ============================================================================

# Producer-consumer queue: acquisition thread → write thread
write_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

# Cumulative sample counters — written by one thread each.
# Individual Python int reads/writes are GIL-atomic; no lock needed.
total_samples_received = 0   # incremented by acquisition_thread
total_samples_written = 0    # incremented by write_thread

# Flag to signal both threads to stop
stop_streaming = False

# --- Ring buffer (shared between acquisition_thread and update_plot) ---
# float32 for PyQtGraph compatibility; updated under data_lock.
ring_buffer = np.zeros(RING_BUFFER_SIZE, dtype=np.float32)
ring_head = 0       # index where the NEXT display sample will be written
ring_filled = 0     # samples currently in ring (grows to RING_BUFFER_SIZE then clamps)
data_lock = threading.Lock()
data_updated = False

# Rate tracking
rate_start_time = time.perf_counter()
rate_interval_start_time = rate_start_time
rate_interval_start_count = 0


# ============================================================================
# PYQTGRAPH WINDOW SETUP
# ============================================================================

app = pg.mkQApp("PicoScope Streaming to Disk")

win = pg.GraphicsLayoutWidget(title="PicoScope — RAW to disk | downsampled display")
win.resize(1_000, 500)
win.show()

ADC_MIN = int(np.iinfo(NUMPY_DTYPE).min)
ADC_MAX = int(np.iinfo(NUMPY_DTYPE).max)

plot = win.addPlot(
    title=f"Channel A — RAW to disk | ÷{DISPLAY_DOWNSAMPLE:,} display decimation"
)
plot.setLabel('left', 'Amplitude', units='ADC counts')
plot.setLabel('bottom', 'Raw sample index')
plot.showGrid(x=True, y=True)
plot.setYRange(ADC_MIN, ADC_MAX, padding=0.02)
plot.setLimits(yMin=ADC_MIN, yMax=ADC_MAX)
plot.getViewBox().setMouseEnabled(y=False)

# X range: RING_BUFFER_SIZE display points × DISPLAY_DOWNSAMPLE raw samples each
plot.setXRange(0, RING_BUFFER_SIZE * DISPLAY_DOWNSAMPLE, padding=0)

curve = plot.plot(
    pen=None,
    symbol='o',
    symbolSize=3,
    symbolBrush='cyan',
    symbolPen=pg.mkPen(color='cyan', width=1),
    clipToView=True,
    autoDownsample=False
)


# ============================================================================
# ACQUISITION THREAD
# ============================================================================

def acquisition_thread():
    """
    Polls the PicoScope for new raw samples. Each chunk is handled twice:

      1. Full-resolution copy → write_queue for the write thread (disk).
      2. Stride-decimated slice → ring_buffer under data_lock (display).

    The stride decimation (chunk[::DISPLAY_DOWNSAMPLE]) is an O(n/ratio)
    array operation and adds negligible time to each polling cycle.
    """
    global stop_streaming, total_samples_received
    global ring_head, ring_filled, data_updated

    print("Acquisition thread started")
    last_status = None
    current_buffer_index = 0

    while not stop_streaming:
        try:
            info = scope.get_streaming_latest_values(
                channel=psdk.CHANNEL.A,
                ratio_mode=RATIO_MODE,
                data_type=ADC_DATA_TYPE
            )

            last_status = info['status']

            if info['overflowed?']:
                print("[WARNING] Hardware buffer overflow — reduce SAMPLE_INTERVAL_NS "
                      "or decrease POLL_INTERVAL")

            if info['auto stopped?']:
                print("[INFO] Driver auto-stopped streaming")
                stop_streaming = True
                break

            n_samples = info['no of samples']

            if n_samples > 0:
                buffer_index = info['Buffer index'] % 2
                start_index = info.get('start index', 0)
                src = buffer_0 if buffer_index == 0 else buffer_1

                # .copy() releases the hardware buffer back to the driver
                chunk = src[start_index:start_index + n_samples].copy()
                total_samples_received += n_samples

                # Hot-swap: re-register the buffer the driver just vacated so it
                # is ready for the next fill cycle.
                if buffer_index != current_buffer_index:
                    current_buffer_index = buffer_index
                    free_buf = buffer_1 if buffer_index == 0 else buffer_0
                    scope.set_data_buffer(
                        psdk.CHANNEL.A, SAMPLES_PER_BUFFER,
                        buffer=free_buf, action=psdk.ACTION.ADD,
                        datatype=ADC_DATA_TYPE, ratio_mode=RATIO_MODE
                    )

                # 1. Disk: enqueue full-resolution chunk
                try:
                    write_queue.put_nowait(chunk)
                except queue.Full:
                    print(f"[WARNING] Write queue full — disk cannot keep up, "
                          f"{n_samples:,} samples dropped")

                # 2. Display: stride-decimate for the ring buffer.
                # chunk[::DISPLAY_DOWNSAMPLE] keeps every Nth raw sample, giving
                # a faithful (if sparse) preview at a manageable display rate.
                display_chunk = chunk[::DISPLAY_DOWNSAMPLE].astype(np.float32)

                with data_lock:
                    n_ds = len(display_chunk)

                    # If the batch exceeds the ring, only the newest samples matter
                    if n_ds > RING_BUFFER_SIZE:
                        display_chunk = display_chunk[-RING_BUFFER_SIZE:]
                        n_ds = RING_BUFFER_SIZE

                    space_to_end = RING_BUFFER_SIZE - ring_head
                    if n_ds <= space_to_end:
                        ring_buffer[ring_head:ring_head + n_ds] = display_chunk
                    else:
                        ring_buffer[ring_head:] = display_chunk[:space_to_end]
                        ring_buffer[:n_ds - space_to_end] = display_chunk[space_to_end:]

                    ring_head = (ring_head + n_ds) % RING_BUFFER_SIZE
                    ring_filled = min(ring_filled + n_ds, RING_BUFFER_SIZE)
                    data_updated = True

                # Optional software capture counter (used when CAPTURE_DURATION_S > 0)
                if capture_samples > 0 and total_samples_received >= capture_samples:
                    print(f"[INFO] Capture target reached ({total_samples_received:,} samples)")
                    stop_streaming = True
                    break

        except Exception as e:
            print(f"Acquisition error (last_status={last_status}): {e}")
            stop_streaming = True
            break

        if POLL_INTERVAL > 0:
            time.sleep(POLL_INTERVAL)

    print("Acquisition thread stopped")


# ============================================================================
# WRITE THREAD
# ============================================================================

def write_thread_func():
    """
    Drains the write queue and writes each full-resolution chunk to disk.
    Runs until stop_streaming is True AND the queue is fully drained, so no
    in-flight data is lost when the acquisition thread signals a stop.
    """
    global total_samples_written

    print(f"Write thread started → {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'wb') as f:
        while not stop_streaming or not write_queue.empty():
            try:
                chunk = write_queue.get(timeout=0.05)
                # tofile() writes raw bytes without numpy metadata overhead
                chunk.tofile(f)
                total_samples_written += len(chunk)
                write_queue.task_done()
            except queue.Empty:
                continue

    print(f"Write thread stopped  — {total_samples_written:,} samples written to disk")


# ============================================================================
# PLOT UPDATE FUNCTION (runs on main thread via QTimer)
# ============================================================================

def update_plot():
    """
    Called by QTimer on the main thread to refresh the PyQtGraph display.
    Reads the ring buffer in logical order (oldest → newest sample) under
    data_lock. Periodically prints a live rate summary to the console.
    """
    global data_updated, ring_head, ring_filled
    global rate_interval_start_time, rate_interval_start_count

    with data_lock:
        if not data_updated:
            return

        if ring_filled < RING_BUFFER_SIZE:
            # FILLING PHASE: data sits contiguously from 0 to ring_filled.
            y_data = ring_buffer[:ring_filled].copy()
        else:
            # WRAPPED PHASE: oldest sample is at ring_head; concatenate to order.
            y_data = np.concatenate((
                ring_buffer[ring_head:],
                ring_buffer[:ring_head]
            ))

        data_updated = False
        snap_total = total_samples_received   # GIL-atomic read

    if len(y_data) == 0:
        return

    # Position each display point at its true raw ADC sample index.
    # Spacing of DISPLAY_DOWNSAMPLE honestly represents the decimation gap.
    x_data = np.arange(len(y_data), dtype=np.int64) * DISPLAY_DOWNSAMPLE
    curve.setData(x_data, y_data)

    # Periodic rate printout
    now = time.perf_counter()
    interval_elapsed = now - rate_interval_start_time
    if interval_elapsed >= RATE_PRINT_INTERVAL:
        interval_samples = snap_total - rate_interval_start_count
        instant_ms = interval_samples / interval_elapsed / 1e6
        avg_ms = snap_total / (now - rate_start_time) / 1e6 if (now - rate_start_time) > 0 else 0.0
        q_depth = write_queue.qsize()
        q_flag = f"  [QUEUE GROWING: {q_depth}]" if q_depth > QUEUE_WARN_DEPTH else ""
        snap_written = total_samples_written
        print(f"[RATE] {instant_ms:.1f} MS/s  (avg {avg_ms:.1f} MS/s) | "
              f"written: {snap_written:,}  queue: {q_depth}{q_flag}")

        rate_interval_start_time = now
        rate_interval_start_count = snap_total


# ============================================================================
# START THREADS AND QT TIMER
# ============================================================================

acq_thread = threading.Thread(target=acquisition_thread, daemon=True)
w_thread = threading.Thread(target=write_thread_func, daemon=False)

acq_thread.start()
w_thread.start()

timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(REFRESH_MS)

if capture_samples > 0:
    print(f"Streaming {capture_samples:,} samples ({CAPTURE_DURATION_S} s) to disk "
          f"with live display... (close window or Ctrl+C to stop early)\n")
else:
    print("Streaming to disk with live display... Close the plot window or Ctrl+C to stop.\n")


# ============================================================================
# MAIN CAPTURE LOOP (Qt event loop)
# ============================================================================

capture_start = time.perf_counter()

try:
    pg.exec()
except KeyboardInterrupt:
    pass


# ============================================================================
# CLEANUP
# ============================================================================

# Record elapsed before teardown for accurate throughput summary
capture_elapsed = time.perf_counter() - capture_start

timer.stop()
stop_streaming = True
acq_thread.join(timeout=2.0)

# Drain any in-flight chunks before closing the scope — the write thread
# must finish before scope.stop() or the buffer pointers become invalid.
print("Flushing write queue to disk...")
w_thread.join(timeout=60.0)
if w_thread.is_alive():
    print("[WARNING] Write thread did not finish draining — output file may be incomplete")

scope.stop()
scope.close_unit()
print("PicoScope closed.")


# ============================================================================
# POST-CAPTURE SUMMARY AND METADATA
# ============================================================================

actual_disk_mbps = total_samples_written / capture_elapsed / 1e6 if capture_elapsed > 0 else 0

print(f"\n{'─' * 50}")
print(f"Capture duration  : {capture_elapsed:.3f} s")
print(f"Samples received  : {total_samples_received:,}")
print(f"Samples written   : {total_samples_written:,}")
print(f"Avg throughput    : {actual_disk_mbps:.1f} MB/s  (to disk)")
dropped = total_samples_received - total_samples_written
if dropped > 0:
    print(f"[WARNING] Samples dropped (queue overflow): {dropped:,}")
print(f"{'─' * 50}\n")

metadata = {
    "timestamp": datetime.now().isoformat(),
    "channel": "A",
    "ratio_mode": "RAW",
    "display_downsample": DISPLAY_DOWNSAMPLE,
    "sample_interval_ns": actual_interval_ns,
    "sample_rate_hz": sample_rate,
    "dtype": "int8",
    "bytes_per_sample": 1,
    "n_samples": total_samples_written,
    "capture_duration_s": round(capture_elapsed, 6),
    "output_file": OUTPUT_FILE,
    "total_bytes": total_samples_written,
}

metadata_path = OUTPUT_FILE.replace('.bin', '_metadata.json')
with open(metadata_path, 'w') as mf:
    json.dump(metadata, mf, indent=2)

print(f"Binary data   : {OUTPUT_FILE}")
print(f"Metadata      : {metadata_path}")
print()
print("Load with:")
print("  import numpy as np, json")
print(f"  meta = json.load(open('{metadata_path}'))")
print(f"  data = np.fromfile('{OUTPUT_FILE}', dtype=np.int8)")
print("  assert len(data) == meta['n_samples']")
