"""Continuous streaming example using threading to update a live plot.

This version adds various helpers to aid debugging of high CPU or memory
usage when streaming large amounts of data. It also drives the built-in
signal generator with a simple sine wave so data appears on-screen.
"""

import logging
import tracemalloc

import matplotlib
backend = matplotlib.get_backend()
print(f"Matplotlib backend: {backend}")
if backend not in matplotlib.rcsetup.interactive_bk:
    matplotlib.use("TkAgg")

import pypicosdk as psdk
from matplotlib import pyplot as plt
from collections import deque
from queue import Queue, Empty, Full
import threading
import time
import psutil

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
tracemalloc.start()
process = psutil.Process()

# Setup variables
sample_interval = 1
sample_units = psdk.PICO_TIME_UNIT.US
plot_samples = 5000  # samples shown on screen
chunk_samples = 1000  # number of samples to read per iteration
channel_a = psdk.CHANNEL.A
voltage_range = psdk.RANGE.V1

# SigGen variables
siggen_frequency = 1000  # Hz
siggen_pk2pk = 2  # Volts peak-to-peak

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Output a sine wave to help visualise captured data
scope.set_siggen(siggen_frequency, siggen_pk2pk, psdk.WAVEFORM.SINE)

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=voltage_range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=0)

# Allocate a buffer for streaming
# The same buffer is reused on every read so we don't need to re-register it
channels_buffer = scope.set_data_buffer_for_enabled_channels(chunk_samples)

# Start streaming with FIFO up to 4G samples
auto_stop = 0
actual_interval = scope.run_streaming(
    sample_interval,
    sample_units,
    0,
    4_000_000_000,
    auto_stop,
    1,
    psdk.RATIO_MODE.RAW,
)

seconds_per_sample = {
    psdk.PICO_TIME_UNIT.FS: 1e-15,
    psdk.PICO_TIME_UNIT.PS: 1e-12,
    psdk.PICO_TIME_UNIT.NS: 1e-9,
    psdk.PICO_TIME_UNIT.US: 1e-6,
    psdk.PICO_TIME_UNIT.MS: 1e-3,
    psdk.PICO_TIME_UNIT.S: 1,
}[sample_units] * actual_interval

# Thread-safe queue and stop event for asynchronous streaming
# Bounded queue helps catch situations where data production outpaces consumption
data_queue: Queue[list] = Queue(maxsize=100)
stop_event = threading.Event()


def streaming_worker() -> None:
    """Continuously read streaming data into a queue."""
    trig_info = psdk.PICO_STREAMING_DATA_TRIGGER_INFO()
    try:
        while not stop_event.is_set():
            available = scope.no_of_streaming_values()
            if available == 0:
                time.sleep(0.01)
                continue

            to_read = min(available, chunk_samples)
            data_array = (psdk.PICO_STREAMING_DATA_INFO * 1)()
            data_array[0].channel_ = channel_a
            data_array[0].mode_ = psdk.RATIO_MODE.RAW
            data_array[0].type_ = psdk.DATA_TYPE.INT16_T
            data_array[0].noOfSamples_ = to_read
            data_array[0].bufferIndex_ = 0
            data_array[0].startIndex_ = 0
            data_array[0].overflow_ = 0

            scope.get_streaming_latest_values(data_array, trig_info)
            num = data_array[0].noOfSamples_
            if num:
                mv = [
                    scope.adc_to_mv(sample, voltage_range)
                    for sample in channels_buffer[channel_a][:num]
                ]
                try:
                    data_queue.put(mv, timeout=0.1)
                except Full:
                    logging.warning("Data queue full - dropping samples")
                else:
                    logging.info(
                        "read %d samples, queue size=%d", num, data_queue.qsize()
                    )
    except Exception:  # pragma: no cover - debug helper only
        logging.exception("Error in streaming_worker")


worker = threading.Thread(target=streaming_worker, daemon=True)
worker.start()

# Setup matplotlib for interactive plotting
plt.ion()
fig, ax = plt.subplots()
(line,) = ax.plot([], [])
plt.show(block=False)
ax.set_xlabel("Time (s)")
ax.set_ylabel("Amplitude (mV)")
ax.grid(True)

# Rolling buffers for plot data
time_axis = deque(maxlen=plot_samples)
values = deque(maxlen=plot_samples)

collected = 0

try:
    while True:
        try:
            data_chunk = data_queue.get(timeout=0.1)
        except Empty:
            plt.pause(0.001)
            continue

        for sample in data_chunk:
            time_axis.append(collected * seconds_per_sample)
            values.append(sample)
            collected += 1

        line.set_data(list(time_axis), list(values))
        if time_axis:
            ax.set_xlim(time_axis[0], time_axis[-1])
        if collected % 1000 == 0:
            cpu = psutil.cpu_percent()
            mem = process.memory_info().rss / (1024**2)
            current, peak = tracemalloc.get_traced_memory()
            logging.info(
                "CPU %.1f%% RSS %.1f MiB (current %.1f MiB, peak %.1f MiB)",
                cpu,
                mem,
                current / (1024**2),
                peak / (1024**2),
            )
        plt.pause(0.001)
except KeyboardInterrupt:
    pass
finally:
    stop_event.set()
    worker.join()

# Finish with PicoScope
scope.close_unit()
plt.ioff()
plt.show()
