"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Simple frequency measurement using a block capture.
Measures the signal frequency by averaging time between zero crossings.
"""
from measurements import measure_frequency

from matplotlib import pyplot as plt
import pypicosdk as psdk

# Capture configuration
SAMPLES = 5_000_000
SAMPLE_RATE = 500  # in MS/s
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1
THRESHOLD = 0
HYSTERESIS_MV = 10

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
