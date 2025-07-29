"""Simple frequency measurement using a block capture.
Measures the signal frequency by averaging time between zero crossings.
"""
import numpy as np
import pypicosdk as psdk
from matplotlib import pyplot as plt

# Capture configuration
SAMPLES = 5_000_000
SAMPLE_RATE = 500  # in MS/s
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1
THRESHOLD = 0
HYSTERESIS_MV = 10


def zero_crossings(data: np.ndarray, hysteresis: float = 0.0) -> np.ndarray:
    """Return indices of zero crossings in ``data`` with optional hysteresis."""

    centered = data - data.mean()
    if hysteresis <= 0:
        return np.where(np.diff(np.sign(centered)))[0]

    sign = 1 if centered[0] >= 0 else -1
    crossings = []
    for i, value in enumerate(centered[1:], 1):
        if sign >= 0 and value <= -hysteresis:
            sign = -1
            crossings.append(i - 1)
        elif sign <= 0 and value >= hysteresis:
            sign = 1
            crossings.append(i - 1)
    return np.asarray(crossings, dtype=int)


def measure_frequency(
    data: np.ndarray, sample_rate: float, hysteresis: float = 0.0
) -> float:
    """Return the average frequency of ``data`` in Hz.

    Args:
        data: Waveform samples.
        sample_rate: Sampling rate in samples per second.
        hysteresis: Threshold for zero crossing detection in mV.
    """

    crossings = zero_crossings(data, hysteresis)
    if len(crossings) < 3:
        return float("nan")
    # Use every other crossing to avoid measuring half periods
    periods = (crossings[2:] - crossings[:-2]) / sample_rate
    return float(1 / periods.mean())


# Initialize PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup channel and trigger
scope.set_channel(channel=CHANNEL, range=RANGE)
scope.set_simple_trigger(channel=CHANNEL, threshold_mv=THRESHOLD)

scope.set_siggen(0.05E6, 1.0, psdk.WAVEFORM.SINE)

# Convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(SAMPLE_RATE, psdk.SAMPLE_RATE.MSPS)

# Run block capture
channels_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Close connection to PicoScope
scope.close_unit()

# Extract waveform and measure frequency using the actual sample rate
waveform = channels_buffer[CHANNEL]

# Calculate sample rate from returned time axis (ns)
actual_sample_rate = 1e9 / (time_axis[1] - time_axis[0])

freq_value = measure_frequency(waveform, actual_sample_rate, HYSTERESIS_MV)

print(f"Measured frequency: {freq_value/1e6:.2f} MHz")

# Display waveform
plt.plot(time_axis, waveform)
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.title("Captured Waveform")
plt.show()