"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Hardware-triggered streaming to disk — PicoScope 6000E

Description:
  Configures a scope hardware trigger (set_simple_trigger), then streams
  continuously, buffering the most recent PRE_TRIGGER_SAMPLES in memory
  without writing anything to disk. When the hardware reports triggered?,
  the pre-trigger buffer is flushed to disk and the post-trigger samples
  continue writing until POST_TRIGGER_SAMPLES have been received.

  Trigger detection is hardware-only (no software threshold scan). The
  pre-trigger data is held in a rolling deque on the PC so that nothing
  reaches disk until the hardware confirms the trigger has fired.

  Why streaming instead of block mode?
    In block mode the device fills its onboard memory, then transfers
    everything to the host after capture ends — capture and transfer are
    strictly sequential. For a large post-trigger window this means the
    full capture duration elapses before a single byte reaches disk.

    In streaming mode data flows device → host continuously. The write
    thread drains to disk while the acquisition thread is still collecting
    post-trigger samples. By the time the post-trigger target is reached,
    the vast majority of data is already on disk, eliminating the
    sequential transfer phase and allowing post-processing to begin
    immediately.

    The post-capture summary reports how many samples were already on disk
    when the target was reached, and how long the final queue drain took.

  Architecture — three threads:
    acquisition_thread : polls hardware; buffers pre-trigger in a rolling
                         deque; flushes deque + writes post-trigger chunks
                         on triggered?; stops once POST_TRIGGER_SAMPLES
                         received
    write_thread       : drains the queue and writes chunks to disk
                         (queue is empty until the trigger fires)
    main thread        : live status (waiting / capturing), Ctrl+C handler

  Output:
    <OUTPUT_FILE>                — raw binary INT8 samples
    <OUTPUT_FILE_metadata.json>  — sample rate, dtype, trigger offset,
                                   pre/post sample counts

Key Concepts:
  - Hardware trigger: set_simple_trigger() is called before run_streaming().
    The hardware detects the crossing and reports triggered? in the poll
    callback. No per-sample software scan is needed.
  - Pre-trigger deque: incoming chunks are appended to a deque and oldest
    chunks shed from the front to keep the total <= PRE_TRIGGER_SAMPLES.
    Nothing is written to disk during this phase.
  - On triggered?: the entire deque (containing PRE_TRIGGER_SAMPLES of data)
    is flushed to the write queue in one go, then subsequent chunks flow
    directly to the queue until POST_TRIGGER_SAMPLES have been received.
  - Pre-trigger minimum: PRE_TRIGGER_SAMPLES must be >= POLL_INTERVAL ×
    sample_rate. Below this, a trigger that fires within a single poll window
    may not have enough pre-trigger data in the deque yet. A warning is
    printed at startup if this constraint is violated.
  - trigger_file_offset: the deque holds at most PRE_TRIGGER_SAMPLES, so
    the trigger sample is at approximately PRE_TRIGGER_SAMPLES in the file.
    data[:trigger_file_offset] = pre-trigger; data[trigger_file_offset:] = post.

SDK Limitations for streaming triggers:
  - RATIO_MODE.TRIGGER is not supported in streaming (block-mode only).
    Use RATIO_MODE.RAW with set_simple_trigger() instead.
  - Trigger settings require a full hardware restart (stop → reconfigure →
    run_streaming) to take effect; cannot be changed mid-stream.
  - Pre-trigger is capped by available PC memory and a 4-billion-sample
    SDK hard limit.
  - Post-trigger in block mode is capped by device onboard memory. In
    streaming mode it is limited only by disk space.

Requirements:
  - PicoScope 6000E
  - Python packages: numpy pypicosdk

Setup:
  - Connect a signal to Channel A (or use the AWG below)
  - Set TRIGGER_THRESHOLD_MV to a level your signal crosses
