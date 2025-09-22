"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Auxiliary trigger example for a Picoscope 6000E device

Description:
  This example script captures a single aqusition with minimal abstraction
  It is intended to demonstrate how to use the pyPicoSDK librarby to automate
  your Picoscope device

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup:
  - Connect 6000E AWG output to AUX trig input & Channel A
    of the oscilloscope using a tee BNC connector / cable or probe
"""

import pypicosdk as psdk
from matplotlib import pyplot as plt

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 50_000

# Create "scope" class and initialise PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Set siggen to 1KHz & 3Vpkpk output
# For this demo, split SigGen output to TRIGGER_AUX and Channel A input
scope.set_siggen(frequency=1e6, pk2pk=3, wave_type=psdk.WAVEFORM.SINE)

# Enable Channel A and set range to +/ 2V (4V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)

# Configure an advanced trigger using the AUX input
# Threshold parameters are ignored when using AUX trig input (fixed 1.25 V threshold)
scope.set_advanced_trigger(
    channel=psdk.CHANNEL.TRIGGER_AUX,
    state=psdk.TRIGGER_STATE.TRUE,
    direction=psdk.THRESHOLD_DIRECTION.RISING,
    threshold_mode=psdk.THRESHOLD_MODE.LEVEL,
    threshold_upper_mv=0,                           # Required by driver despite fixed threshold
    threshold_lower_mv=0,                           # Required by driver despite fixed threshold
)

# Helper function to set timebase of scope by sample rate
TIMEBASE = scope.sample_rate_to_timebase(500, psdk.SAMPLE_RATE.MSPS)


# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # Direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # Set timebase via requested sample interval

# Helper function which sets up buffers for time axis and samples automatically and returns mV values
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Release the device from the driver
scope.close_unit()

# Use matplotlib to plot the data
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A], label="Channel A")
plt.title('Example plot for Channel A using AUX trigger')
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)

# Set the Y axis of the graph to the largest voltage range selected for enabled channels, with mV units
plt.ylim(scope.get_ylim(unit='mv'))

# Display the completed plot
plt.show()
