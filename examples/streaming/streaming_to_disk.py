"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

High-throughput raw streaming to disk — PicoScope 6000E

Description:
  Streams raw ADC samples continuously to a binary file without any plotting.
  Designed to sustain >300 MS/s (300 MB/s at INT8), though the achievable rate
  depends on hardware and disk speed.

  Disk bandwidth requirement: sample_rate_MS/s ≈ MB/s required (INT8, 1 byte/sample).
  An NVMe SSD is recommended for rates above ~500 MB/s. SATA SSDs (~500 MB/s) cover
  most use cases. HDDs (~150 MB/s) are not viable above ~150 MS/s.

  Architecture — three threads:
    acquisition_thread : polls hardware every POLL_INTERVAL, copies new samples
                         into a queue
    write_thread       : drains the queue and writes chunks to disk
    main thread        : duration timer, live rate printout, Ctrl+C handler

  Compared with the plotting examples, there is no ring buffer. The ring buffer
  exists only to feed the display window; without a plot it is not needed. Data
  flows directly: hardware buffer → queue → disk.

  Output:
    <OUTPUT_FILE>           — raw binary INT8 samples (load with np.fromfile)
    <OUTPUT_FILE_metadata>  — JSON sidecar with sample rate, dtype, sample count

Key Concepts:
  - Raw mode: RATIO_MODE.RAW, ratio=0 — every ADC sample delivered to host
  - INT8 data: 8-bit signed integers (-128 to +127), 1 byte per sample
  - Double buffering: two hardware buffers alternate so data is never lost
  - Producer-consumer: acquisition thread enqueues; write thread flushes to disk
  - No lock needed: acquisition thread owns hardware buffers; write thread owns
    the file; main thread only reads monotonic counters
  - Capture length is set by CAPTURE_DURATION_S (seconds). After run_streaming()
    returns the actual hardware-rounded sample interval, the exact sample target
    is computed and the acquisition thread stops itself once that count is reached.
    Set CAPTURE_DURATION_S = 0 to run until Ctrl+C.

Performance notes:
  - If [WARNING] Hardware buffer overflow: the acquisition thread is too slow.
    Try reducing POLL_INTERVAL or lowering SAMPLE_INTERVAL_NS (slower ADC rate).
  - If [QUEUE GROWING]: the write thread cannot keep up with ingest. The queue
    will grow until it hits QUEUE_MAXSIZE, then samples are dropped.
  - POLL_INTERVAL = 0 (busy-wait) may reduce latency but pegs a CPU core.

Requirements:
  - PicoScope 6000E
  - NVMe SSD (recommended for >300 MS/s)
  - Python packages: (pip install) numpy pypicosdk

Setup:
  - Connect a signal to Channel A (or leave open for noise / use AWG)