"""
import collections
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

# Raw mode: no hardware downsampling — every ADC sample delivered to host
RATIO_MODE = psdk.RATIO_MODE.RAW
ADC_DATA_TYPE = psdk.DATA_TYPE.INT8_T
NUMPY_DTYPE = np.int8

SAMPLE_INTERVAL_NS = 3.2        # ~312 MS/s (hardware rounds to nearest timebase)
SAMPLES_PER_BUFFER = 10_000_000 # each of the two hardware double-buffers
POLL_INTERVAL = 0.0005          # seconds between hardware polls (0 = busy-wait)

# --- Trigger ---
# Threshold in millivolts. At ±2 V range the full ADC scale is ±2000 mV.
TRIGGER_THRESHOLD_MV = 2000
TRIGGER_DIRECTION = 'rising'   # 'rising', 'falling', 'rising or falling', 'above', 'below'

# Samples to capture before and after the trigger crossing.
# PRE_TRIGGER_SAMPLES must be >= POLL_INTERVAL × sample_rate (checked at startup).
# At 312 MS/s: 1 M pre = ~3.2 ms; 14 B post = ~44.8 s capture.
# A large POST_TRIGGER_SAMPLES demonstrates the key streaming advantage: data
# flows to disk throughout the capture rather than waiting until the end, so
# processing can begin before the capture finishes and no device onboard memory
# is consumed.
PRE_TRIGGER_SAMPLES = 1_000_000
POST_TRIGGER_SAMPLES = 14_000_000_000

OUTPUT_FILE = "triggered_capture.bin"

QUEUE_MAXSIZE = 500     # max chunks buffered between acquisition and write threads
QUEUE_WARN_DEPTH = 100  # warn if queue depth exceeds this
RATE_PRINT_INTERVAL = 1.0


# ============================================================================
# HARDWARE SETUP
# ============================================================================

scope = psdk.ps6000a()
scope.open_unit()
print(f"Connected to PicoScope: {scope.get_unit_serial()}")
print(f"Hardware buffers: {SAMPLES_PER_BUFFER:,} samples each (× 2)")

scope.set_channel(
    channel=psdk.CHANNEL.A,
    range=psdk.RANGE.V5,
    coupling=psdk.COUPLING.DC,
    probe_scale=10
)

# Optionally drive a test signal via the built-in AWG
scope.set_siggen(frequency=1e6, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)

# Configure hardware trigger — must be called before run_streaming().
# auto_trigger=0: wait indefinitely for the trigger; set a microsecond
# timeout here if you want the capture to proceed even without a trigger.
scope.set_simple_trigger(
    channel=psdk.CHANNEL.A,
    threshold=TRIGGER_THRESHOLD_MV,
    threshold_unit='mv',
    direction=TRIGGER_DIRECTION,
    auto_trigger=0
)


# ============================================================================
# DOUBLE BUFFER SETUP
# ============================================================================

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

_nearest = scope.get_nearest_sampling_interval(SAMPLE_INTERVAL_NS * 1e-9)
sample_rate = 1 / _nearest['actual_sample_interval']
actual_interval_ns = _nearest['actual_sample_interval'] * 1e9

pre_duration_ms = PRE_TRIGGER_SAMPLES / sample_rate * 1e3
post_duration_ms = POST_TRIGGER_SAMPLES / sample_rate * 1e3
total_capture_samples = PRE_TRIGGER_SAMPLES + POST_TRIGGER_SAMPLES
estimated_mb = total_capture_samples * np.dtype(NUMPY_DTYPE).itemsize / 1e6

print(f"Actual sample interval : {actual_interval_ns:.4g} ns")
print(f"ADC sample rate        : {sample_rate / 1e6:.2f} MS/s")
print(f"Trigger                : {TRIGGER_DIRECTION} edge at {TRIGGER_THRESHOLD_MV} mV")
print(f"Pre-trigger window     : {PRE_TRIGGER_SAMPLES:,} samples  ({pre_duration_ms:.1f} ms)")
print(f"Post-trigger window    : {POST_TRIGGER_SAMPLES:,} samples  ({post_duration_ms:.1f} ms)")
print(f"Estimated file size    : {estimated_mb:.1f} MB")

# Warn if pre-trigger is below the minimum guaranteed by the poll interval.
# A trigger that fires within a single poll window needs at least one full
# poll's worth of samples already resident in the hardware buffer.
min_pre_trigger = int(POLL_INTERVAL * sample_rate)
if PRE_TRIGGER_SAMPLES < min_pre_trigger:
    print(f"[WARNING] PRE_TRIGGER_SAMPLES ({PRE_TRIGGER_SAMPLES:,}) is below the "
          f"recommended minimum ({min_pre_trigger:,} = POLL_INTERVAL × sample_rate). "
          f"Pre-trigger data may be incomplete if the trigger fires within the first poll.")
print()

# auto_stop=0: streaming continues until we call scope.stop(). The driver
# validates maxPre + maxPost against device memory when auto_stop=1, which
# rejects captures larger than device memory. With auto_stop=0 this check
# is skipped and we stop manually once POST_TRIGGER_SAMPLES are received.
# max_post_trigger_samples is a buffer-sizing hint; SAMPLES_PER_BUFFER is
# sufficient since the actual capture limit is enforced in software below.
actual_interval = scope.run_streaming(
    sample_interval=SAMPLE_INTERVAL_NS,
    time_units=psdk.TIME_UNIT.NS,
    max_pre_trigger_samples=PRE_TRIGGER_SAMPLES,
    max_post_trigger_samples=SAMPLES_PER_BUFFER,
    auto_stop=0,
    ratio=0,
    ratio_mode=RATIO_MODE
)


# ============================================================================
# QUEUE AND SHARED STATE
# ============================================================================

write_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

# Counters written by one thread each — GIL makes individual int reads atomic.
total_samples_received = 0  # acquisition_thread
total_samples_written = 0   # write_thread

stop_streaming = False

# Pre-trigger buffer — written and read only by acquisition_thread, except
# trigger_fired which is also read by the main thread for display (GIL-safe).
trigger_fired = False               # set True when triggered? first seen
pre_trigger_deque = collections.deque()  # chunks buffered before trigger
pre_trigger_total = 0               # total samples currently in deque


# ============================================================================
# ACQUISITION THREAD
# ============================================================================

def acquisition_thread():
    """
    Polls the PicoScope and manages two phases:

      Pre-trigger (trigger_fired is False):
        Buffer incoming chunks in pre_trigger_deque, shedding oldest chunks
        from the front to keep the total <= PRE_TRIGGER_SAMPLES. Nothing is
        written to disk. When triggered? fires, flush the entire deque to
        the write queue in one go and set trigger_fired.

      Post-trigger (trigger_fired is True):
        Enqueue every chunk directly for the write thread. Stop once
        post_trigger_received >= POST_TRIGGER_SAMPLES.

    Samples are always processed before checking the stop condition so the
    final chunk from the last poll is never lost.
    """
    global stop_streaming, total_samples_received
    global trigger_fired, pre_trigger_deque, pre_trigger_total

    print("Acquisition thread started")
    last_status = None
    current_buffer_index = 0
    post_trigger_received = 0

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

            n_samples = info['no of samples']

            if n_samples > 0:
                buffer_index = info['Buffer index'] % 2
                start_index = info.get('start index', 0)
                src = buffer_0 if buffer_index == 0 else buffer_1

                chunk = src[start_index:start_index + n_samples].copy()
                total_samples_received += n_samples

                # Hot-swap: re-register the vacated buffer for the next fill cycle
                if buffer_index != current_buffer_index:
                    current_buffer_index = buffer_index
                    free_buf = buffer_1 if buffer_index == 0 else buffer_0
                    scope.set_data_buffer(
                        psdk.CHANNEL.A, SAMPLES_PER_BUFFER,
                        buffer=free_buf, action=psdk.ACTION.ADD,
                        datatype=ADC_DATA_TYPE, ratio_mode=RATIO_MODE
                    )

                if not trigger_fired:
                    # Buffer in rolling pre-trigger deque — no disk writes yet
                    pre_trigger_deque.append(chunk)
                    pre_trigger_total += len(chunk)

                    # Shed oldest chunks to keep buffer <= PRE_TRIGGER_SAMPLES
                    while (len(pre_trigger_deque) > 0 and
                           pre_trigger_total - len(pre_trigger_deque[0]) >= PRE_TRIGGER_SAMPLES):
                        removed = pre_trigger_deque.popleft()
                        pre_trigger_total -= len(removed)
                else:
                    # Post-trigger: write directly to queue
                    try:
                        write_queue.put_nowait(chunk)
                    except queue.Full:
                        print(f"[WARNING] Write queue full — disk cannot keep up, "
                              f"{n_samples:,} samples dropped")
                    post_trigger_received += n_samples

            # Check triggered? after buffering the current chunk so the chunk
            # containing the trigger crossing is included in the deque flush.
            if info['triggered?'] and not trigger_fired:
                trigger_fired = True
                print(f"\n[TRIGGER] Hardware trigger fired  "
                      f"(sample {info['triggered at']:,} in stream)")

                # Flush the entire pre-trigger deque to the write queue
                for pre_chunk in pre_trigger_deque:
                    try:
                        write_queue.put_nowait(pre_chunk)
                    except queue.Full:
                        print("[WARNING] Write queue full during pre-trigger flush")
                pre_trigger_deque.clear()
                pre_trigger_total = 0

            if trigger_fired and post_trigger_received >= POST_TRIGGER_SAMPLES:
                # Snapshot samples already on disk — the remainder is still in
                # the write queue and will drain in the post-capture flush.
                # Use the capture target as the denominator, not total_samples_received:
                # total_samples_received includes all the pre-trigger stream data that
                # was shed from the rolling deque before the trigger fired.
                on_disk = total_samples_written
                capture_target = PRE_TRIGGER_SAMPLES + POST_TRIGGER_SAMPLES
                pct = on_disk * 100 // capture_target
                print(f"[INFO] Post-trigger target reached — {on_disk:,} samples already on disk "
                      f"({pct}% of {capture_target:,} capture target)")
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
    Drains the write queue and writes each chunk to the binary output file.
    Runs until stop_streaming is True AND the queue is fully drained.
    """
    global total_samples_written

    print(f"Write thread started → {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'wb') as f:
        while not stop_streaming or not write_queue.empty():
            try:
                chunk = write_queue.get(timeout=0.05)
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

print(f"Waiting for {TRIGGER_DIRECTION} edge trigger at {TRIGGER_THRESHOLD_MV} mV... "
      f"(Ctrl+C to abort)\n")


# ============================================================================
# MAIN CAPTURE LOOP
# ============================================================================

capture_start = time.perf_counter()
last_snap = 0

try:
    while not stop_streaming:
        time.sleep(RATE_PRINT_INTERVAL)
        elapsed = time.perf_counter() - capture_start

        snap_received = total_samples_received
        snap_written = total_samples_written
        q_depth = write_queue.qsize()

        interval_samples = snap_received - last_snap
        instant_ms = interval_samples / RATE_PRINT_INTERVAL / 1e6

        if not trigger_fired:
            print(f"[WAITING]   {instant_ms:.1f} MS/s  |  "
                  f"pre-buffer filling... ({elapsed:.1f} s elapsed)")
        else:
            # Progress relative to the capture target, not total samples received.
            # total_samples_received includes discarded pre-trigger stream data
            # (everything shed from the rolling deque before the trigger fired).
            capture_target = PRE_TRIGGER_SAMPLES + POST_TRIGGER_SAMPLES
            pct_written = snap_written * 100 // capture_target
            q_flag = f"  [QUEUE GROWING: {q_depth}]" if q_depth > QUEUE_WARN_DEPTH else ""
            print(f"[CAPTURING] {instant_ms:.1f} MS/s  |  "
                  f"written: {snap_written:,} ({pct_written}%)  queue: {q_depth}{q_flag}")

        last_snap = snap_received

except KeyboardInterrupt:
    stop_streaming = True
    print("\nCapture aborted by user.")


# ============================================================================
# CLEANUP
# ============================================================================

capture_elapsed = time.perf_counter() - capture_start
stop_streaming = True
acq_thread.join(timeout=2.0)

# Snapshot samples on disk before the final drain so we can report the overlap.
samples_on_disk_at_stop = total_samples_written

drain_start = time.perf_counter()
print("Flushing write queue to disk...")
w_thread.join(timeout=60.0)
drain_elapsed = time.perf_counter() - drain_start
if w_thread.is_alive():
    print("[WARNING] Write thread did not finish draining — output file may be incomplete")

scope.stop()
scope.close_unit()
print("PicoScope closed.")


# ============================================================================
# POST-CAPTURE SUMMARY AND METADATA
# ============================================================================

print(f"\n{'─' * 50}")
print(f"Trigger fired          : {trigger_fired}")
print(f"Total elapsed          : {capture_elapsed:.3f} s  (trigger wait + capture)")
print(f"Post-capture drain     : {drain_elapsed:.3f} s  (queue flush after target reached)")
print(f"Samples received       : {total_samples_received:,}")
print(f"Samples written        : {total_samples_written:,}")
if trigger_fired and total_samples_written > 0:
    pct_during = samples_on_disk_at_stop * 100 // total_samples_written
    print(f"On disk at target      : {samples_on_disk_at_stop:,}  ({pct_during}% transferred during capture)")
if trigger_fired:
    print(f"Trigger file offset    : {PRE_TRIGGER_SAMPLES:,}  (index in output file)")
print(f"{'─' * 50}\n")

if not trigger_fired:
    print("[INFO] No trigger detected — output file contains pre-trigger data only.")
else:
    # The hardware guarantees exactly PRE_TRIGGER_SAMPLES before the trigger,
    # so the trigger sample is always at index PRE_TRIGGER_SAMPLES in the file.
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "channel": "A",
        "ratio_mode": "RAW",
        "sample_interval_ns": actual_interval_ns,
        "sample_rate_hz": sample_rate,
        "dtype": "int8",
        "bytes_per_sample": 1,
        "n_samples": total_samples_written,
        "trigger_file_offset": PRE_TRIGGER_SAMPLES,
        "pre_trigger_samples": PRE_TRIGGER_SAMPLES,
        "post_trigger_samples": POST_TRIGGER_SAMPLES,
        "trigger_threshold_mv": TRIGGER_THRESHOLD_MV,
        "trigger_direction": TRIGGER_DIRECTION,
        "output_file": OUTPUT_FILE,
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
    print(f"  trig = meta['trigger_file_offset']  # trigger sample is at this index")
    print(f"  pre  = data[:trig]                  # samples before trigger")
    print(f"  post = data[trig:]                  # samples from trigger onwards")
