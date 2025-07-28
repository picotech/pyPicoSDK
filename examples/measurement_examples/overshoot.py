"""Simple amplitude measurement using a block capture.
Uses histogram-based top and base functions to provide a robust amplitude
measurement. The script can also calculate RMS amplitude.
"""
import numpy as np
import pypicosdk as psdk
from matplotlib import pyplot as plt


# Capture configuration
SAMPLES = 5_000
SAMPLE_RATE = 500  # in MS/s
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1
BINS = 32
THRESHOLD = 0


def top(data):
    # Return the "Top" mode of the data

    # Sort and get upper 40% of samples
    data = np.sort(data)
    data = data[int(len(data) * 0.6) :]

    # Build histogram and get max counts
    counts, bin_edges = np.histogram(data, bins=BINS)
    mode_bin_index = np.argmax(counts)

    # Get upper and lower edges of bins
    lbe = bin_edges[mode_bin_index]
    upe = bin_edges[mode_bin_index + 1]

    # Get data between the bin edges
    filtered = data[(data >= lbe) & (data <= upe)]

    # Return the average of samples between bin edges
    return float(filtered.mean())

def base(data):
    # Return the "Base" mode of the data

    # Sort and get lower 40% of samples
    data = np.sort(data)
    data = data[: int(len(data) * 0.4)]

    # Build histogram and get max counts
    counts, bin_edges = np.histogram(data, bins=BINS)
    mode_bin_index = np.argmax(counts)

    # Get upper and lower edges of bins
    lbe = bin_edges[mode_bin_index]
    upe = bin_edges[mode_bin_index + 1]

    # Get data between the bin edges
    filtered = data[(data >= lbe) & (data <= upe)]
    
    # Return the average of samples between bin edges
    return float(filtered.mean())

def max_value(data):
    return np.max(data)

def min_value(data):
    return np.min(data)

def positive_overshoot_filtered(data):
    return  (max_value(data) - top(data))  / max_value(data) * 100

def negative_overshoot_filtered(data):
    return (min_value(data) - base(data)) / min_value(data) * 100

# Initialize PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup channel and trigger
scope.set_channel(channel=CHANNEL, range=RANGE)
scope.set_simple_trigger(channel=CHANNEL, threshold_mv=THRESHOLD)

scope.set_siggen(1E6, 1.6, psdk.WAVEFORM.SQUARE)

# Convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(SAMPLE_RATE, psdk.SAMPLE_RATE.MSPS)

# Run block capture
channels_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Close connection to PicoScope
scope.close_unit()

# Extract waveform and measure amplitude
waveform = (channels_buffer[CHANNEL])

pos_over = positive_overshoot_filtered(waveform)
neg_over = negative_overshoot_filtered(waveform)

print(f"Positive overshoot: {pos_over:.2f} %")
print(f"Negative overshoot: {neg_over:.2f} %")

# Display waveform
plt.plot(time_axis, waveform)
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.title("Captured Waveform")
plt.show()