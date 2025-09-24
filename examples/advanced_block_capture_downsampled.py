"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Advanced block mode example for a Picoscope 6000E device (downsampled data)

Description:
  This example mirrors the basic advanced block example but retrieves
  downsampled data (e.g., averaged) from the driver instead of raw samples.

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup:
  - Connect 6000E AWG output to Channel A
    of the oscilloscope using a BNC cable or probe
"""

from matplotlib import pyplot as plt
import numpy as np
import pypicosdk as psdk

# Number of raw samples to request from the driver before downsampling
SAMPLES = 100_000

# Configure downsampling
# Ratio of raw samples per output sample and the mode applied by the driver
DOWNSAMPLE_RATIO = 10
RATIO_MODE = psdk.RATIO_MODE.DECIMATE  # alternatives: RAW, DECIMATE, AGGREGATE, TRIGGER

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Print the returned serial number of the initialized instrument
print(scope.get_unit_serial())

# Set siggen to 50kHz & 1.8Vpkpk output sine wave
scope.set_siggen(frequency=50_000, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)

# Enable channel A with +/- 1V range (2V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Configure a simple rising edge trigger for channel A, wait indefinitely (do not auto trigger)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0, auto_trigger=0)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Print to console the actual sample rate selected by the device driver
raw_sample_rate = scope.get_actual_sample_rate()
print(raw_sample_rate)

# Set up buffers for both raw and downsampled data
raw_buffers = scope.set_data_buffer_for_enabled_channels(
    samples=SAMPLES,
    ratio_mode=psdk.RATIO_MODE.RAW,
)

downsampled_buffers = scope.set_data_buffer_for_enabled_channels(
    samples=SAMPLES,
    ratio_mode=RATIO_MODE,
    clear_buffer=False,  # Don't clear the raw buffers
)

# Run single acquisition
scope.run_block_capture(timebase=TIMEBASE, samples=SAMPLES)

# Get raw data from the acquisition
raw_samples = scope.get_values(SAMPLES, ratio=0, ratio_mode=psdk.RATIO_MODE.RAW)

# Get downsampled data from the same acquisition
downsampled_samples = scope.get_values(SAMPLES, ratio=DOWNSAMPLE_RATIO, ratio_mode=RATIO_MODE)

# Convert both datasets to mV
raw_buffers = scope.adc_to_mv(raw_buffers)
downsampled_buffers = scope.adc_to_mv(downsampled_buffers)

# Build a time axis in nano seconds on the raw-sample grid (length SAMPLES)
time_axis = scope.get_time_axis(TIMEBASE, SAMPLES)

# Realign downsampled samples into sparse arrays with initialized with NaNs to visualize gaps
expanded_buffers = scope.realign_downsampled_data(
    downsampled_buffers=downsampled_buffers,
    total_raw_samples=SAMPLES,
    returned_samples=downsampled_samples,
    ratio=DOWNSAMPLE_RATIO,
    ratio_mode=RATIO_MODE,
)

# Release the device from the driver
scope.close_unit()

# Use matplotlib to setup the graph and plot the data
plt.plot(time_axis, raw_buffers[psdk.CHANNEL.A], label='Raw data', color='lightblue')
plt.plot(time_axis, expanded_buffers[psdk.CHANNEL.A], marker='x', label='Downsampled', color='red')
plt.title('Raw vs Downsampled plot for channel A')
plt.xlabel('Time (ns)')
plt.ylabel('Voltage (mV)')
plt.legend()
plt.grid(True)

# Set the Y axis of the graph to the largest voltage range selected for enabled channels, in mV
plt.ylim(scope.get_ylim(unit='mv'))

# Display the completed plot
plt.show()
