"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Basic RAW streaming example for a PicoScope 6000E device with PyQtGraph

Description:
  Demonstrates continuous streaming data capture WITHOUT hardware downsampling.
  Every raw ADC sample is delivered to the host and plotted in real time using
  PyQtGraph. Compare with basic_streaming_pyqtgraph.py which uses 640:1
  hardware decimation.

  Because every sample reaches the host, the ADC sample rate must be much lower
  than in the downsampled example (1 MS/s here vs 1.25 GS/s there). This
  trade-off gives full-fidelity data at the cost of lower bandwidth.

  This stream-to-plot example teaches recommended best practice for streaming
  and is set to 1 MS/s by default. In a Python environment with ~100K samples
  rolling on the graph, rates up to 10 MS/s are achievable — but for a live
  visual plot this is usually unnecessary, since the screen can only display
  a fraction of those points at any one time.

Key Concepts:
  - Raw mode: ratio=0 with RATIO_MODE.RAW — no hardware downsampling
  - INT8 data: Raw samples are 8-bit signed integers (-128 to +127)
  - Double buffering: Two hardware buffers alternate so data is never lost
  - Ring buffer: Circular buffer stores a rolling window of samples for display
  - Threaded acquisition: Background thread polls hardware,
    main thread updates plot
  - QTimer plot refresh: Qt timer triggers plot updates at ~30 FPS

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) pyqtgraph numpy pypicosdk PyQt5

Setup:
  - Connect a signal to Channel A (or use the AWG output)
