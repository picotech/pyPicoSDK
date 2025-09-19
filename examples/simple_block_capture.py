"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Simple block capture example for a PicoScope 6000E device

Description:
  Demonstrates how to perform a basic block capture using pyPicoSDK.

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib pypicosdk

Setup:
  - Connect Channel A to the AWG output
"""
from matplotlib import pyplot as plt
import pypicosdk as psdk

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 5_000

# Create "scope" class and initialize PicoScope
scope = psdk.psospa()
scope.open_unit()

# Print the returned serial number of the initialized instrument
print(scope.get_unit_serial())

# Set siggen to 1MHz & 0.8Vpkpk output sine wave
scope.set_siggen(frequency=1_000_000, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)

# Enable channel A with +/- 1V range (2V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Configure a simple rising edge trigger for channel A, wait indefinitely (do not auto trigger)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0, auto_trigger=0)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # set timebase via requested sample interval

# Print to console the actual sample rate selected by the device driver
print(scope.get_actual_sample_rate())

# Perform simple block capture via help function (inc. buffer setup, time axis, mV conversion etc.)
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# time_base, unit = scope.get_time_axis(...)

# Release the device from the driver
scope.close_unit()

# Use matplotlib to setup the graph and plot the data
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)

# Set the Y axis of the graph to the largest voltage range selected for enabled channels, in mV
plt.ylim(scope.get_ylim(unit='mv'))

# Display the completed plot
plt.show()
