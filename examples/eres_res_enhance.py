"""
Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms.

This examples demonstrates how to use a moving average filter (implemented through NumPy.convolve)
as a way to enhance the vertical resolution of a channel.
This example uses a square wave. Matplotlib will display the output showing a blue (original) and
orange (enhanced) waveform.

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib pypicosdk

Setup:
 - Connect:
        Channel A to AWG Ouput via BNC or Probe
"""

from matplotlib import pyplot as plt

import pypicosdk as psdk
from pypicosdk import resolution_enhancement

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 500

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Set siggen to 10MhHz & 3.5Vpkpk output
scope.set_siggen(frequency=10_00_000, pk2pk=3.5, wave_type=psdk.WAVEFORM.SQUARE)

# Enable channel A with +/- 1V range (4V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)

# Configure a simple rising edge trigger for channel A, wait indefinitely (do not auto trigger)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0, auto_trigger=0)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=1.25, unit=psdk.SAMPLE_RATE.GSPS)

# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # set timebase via requested sample interval

# Print to console the actual sample rate selected by the device driver
print(scope.get_actual_sample_rate())

# Create buffers in this application space to hold returned sample array
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Create a duplicate channel_buffer array after applying the moving average enhancement technique
# in a new array named enhanced_buffer
enhanced_buffer = resolution_enhancement(channel_buffer[psdk.CHANNEL.A], enhanced_bits=2, padded=False)

# Finish with PicoScope
scope.close_unit()

# Create subplots: Top = Raw buffer, Bottom = Enhanced buffer
fig, ax = plt.subplots(figsize=(10, 6))

# Raw buffer
ax.plot(channel_buffer[psdk.CHANNEL.A], marker='x', label="Raw Buffer", alpha=0.7)

# Enhanced buffer
ax.plot(enhanced_buffer, marker='x', label="Enhanced Buffer", color="orange", alpha=0.7)

# Labels, title and layout
ax.set_xlabel("Time (ns)")
ax.set_ylabel("Amplitude (mV)")
ax.set_title("Raw vs Resolution Enhanced Buffer")
ax.grid(True)
ax.legend()
plt.tight_layout()

# Set the Y axis of the graph to the largest voltage range selected for enabled channels, in mV
plt.ylim(scope.get_ylim(unit='mv'))

# Display the plot
plt.show()
