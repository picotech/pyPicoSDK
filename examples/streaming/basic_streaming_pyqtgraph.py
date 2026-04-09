"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Basic streaming example for a PicoScope 6000E device with PyQtGraph

Description:
  Demonstrates how to perform continuous streaming data capture with real-time
  plotting using pyPicoSDK and PyQtGraph. Uses hardware downsampling (decimate
  mode) with double-buffered data acquisition in a background thread.

Key Concepts:
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

# Hardware downsampling ratio: every 640 raw ADC samples
# produce 1 output sample
DOWNSAMPLE_RATIO = 640

# Downsampling mode: DECIMATE keeps every Nth sample, discarding the rest
DOWNSAMPLE_MODE = psdk.RATIO_MODE.DECIMATE

# ADC data type for DECIMATE mode (8-bit signed integer, range -128 to +127)
ADC_DATA_TYPE = psdk.DATA_TYPE.INT8_T

# Numpy data type matching the ADC data type above
NUMPY_DTYPE = np.int8

# Number of downsampled samples kept in the rolling display buffer. Large windows require more RAM
RING_BUFFER_SIZE = 2_000

# How often the acquisition thread polls the hardware for new data (seconds)
POLL_INTERVAL = 0.01

# Plot refresh interval in milliseconds (~30 FPS)
REFRESH_MS = 33

# Requested ADC sample interval in nanoseconds (hardware may adjust this)
SAMPLE_INTERVAL_NS = 1_000


# ============================================================================
# HARDWARE SETUP
# ============================================================================

# Create "scope" class for a PicoScope 6000E device
scope = psdk.ps6000a()

# Open the device and connect to it
scope.open_unit()

# Print the serial number of the connected instrument
print(f"Connected to PicoScope: {scope.get_unit_serial()}")

# Query the device's maximum sample memory and size the buffer to use 95% of it
max_memory = scope.get_maximum_available_memory()
SAMPLES_PER_BUFFER = int(max_memory * 0.95 / DOWNSAMPLE_RATIO)
print(f"Device memory: {max_memory:,} samples → "
      f"buffer: {SAMPLES_PER_BUFFER:,} downsampled samples")

# Enable Channel A with ±500mV range and DC coupling
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.mV500, coupling=psdk.COUPLING.DC)

scope.set_siggen(frequency=1, pk2pk=0.8, wave_type=psdk.WAVEFORM.SINE)

# ============================================================================
# DOUBLE BUFFER SETUP
# ============================================================================

# Create two hardware buffers for double-buffered streaming
# While the driver fills one buffer, we safely read from the other
buffer_0 = np.zeros(SAMPLES_PER_BUFFER, dtype=NUMPY_DTYPE)
buffer_1 = np.zeros(SAMPLES_PER_BUFFER, dtype=NUMPY_DTYPE)

# Clear any previously registered buffers on Channel A
scope.set_data_buffer(psdk.CHANNEL.A, 0, action=psdk.ACTION.CLEAR_ALL)

# Register both buffers with the driver for downsampled streaming
# ACTION.ADD tells the driver to add each buffer to its internal list
for buf in [buffer_0, buffer_1]:
    scope.set_data_buffer(
        psdk.CHANNEL.A, SAMPLES_PER_BUFFER, buffer=buf,
        action=psdk.ACTION.ADD, datatype=ADC_DATA_TYPE,
        ratio_mode=DOWNSAMPLE_MODE
    )


# ============================================================================
# START STREAMING
# ============================================================================

# Start continuous streaming with hardware downsampling
# auto_stop=0 means streaming runs indefinitely until we call scope.stop()
actual_interval = scope.run_streaming(
    sample_interval=SAMPLE_INTERVAL_NS,
    time_units=psdk.TIME_UNIT.NS,
    max_pre_trigger_samples=0,
    max_post_trigger_samples=1_000_000,
    auto_stop=0,
    ratio=DOWNSAMPLE_RATIO,
    ratio_mode=DOWNSAMPLE_MODE
)

# Calculate the actual ADC sample rate from the returned interval
hardware_sample_rate = 1e9 / actual_interval

