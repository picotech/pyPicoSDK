"""Simple frequency measurement using a block capture.
Measures the signal frequency by averaging time between zero crossings.
"""
import numpy as np
import pypicosdk as psdk
from matplotlib import pyplot as plt

# Capture configuration
SAMPLES = 5_000
SAMPLE_RATE = 500  # in MS/s
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1
THRESHOLD = 0


def zero_crossings(data: np.ndarray) -> np.ndarray:
    """Return indices of zero crossings in ``data``."""

    centered = data - data.mean()
    return np.where(np.diff(np.signbit(centered)))[0]


def measure_frequency(data: np.ndarray, sample_rate: float) -> float:
    """Return the average frequency of ``data`` in Hz."""

    crossings = zero_crossings(data)
    if len(crossings) < 2:
        return float("nan")
    periods = np.diff(crossings) / sample_rate
    return float(1 / periods.mean())


# Initialize PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup channel and trigger
scope.set_channel(channel=CHANNEL, range=RANGE)
scope.set_simple_trigger(channel=CHANNEL, threshold_mv=THRESHOLD)

scope.set_siggen(1E6, 1.0, psdk.WAVEFORM.SINE)

# Convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(SAMPLE_RATE, psdk.SAMPLE_RATE.MSPS)

# Run block capture
channels_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Close connection to PicoScope
scope.close_unit()

# Extract waveform and measure frequency
waveform = channels_buffer[CHANNEL]

freq_value = measure_frequency(waveform, SAMPLE_RATE * 1e6)

print(f"Measured frequency: {freq_value/1e6:.2f} MHz")

# Display waveform
plt.plot(time_axis, waveform)
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.title("Captured Waveform")
plt.show()