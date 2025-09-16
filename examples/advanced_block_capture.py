"""
Advanced block mode example for a Picoscope 6000E device

Description:
  This example script captures a single acquisition with minimal abstraction
  It is intended to demonstrate how to use the pyPicoSDK library to automate
  your Picoscope device

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup:
  - Connect 6000E AWG output to Channel A
    of the oscilloscope using a BNC cable or probe
"""

from matplotlib import pyplot as plt
import pypicosdk as psdk

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 100_000

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Print the returned serial number of the initialized instrument
print(scope.get_unit_serial())

# Set siggen to 50kHz & 1.8Vpkpk output
scope.set_siggen(frequency=50_000, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)

# Enable channel A with +/- 1V range (2V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Configure a simple rising edge trigger for channel A
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(500, psdk.SAMPLE_RATE.MSPS)

# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # set timebase via requested sample interval

# Print to console the actual sample rate selected by the device driver
print(scope.get_actual_sample_rate())

# Create buffers in this application space to hold returned sample array
channels_buffer = scope.set_data_buffer_for_enabled_channels(samples=SAMPLES)

# Run the aqusition using the selected timebase and numbver of samples from above
scope.run_block_capture(timebase=TIMEBASE, samples=SAMPLES)

# Populate the python array with actual ADC values from the device
scope.get_values(SAMPLES)

# Scale the raw ADC values to mV values according to the selected timebase
channels_buffer = scope.adc_to_mv(channels_buffer)

# Create an array of time values in nano seconds, to align with each sample point
time_axis = scope.get_time_axis(TIMEBASE, SAMPLES)

# Release the device from the driver
scope.close_unit()

# Use matplotlib to plot the data
plt.plot(time_axis, channels_buffer[psdk.CHANNEL.A])
plt.title('Example plot for Channel A')
plt.xlabel('Time (ns)')
plt.ylabel('Voltage (mV)')
plt.grid(True)

# Set the Y axis of the graph to the largest voltage range selected for enabled channels, in mV
plt.ylim(scope.get_ylim(unit='mv'))

# Display the completed plot
plt.show()
