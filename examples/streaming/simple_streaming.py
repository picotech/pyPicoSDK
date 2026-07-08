"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Hardware-agnostic streaming with live plot — PicoScope 6000E / 3000E / 5000E / 5000D

Description:
  Streams Channel A continuously using StreamingSession, the supported
  hardware-agnostic streaming loop, and displays the most recent samples in
  a live PyQtGraph window. The session owns buffer registration, rotation
  and polling for every driver, so the ONLY line that changes between
  devices is the SCOPE_CLASS below.

  Compare with the other examples in this folder, which drive the low-level
  streaming calls (set_data_buffer / run_streaming /
  get_streaming_latest_values) directly: that surface exposes each driver's
  own buffer model, so those scripts are written per-device. This example is
  the streaming equivalent of simple_block_capture.py: the wrapper owns the
  sequence, the user owns the samples.

Key Concepts:
  - StreamingSession yields chunks: each chunk holds a private numpy copy of
    the new samples per channel, safe to keep or hand to another thread.
  - Chunks arrive in the capture's native dtype (no upcasting) and carry
    over-range, trigger and auto-stop flags.
  - Threaded acquisition: a background thread iterates the session and keeps
    a rolling window of the newest samples; the main thread runs Qt and a
    QTimer refreshes the plot. Chunk copies make this hand-off safe, and
    request_stop() ends the loop safely from the GUI thread.
  - The session surfaces capability walls instead of hiding them: a
    configuration the connected driver cannot express raises PicoSDKException
    at construction rather than degrading silently.
  - Achievable sample rates still differ per device family. The session
    reports the driver's actual interval via actual_sample_interval, which
    this example uses to size the plot window in real time units.

Requirements:
  - Any streaming-capable PicoScope (6000E, 3000E, 5000E, 5000D)
  - Python packages: (pip install) numpy pyqtgraph PyQt5 pypicosdk

Setup:
  - Connect a signal to Channel A (or use the AWG below)
  - Set SCOPE_CLASS to match your device
  - Close the plot window (or Ctrl+C) to stop