"""
import time
import threading
import queue
import json
from datetime import datetime
import numpy as np
import pypicosdk as psdk


# ============================================================================
# CONFIGURATION
# ============================================================================

# Raw mode: no hardware downsampling — every ADC sample is delivered to host
RATIO_MODE = psdk.RATIO_MODE.RAW

# ADC data type for raw mode (8-bit signed integer, range -128 to +127).
# INT8 is essential at high rates: 300 MS/s × 1 byte = 300 MB/s.
# Switching to INT16 would double the disk bandwidth requirement.
ADC_DATA_TYPE = psdk.DATA_TYPE.INT8_T
NUMPY_DTYPE = np.int8

# Requested ADC sample interval in nanoseconds.
# 4 ns → ~250 MS/s (hardware rounds to nearest achievable timebase).
# The actual interval is printed at startup.
SAMPLE_INTERVAL_NS = 3.2

# Size of each hardware double-buffer registered with the driver.
# Must hold comfortably more samples than arrive between consecutive polls.
# At 300 MS/s with a 0.5 ms poll: ~150,000 samples per poll → 10 M gives ~67× headroom.
SAMPLES_PER_BUFFER = 10_000_000

# How often the acquisition thread polls the hardware for new data (seconds).
# 0.5 ms is aggressive but safe — the hardware buffers absorb any jitter.
# Set to 0 for a busy-wait loop (lower latency, higher CPU usage).
POLL_INTERVAL = 0.0005

# Desired capture duration in seconds. The exact sample target is calculated
# from the actual hardware sample rate after run_streaming() returns, so the
# capture length is accurate regardless of hardware rounding of the interval.
# Set to 0 to run until Ctrl+C.
CAPTURE_DURATION_S = 4

# Output binary file path. A JSON metadata sidecar is written alongside it.
OUTPUT_FILE = "streaming_capture.bin"

# Write queue sizing. Each item is one poll's worth of samples (~150 k at 300 MS/s).
# If the queue fills, samples are dropped and a warning is printed.
QUEUE_MAXSIZE = 500

# Print a warning in the rate line if the queue exceeds this depth.
QUEUE_WARN_DEPTH = 100

# How often (seconds) the console rate line is printed
RATE_PRINT_INTERVAL = 1.0


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

# Clear any previously registered buffers, then register both
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
# Channels must be configured first (done above) as the number of active
# channels affects which timebases are available.
# This lets us compute capture_samples and pass it into run_streaming() so the
# hardware stops automatically — no software timer or second streaming call needed.
_nearest = scope.get_nearest_sampling_interval(SAMPLE_INTERVAL_NS * 1e-9)
sample_rate = 1 / _nearest['actual_sample_interval']
disk_mbps = sample_rate * np.dtype(NUMPY_DTYPE).itemsize / 1e6
capture_samples = int(CAPTURE_DURATION_S * sample_rate) if CAPTURE_DURATION_S > 0 else 0

print(f"Actual sample interval : {_nearest['actual_sample_interval'] * 1e9:.4g} ns")
print(f"ADC sample rate        : {sample_rate / 1e6:.2f} MS/s")
print(f"Disk write requirement : {disk_mbps:.0f} MB/s  (INT8, 1 byte/sample)")
if capture_samples > 0:
    estimated_gb = capture_samples * np.dtype(NUMPY_DTYPE).itemsize / 1e9
    print(f"Capture target         : {capture_samples:,} samples  ({CAPTURE_DURATION_S} s)")
    print(f"Estimated file size    : {estimated_gb:.2f} GB")
print()

actual_interval = scope.run_streaming(
    sample_interval=SAMPLE_INTERVAL_NS,
    time_units=psdk.TIME_UNIT.NS,
    max_pre_trigger_samples=0,
    max_post_trigger_samples=capture_samples if capture_samples > 0 else 1_000_000,
    auto_stop=1 if capture_samples > 0 else 0,
    ratio=0,
    ratio_mode=RATIO_MODE
)


# ============================================================================
# QUEUE AND SHARED STATE
# ============================================================================

# Producer-consumer queue between acquisition thread and write thread.
# maxsize caps peak in-memory backlog — each item is one poll's samples.
write_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

# Cumulative sample counters — written by one thread each, read by main thread.
# Python's GIL makes individual int reads/writes atomic; no lock needed.
total_samples_received = 0   # incremented by acquisition_thread
total_samples_written = 0    # incremented by write_thread

# Flag to signal both threads to stop
stop_streaming = False


# ============================================================================
# ACQUISITION THREAD
# ============================================================================

def acquisition_thread():
    """
    Polls the PicoScope for new raw samples and enqueues each batch for the
    write thread. Never writes to disk directly — minimises time spent outside
    the polling loop.

    The driver alternates between buffer_0 and buffer_1 (double buffering).
    When it switches, we re-register the vacated buffer so it is ready for
    the next cycle (hot-swap).
    """
    global stop_streaming, total_samples_received

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

                # .copy() is essential: releases the hardware buffer back to the
                # driver immediately so it can be re-registered or reused.
                chunk = src[start_index:start_index + n_samples].copy()

                try:
                    write_queue.put_nowait(chunk)
                except queue.Full:
                    print("[WARNING] Write queue full — disk cannot keep up, "
                          f"{n_samples:,} samples dropped")

                total_samples_received += n_samples

                # Hot-swap: re-register the buffer the driver just vacated so
                # it is available for the next fill cycle.
                if buffer_index != current_buffer_index:
                    current_buffer_index = buffer_index
                    free_buf = buffer_1 if buffer_index == 0 else buffer_0
                    scope.set_data_buffer(
                        psdk.CHANNEL.A, SAMPLES_PER_BUFFER,
                        buffer=free_buf, action=psdk.ACTION.ADD,
                        datatype=ADC_DATA_TYPE, ratio_mode=RATIO_MODE
                    )

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
    Drains the write queue and writes each chunk to the binary output file.
    Runs until stop_streaming is True AND the queue is fully drained, so no
    in-flight data is lost when the acquisition thread signals a stop.
    """
    global total_samples_written

    print(f"Write thread started → {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'wb') as f:
        while not stop_streaming or not write_queue.empty():
            try:
                chunk = write_queue.get(timeout=0.05)
                # tofile() writes the raw bytes without any numpy metadata —
                # equivalent to f.write(chunk.tobytes()) but avoids the extra copy.
                chunk.tofile(f)
                total_samples_written += len(chunk)
                write_queue.task_done()
            except queue.Empty:
                continue

    print(f"Write thread stopped  — {total_samples_written:,} samples written to disk")


# ============================================================================
# START THREADS
# ============================================================================

acq_thread = threading.Thread(target=acquisition_thread, daemon=True)
w_thread = threading.Thread(target=write_thread_func, daemon=False)

acq_thread.start()
w_thread.start()

if capture_samples > 0:
    print(f"Streaming {capture_samples:,} samples ({CAPTURE_DURATION_S} s)... "
          f"(Ctrl+C to stop early)\n")
else:
    print("Streaming... Press Ctrl+C to stop.\n")


# ============================================================================
# MAIN CAPTURE LOOP
# ============================================================================

capture_start = time.perf_counter()
last_snap = 0

try:
    while not stop_streaming:
        time.sleep(RATE_PRINT_INTERVAL)
        elapsed = time.perf_counter() - capture_start

        # Snapshot counters — reads of individual Python ints are GIL-atomic
        snap_received = total_samples_received
        snap_written = total_samples_written
        q_depth = write_queue.qsize()

        interval_samples = snap_received - last_snap
        instant_ms = interval_samples / RATE_PRINT_INTERVAL / 1e6
        avg_ms = snap_received / elapsed / 1e6 if elapsed > 0 else 0.0

        q_flag = f"  [QUEUE GROWING: {q_depth}]" if q_depth > QUEUE_WARN_DEPTH else ""

        print(f"[RATE] {instant_ms:.1f} MS/s  (avg {avg_ms:.1f} MS/s) | "
              f"written: {snap_written:,}  queue: {q_depth}{q_flag}")

        last_snap = snap_received

except KeyboardInterrupt:
    stop_streaming = True
    print("\nCapture interrupted by user.")


# ============================================================================
# CLEANUP
# ============================================================================

# Record final elapsed time before teardown
capture_elapsed = time.perf_counter() - capture_start

# Signal acquisition thread to exit and wait for it
stop_streaming = True
acq_thread.join(timeout=2.0)

# Wait for the write thread to drain the queue and close the file.
# Use a generous timeout — at 300 MB/s a full 500-item queue is ~37 GB;
# in practice the queue drains quickly once acquisition stops.
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

# Write JSON metadata sidecar — compatible with Smart_streaming validation tools
# which expect 'n_samples' and 'sample_rate_hz'.
metadata = {
    "timestamp": datetime.now().isoformat(),
    "channel": "A",
    "ratio_mode": "RAW",
    "sample_interval_ns": actual_interval,
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