"""
import time
import threading
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
import pypicosdk as psdk


# ============================================================================
# CONFIGURATION
# ============================================================================

# Raw mode: no hardware downsampling — every ADC sample
# is delivered to the host
RATIO_MODE = psdk.RATIO_MODE.RAW

# ADC data type for raw mode (8-bit signed integer, range -128 to +127)
ADC_DATA_TYPE = psdk.DATA_TYPE.INT8_T

# Numpy data type matching the ADC data type above
NUMPY_DTYPE = np.int8

# ADC range derived from the data type (e.g. INT8 → -128..+127)
ADC_MIN = int(np.iinfo(NUMPY_DTYPE).min)
ADC_MAX = int(np.iinfo(NUMPY_DTYPE).max)

# Number of raw samples kept in the rolling display buffer
# (1M = 1 second @ 1 MS/s).
# Recommended max: 1,000,000. Larger values increase per-frame cost because
# the entire buffer is copied and passed to PyQtGraph on every plot refresh.
RING_BUFFER_SIZE = 1_000_000

# Size of each hardware double-buffer registered with the driver.
# Must be large enough that it does not overflow between polls — i.e. the
# buffer must hold more samples than arrive between consecutive calls to
# get_streaming_latest_values(). At 10 MHz with 1 ms polls, ~10,000 samples
# arrive per poll, so 10M gives ~1000× headroom.
SAMPLES_PER_BUFFER = 10_000_000

# How often the acquisition thread polls the hardware for new data (seconds)
POLL_INTERVAL = 0.001

# Plot refresh interval in milliseconds (~30 FPS)
REFRESH_MS = 60

# Requested ADC sample interval in nanoseconds (1000 ns = 1 µs = 1 MS/s).
# The hardware may adjust this; the actual interval is printed at startup.
SAMPLE_INTERVAL_NS = 1000


# ============================================================================
# HARDWARE SETUP
# ============================================================================

# Create "scope" class for a PicoScope 6000E device
scope = psdk.ps6000a()

# Open the device and connect to it
scope.open_unit()

# Print the serial number of the connected instrument
print(f"Connected to PicoScope: {scope.get_unit_serial()}")

print(f"Hardware buffer: {SAMPLES_PER_BUFFER:,} samples per buffer")

# Enable Channel A with ±500mV range and DC coupling
scope.set_channel(
    channel=psdk.CHANNEL.A,
    range=psdk.RANGE.V2,
    coupling=psdk.COUPLING.DC
)

# Configure the built-in signal generator to output a 1 MHz sine wave
# at 1.8 V peak-to-peak — useful for testing without an external source
scope.set_siggen(frequency=1e6, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)


# ============================================================================
# DOUBLE BUFFER SETUP
# ============================================================================

# Create two hardware buffers for double-buffered streaming.
# While the driver fills one buffer, we safely read from the other.
buffer_0 = np.zeros(SAMPLES_PER_BUFFER, dtype=NUMPY_DTYPE)
buffer_1 = np.zeros(SAMPLES_PER_BUFFER, dtype=NUMPY_DTYPE)

# Clear any previously registered buffers on Channel A
scope.set_data_buffer(psdk.CHANNEL.A, 0, action=psdk.ACTION.CLEAR_ALL)

# Register both buffers with the driver for raw streaming
for buf in [buffer_0, buffer_1]:
    scope.set_data_buffer(
        psdk.CHANNEL.A, SAMPLES_PER_BUFFER, buffer=buf,
        action=psdk.ACTION.ADD, datatype=ADC_DATA_TYPE,
        ratio_mode=RATIO_MODE
    )


# ============================================================================
# START STREAMING
# ============================================================================

# Start continuous raw streaming (ratio=0 means no downsampling).
# auto_stop=0 means streaming runs indefinitely until we call scope.stop().
actual_interval = scope.run_streaming(
    sample_interval=SAMPLE_INTERVAL_NS,
    time_units=psdk.TIME_UNIT.NS,
    max_pre_trigger_samples=0,
    max_post_trigger_samples=1_000_000,
    auto_stop=0,
    ratio=0,
    ratio_mode=RATIO_MODE
)

# Calculate the actual ADC sample rate from the returned interval
sample_rate = 1e9 / actual_interval

# Print the actual streaming parameters selected by the hardware
print(f"Actual sample interval: {actual_interval} ns")
print(f"ADC sample rate: {sample_rate / 1e6:.2f} MHz (raw — no downsampling)")
print(f"Ring buffer: {RING_BUFFER_SIZE:,} samples "
      f"({RING_BUFFER_SIZE / sample_rate:.3f} s window)")


# ============================================================================
# RING BUFFER INITIALISATION
# ============================================================================

# Circular (ring) buffer: a fixed-size array that overwrites the oldest
# samples when full, giving a sliding window over the most recent data.
# Uses the same integer dtype as the ADC — no float conversion needed
# because raw mode delivers every sample (no gaps that would require NaN).
ring_buffer = np.zeros(RING_BUFFER_SIZE, dtype=NUMPY_DTYPE)

# Write cursor: index where the NEXT sample will be written.
# Advances forward and wraps to 0 when it reaches RING_BUFFER_SIZE,
# creating the circular behaviour.
ring_head = 0

# How many slots contain real data (grows from 0 to RING_BUFFER_SIZE,
# then stays clamped). Lets the reader distinguish "buffer partly filled"
# from "buffer full and wrapping".
ring_filled = 0

# Mutex: the acquisition thread WRITES the ring buffer and the Qt timer
# READS it — the lock prevents them from accessing it simultaneously.
data_lock = threading.Lock()

# Flag indicating new data is available for plotting
data_updated = False

# Flag to signal the acquisition thread to stop
stop_streaming = False

# ── Live rate tracking ──
# These variables measure the OBSERVED throughput of raw samples
# actually delivered by the driver to our application — NOT a theoretical
# rate. The hardware ADC rate is printed once at startup (sample_rate);
# this tracks what we actually receive, and should be close to it.

# Cumulative count of raw samples received from the driver.
# Incremented in the acquisition thread under data_lock.
total_samples_received = 0

# High-resolution timestamps used to compute rates:
#   rate_start_time          – session start (for the overall average)
#   rate_interval_start_*    – reset each print window (for the instant rate)
rate_start_time = time.perf_counter()
rate_interval_start_time = rate_start_time
rate_interval_start_count = 0

# How often (seconds) the console rate line is printed
RATE_PRINT_INTERVAL = 1.0


# ============================================================================
# PYQTGRAPH WINDOW SETUP
# ============================================================================

# Create the Qt application (required by PyQtGraph)
app = pg.mkQApp("PicoScope Raw Streaming")

# Create the main graphics window
win = pg.GraphicsLayoutWidget(title="PicoScope Basic Raw Streaming Example")

# Set the initial window size in pixels (width, height)
win.resize(1_000, 500)

# Display the window on screen
win.show()

# Add a plot area to the window
plot = win.addPlot(title="Channel A \u2014 Raw Streaming (No Downsampling)")

# Label axes
plot.setLabel('left', 'Amplitude', units='ADC counts')
plot.setLabel('bottom', 'Sample Index')

# Enable grid lines for easier reading
plot.showGrid(x=True, y=True)

# Lock Y-axis to the full ADC range and prevent mouse zoom/pan on Y.
# The limits are derived from NUMPY_DTYPE so they update automatically
# if the data type changes (e.g. INT8 → INT16 for AVERAGE mode).
plot.setYRange(ADC_MIN, ADC_MAX, padding=0.02)
plot.setLimits(yMin=ADC_MIN, yMax=ADC_MAX)
plot.getViewBox().setMouseEnabled(y=False)

# Lock the x-range to the display window
plot.setXRange(0, RING_BUFFER_SIZE, padding=0)

# Create the plot curve as a continuous line. Unlike the downsampled example
# (which uses scatter dots to honestly show gaps), raw mode has every sample
# so a solid line is appropriate. autoDownsample lets PyQtGraph thin points
# at render time when zoomed out, keeping the frame rate smooth.
curve = plot.plot(
    pen=pg.mkPen(color='cyan', width=1),
    clipToView=True,
    autoDownsample=True
)


# ============================================================================
# ACQUISITION THREAD FUNCTION
# ============================================================================

def acquisition_thread():
    """
    Background thread that continuously polls the PicoScope for new raw
    streaming data and writes it into the shared ring buffer.

    The driver alternates between buffer_0 and buffer_1 (double buffering).
    We read from whichever buffer the driver indicates, copy the new samples
    into the ring buffer, and set data_updated=True so the plot refreshes.
    """
    global ring_head, ring_filled, data_updated, stop_streaming, total_samples_received

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
                print("[WARNING] Driver buffer overflow detected")

            if info['auto stopped?']:
                print("[INFO] Driver auto-stopped streaming")
                break

            n_samples = info['no of samples']

            if n_samples > 0:
                buffer_index = info['Buffer index'] % 2
                start_index = info.get('start index', 0)

                current_buffer = (
                    buffer_0 if buffer_index == 0 else buffer_1
                )

                end = start_index + n_samples
                new_data = current_buffer[start_index:end]

                with data_lock:
                    n = len(new_data)

                    # If the batch is larger than the entire ring buffer,
                    # only the most recent RING_BUFFER_SIZE samples matter —
                    # older ones would be overwritten immediately anyway.
                    if n > RING_BUFFER_SIZE:
                        new_data = new_data[-RING_BUFFER_SIZE:]
                        n = RING_BUFFER_SIZE

                    # How many slots remain between the write cursor and the
                    # physical end of the array — determines if we need to wrap.
                    space_to_end = RING_BUFFER_SIZE - ring_head

                    if n <= space_to_end:
                        # SIMPLE CASE: all new samples fit without wrapping.
                        #   [. . . . H H H H . . . .]
                        #            ^head   ^head+n
                        #            ╰─ new data ──╯
                        ring_buffer[ring_head:ring_head + n] = new_data
                    else:
                        # WRAP CASE: new data spans the boundary between the
                        # end and the start of the array — split into two copies.
                        #
                        #   Before: [. . . . . . . . H H H H]  (space_to_end=4)
                        #                            ^head   ^end
                        #   After:  [W W W . . . . . H H H H]
                        #            ╰wrap╯          ╰first─╯
                        #            (copy 2)        (copy 1)
                        ring_buffer[ring_head:] = new_data[:space_to_end]
                        ring_buffer[:n - space_to_end] = new_data[space_to_end:]

                    # Advance the write cursor, wrapping back to 0 via modulo.
                    # This is what makes the buffer "circular".
                    ring_head = (ring_head + n) % RING_BUFFER_SIZE

                    # Track how full the buffer is (clamp at max — once full,
                    # stays full because old data is simply overwritten)
                    ring_filled = min(ring_filled + n, RING_BUFFER_SIZE)

                    # Bump the cumulative counter so the plot timer can
                    # compute a live observed-throughput rate. Uses n_samples
                    # (the full driver count) not n (which may be truncated
                    # to RING_BUFFER_SIZE) so the rate reflects true throughput.
                    total_samples_received += n_samples

                    # Signal to the plot timer that fresh data is available
                    data_updated = True

                # Hot-swap: when the driver switches to a new buffer, re-register
                # the one it just finished filling so it is ready for the next cycle
                if buffer_index != current_buffer_index:
                    current_buffer_index = buffer_index
                    free_buffer = buffer_1 if buffer_index == 0 else buffer_0
                    scope.set_data_buffer(
                        psdk.CHANNEL.A, SAMPLES_PER_BUFFER,
                        buffer=free_buffer, action=psdk.ACTION.ADD,
                        datatype=ADC_DATA_TYPE, ratio_mode=RATIO_MODE
                    )

        except Exception as e:
            print(f"Acquisition error (last_status={last_status}): {e}")
            break

        time.sleep(POLL_INTERVAL)

    print("Acquisition thread stopped")


# ============================================================================
# PLOT UPDATE FUNCTION
# ============================================================================

def update_plot():
    """
    Called by QTimer on the main thread to refresh the plot.
    Reads ring buffer in logical order (oldest to newest) and
    periodically prints a live sample-rate summary to the console.
    """
    # Declare globals so we can clear/update them after reading
    global data_updated, rate_interval_start_time, rate_interval_start_count

    with data_lock:
        if not data_updated:
            return

        if ring_filled < RING_BUFFER_SIZE:
            # FILLING PHASE: buffer hasn't wrapped yet.
            # Data sits contiguously from index 0 to ring_filled:
            #   [D D D D D D 0 0 0 0 0 0]
            #    ╰─ valid ─╯ ╰─ empty ──╯
            # .copy() is essential: without it y_data would be a VIEW into
            # ring_buffer, and the acq thread could mutate it after we
            # release the lock.
            y_data = ring_buffer[:ring_filled].copy()
        else:
            # WRAPPED PHASE: buffer is full and ring_head has wrapped.
            # The OLDEST sample is at ring_head; the NEWEST is just before it.
            #   [new new new OLD OLD OLD OLD]
            #    ╰─ tail ──╯ ╰── head ─────╯
            #                 ^ring_head
            #
            # To read oldest-to-newest, concatenate:
            #   1) ring_head → end   (oldest data)
            #   2) 0 → ring_head    (newest data)
            # concatenate always returns a new array, so no .copy() needed.
            y_data = np.concatenate((
                ring_buffer[ring_head:],
                ring_buffer[:ring_head]
            ))

        # Clear the flag so we don't re-draw the same data next tick
        data_updated = False

        # Snapshot the cumulative counter while we still hold the lock —
        # avoids a race with the acquisition thread
        snap_total = total_samples_received

    # Skip if there is nothing to plot
    if len(y_data) == 0:
        return

    # Each sample maps 1:1 to a sample index (no downsampling gap)
    x_data = np.arange(len(y_data), dtype=np.int64)

    # Update the plot curve with the new X and Y data
    curve.setData(x_data, y_data)

    # ── Live rate printout (every RATE_PRINT_INTERVAL seconds) ──
    # These are the OBSERVED throughput of raw samples delivered
    # by the driver, not a theoretical rate.
    # instant_rate : raw samples/sec over the most recent window
    # avg_rate     : raw samples/sec averaged since streaming started
    # Expected to be close to sample_rate (the hardware ADC rate).
    now = time.perf_counter()
    interval_elapsed = now - rate_interval_start_time
    if interval_elapsed >= RATE_PRINT_INTERVAL:
        interval_samples = snap_total - rate_interval_start_count
        instant_rate = interval_samples / interval_elapsed
        overall_elapsed = now - rate_start_time
        avg_rate = snap_total / overall_elapsed if overall_elapsed > 0 else 0
        print(f"[RATE] {instant_rate:,.1f} S/s (avg {avg_rate:,.1f} S/s) | "
              f"plotted: {len(y_data):,} | total received: {snap_total:,}")

        # Reset the window counters for the next interval
        rate_interval_start_time = now
        rate_interval_start_count = snap_total


# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Start the background acquisition thread as a daemon thread
acq_thread = threading.Thread(target=acquisition_thread, daemon=True)
acq_thread.start()

# Create a QTimer that fires at the target refresh rate to update the plot
timer = QtCore.QTimer()

# Connect the timer's timeout signal to the plot update function
timer.timeout.connect(update_plot)

timer.start(REFRESH_MS)

print("\nStreaming... Close the plot window or press Ctrl+C to stop.\n")

# Run the Qt event loop — this blocks until the window is closed
try:
    pg.exec()
except KeyboardInterrupt:
    pass


# ============================================================================
# CLEANUP
# ============================================================================

# Signal the acquisition thread to stop its polling loop
stop_streaming = True

# Wait up to 2 seconds for the acquisition thread to finish
acq_thread.join(timeout=2.0)

# Stop streaming on the PicoScope hardware
scope.stop()

# Close the connection to the PicoScope device
scope.close_unit()

print("PicoScope closed. Done.")