# Print the actual streaming parameters selected by the hardware
print(f"Actual sample interval: {actual_interval} ns")
rate_mhz = hardware_sample_rate / 1e6
print(f"Hardware ADC sample rate: {rate_mhz:.2f} MHz")
ds_rate = hardware_sample_rate / DOWNSAMPLE_RATIO
print(f"Downsampled output rate: {ds_rate:.2f} samples/sec")

print(f"Ring buffer: {RING_BUFFER_SIZE:,} downsampled samples")


# ============================================================================
# RING BUFFER INITIALISATION
# ============================================================================

# Circular (ring) buffer: a fixed-size array that overwrites the oldest
# samples when full, giving a sliding window over the most recent data.
# float32 for PyQtGraph compatibility (ADC int8 values are cast on write).
ring_buffer = np.zeros(RING_BUFFER_SIZE, dtype=np.float32)

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


# ============================================================================
# PYQTGRAPH WINDOW SETUP
# ============================================================================

# Create the Qt application (required by PyQtGraph)
app = pg.mkQApp("PicoScope Streaming")

# Create the main graphics window
win = pg.GraphicsLayoutWidget(title="PicoScope Basic Streaming Example")

# Set the initial window size in pixels (width, height)
win.resize(1_000, 500)

# Display the window on screen
win.show()

# Add a plot area to the window
plot = win.addPlot(
    title=f"Channel A \u2014 Continuous Streaming ({DOWNSAMPLE_RATIO}:1 Decimate)"
)

# Label axes
plot.setLabel('left', 'Amplitude', units='ADC counts')
plot.setLabel('bottom', 'Sample Index')

# Enable grid lines for easier reading
plot.showGrid(x=True, y=True)

# Set Y-axis range to the full INT8 ADC range (-128 to +127) with small margin
plot.setYRange(-130, 130)

# Lock the x-range to the display window (in raw ADC sample indices)
plot.setXRange(0, RING_BUFFER_SIZE * DOWNSAMPLE_RATIO, padding=0)

# Create the plot curve as individual scatter points (no connecting line)
# Each dot represents one downsampled sample; the empty space between dots
# honestly shows the DOWNSAMPLE_RATIO gap where no data was retained.
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
# ACQUISITION THREAD FUNCTION
# ============================================================================

def acquisition_thread():
    """
    Background thread that continuously polls the PicoScope for new streaming
    data and writes it into the shared ring buffer.

    The driver alternates between buffer_0 and buffer_1 (double buffering).
    We read from whichever buffer the driver indicates, copy the new samples
    into the ring buffer, and set data_updated=True so the plot refreshes.
    """
    global ring_head, ring_filled, data_updated, stop_streaming

    print("Acquisition thread started")
    last_status = None
    current_buffer_index = 0

    while not stop_streaming:
        try:
            info = scope.get_streaming_latest_values(
                channel=psdk.CHANNEL.A,
                ratio_mode=DOWNSAMPLE_MODE,
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
                new_data = current_buffer[start_index:end].astype(np.float32)

                with data_lock:
                    n = len(new_data)

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
                        datatype=ADC_DATA_TYPE, ratio_mode=DOWNSAMPLE_MODE
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
    Reads ring buffer in logical order (oldest to newest).
    """
    # Declare the flag as global so we can clear it after reading
    global data_updated

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

    # Skip if there is nothing to plot
    if len(y_data) == 0:
        return

    # Position each downsampled sample at its true raw ADC sample index
    x_data = np.arange(len(y_data), dtype=np.int64) * DOWNSAMPLE_RATIO

    # Update the plot curve with the new X and Y data
    curve.setData(x_data, y_data)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Start the background acquisition thread as a daemon thread
# Daemon threads automatically stop when the main program exits
acq_thread = threading.Thread(target=acquisition_thread, daemon=True)
acq_thread.start()

# Create a QTimer that fires at the target refresh rate to update the plot
timer = QtCore.QTimer()

# Connect the timer's timeout signal to the plot update function
timer.timeout.connect(update_plot)

timer.start(REFRESH_MS)

# Print instructions for the user
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

# Print shutdown confirmation
print("PicoScope closed. Done.")