"""
import signal
import threading
import time
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
import pypicosdk as psdk


# ============================================================================
# CONFIGURATION
# ============================================================================

SCOPE_CLASS = psdk.ps6000a      # ps6000a / psospa / ps5000a — change this only

SAMPLE_INTERVAL = 1000          # requested interval between samples
TIME_UNITS = psdk.TIME_UNIT.NS  # 1000 ns -> 1 MS/s (driver rounds to nearest)
DATA_TYPE = psdk.DATA_TYPE.INT16_T  # native on every driver
NUMPY_DTYPE = np.int16          # numpy dtype matching DATA_TYPE

PLOT_WINDOW_SECONDS = 0.01      # width of the rolling display window
REFRESH_MS = 60                 # plot refresh interval (milliseconds)


# ============================================================================
# HARDWARE SETUP
# ============================================================================

scope = psdk.psospa()
scope.open_unit()
print(f"Connected to PicoScope: {scope.get_unit_serial()}")

scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Optionally drive a test signal via the built-in AWG
scope.set_siggen(frequency=1e3, pk2pk=1.5, wave_type=psdk.WAVEFORM.SINE)


# ============================================================================
# STREAMING SESSION
# ============================================================================

stream = psdk.StreamingSession(
    scope,
    sample_interval=SAMPLE_INTERVAL,
    time_units=TIME_UNITS,
    datatype=DATA_TYPE,
)

# Start now, on the main thread before the acquisition thread exists, so the
# driver's actual sample interval is known before the plot window is sized
# from it. Every driver call after this happens on the acquisition thread.
stream.start()
actual_interval_s = stream.actual_sample_interval / TIME_UNITS
print(f"Actual sample interval : {stream.actual_sample_interval:.4g} "
      f"(requested {SAMPLE_INTERVAL})")

# Rolling display window, sized in samples from the ACTUAL rate
window_samples = max(int(PLOT_WINDOW_SECONDS / actual_interval_s), 2)
print(f"Plot window            : {window_samples:,} samples "
      f"({PLOT_WINDOW_SECONDS * 1e3:g} ms)")


# ============================================================================
# SHARED STATE (acquisition thread -> plot timer)
# ============================================================================

# The acquisition thread REPLACES `history` with a new array each chunk
# (never mutates it in place), so the plot timer can safely take the
# reference under the lock and use it after release.
history = np.empty(0, dtype=NUMPY_DTYPE)
data_lock = threading.Lock()

total_samples = 0
start_time = time.perf_counter()


def acquisition_thread():
    """Iterate the session, keeping the newest window_samples for display.

    The loop ends when the main thread calls stream.request_stop(): the
    iterator notices the flag within one poll and raises StopIteration.
    The `with` block then guarantees the driver stop runs here, so every
    driver call after start() stays on this one thread.
    """
    global history, total_samples

    try:
        with stream:
            last_print = start_time
            for chunk in stream:
                samples = chunk.data[psdk.CHANNEL.A]
                total_samples += len(samples)

                with data_lock:
                    history = np.concatenate((history, samples))[-window_samples:]

                now = time.perf_counter()
                if now - last_print >= 1.0:
                    rate_ms = total_samples / (now - start_time) / 1e6
                    print(f"  {total_samples:,} samples  "
                          f"({rate_ms:.2f} MS/s average)")
                    last_print = now
    except Exception as e:
        print(f"Acquisition error: {e}")


# ============================================================================
# PYQTGRAPH WINDOW SETUP
# ============================================================================

app = pg.mkQApp("PicoScope Simple Streaming")

win = pg.GraphicsLayoutWidget(title="PicoScope Simple Streaming (StreamingSession)")
win.resize(1_000, 500)
win.show()

ADC_MIN = int(np.iinfo(NUMPY_DTYPE).min)
ADC_MAX = int(np.iinfo(NUMPY_DTYPE).max)

plot = win.addPlot(title="Channel A — StreamingSession live view")
plot.setLabel('left', 'Amplitude', units='ADC counts')
plot.setLabel('bottom', 'Time', units='ms')
plot.showGrid(x=True, y=True)
plot.setYRange(ADC_MIN, ADC_MAX, padding=0.02)
plot.setLimits(yMin=ADC_MIN, yMax=ADC_MAX)
plot.getViewBox().setMouseEnabled(y=False)
plot.setXRange(0, PLOT_WINDOW_SECONDS * 1e3, padding=0)

curve = plot.plot(
    pen=pg.mkPen(color='cyan', width=1),
    clipToView=True,
    autoDownsample=True
)

# Precomputed x-axis for a full window (milliseconds); sliced while filling
x_full = np.arange(window_samples) * actual_interval_s * 1e3


def update_plot():
    """QTimer callback on the main thread: draw the latest rolling window."""
    with data_lock:
        y_data = history   # safe: acquisition replaces, never mutates

    if len(y_data):
        curve.setData(x_full[:len(y_data)], y_data)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

acq_thread = threading.Thread(target=acquisition_thread, daemon=True)
acq_thread.start()

timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(REFRESH_MS)

# Route Ctrl+C to a clean Qt shutdown. Inside pg.exec() the interrupt is only
# delivered when Python code next runs (the QTimer slot above), so without
# this handler it would surface inside the slot and never stop the app.
signal.signal(signal.SIGINT, lambda *args: app.quit())

print("\nStreaming... Close the plot window or press Ctrl+C to stop.\n")

pg.exec()


# ============================================================================
# CLEANUP
# ============================================================================

# request_stop() is the session's thread-safe stop: it only sets a flag, and
# the acquisition thread performs the driver stop on its next poll.
stream.request_stop()
acq_thread.join(timeout=5.0)
if acq_thread.is_alive():
    print("[WARNING] Acquisition thread did not stop cleanly")

scope.close_unit()


# ============================================================================
# SUMMARY
# ============================================================================

elapsed = time.perf_counter() - start_time
print(f"\n{'-' * 50}")
print(f"Samples captured : {total_samples:,} in {elapsed:.2f} s "
      f"({total_samples / elapsed / 1e6:.2f} MS/s)")
print(f"{'-' * 50}")
