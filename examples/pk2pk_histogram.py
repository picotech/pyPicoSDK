"""
Histogram example for a PicoScope 6000E.

Description:
  This example script captures multiple signals and displays
  a histogram of captured peak-to-peak (pk2pk) values.

Requirements:
- PicoScope 6000E
- Python packages:
  pip install matplotlib scipy numpy pypicosdk

Setup:
  - Connect 6000E (preferebly with FlexRes) SigGen (AWG) to
    Channel A of the oscilloscope using a BNC cable or probe
"""
import matplotlib.pyplot as plt
import numpy as np
import pypicosdk as psdk

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 500

# Create a local variable to hold number of captures for use in
# run_simple_rapid_block_capture helper function
CAPTURES = 1000

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit(resolution="12bit")

# Enable channel A with +/- 500mV range (1V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, coupling=psdk.COUPLING.DC, range=psdk.RANGE.mV500)

# Configure a simple rising edge trigger for channel A
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=200,
                         direction=psdk.TRIGGER_DIR.RISING, auto_trigger=0)

# Set siggen to 10MHz & 0.9Vpkpk output sine wave
scope.set_siggen(frequency=10_000_000, pk2pk=0.9, wave_type=psdk.WAVEFORM.SINE)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(1.25, psdk.SAMPLE_RATE.GSPS)

# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # set timebase via requested sample interval

# Perform rapid block capture via help function (inc. buffer setup, time axix mV conversion etc.)
channel_buffer, time_axis = scope.run_simple_rapid_block_capture(TIMEBASE, SAMPLES, CAPTURES)

# Extract channel A waveforms from NumPy array which holds both sample and time data
waveforms = channel_buffer[psdk.CHANNEL.A]

# Use numpy to generate pk2pk values per capture (using axis=1)
pk2pk_values = np.ptp(waveforms, axis=1)

# Calculate statistics
print(f"Mean Pk-Pk: {np.mean(pk2pk_values):.2f} mV")
print(f"Std Dev Pk-Pk: {np.std(pk2pk_values):.2f} mV")

# Setup matplotlib subplots
fig, axs = plt.subplots(2, 1, figsize=(10, 8))

# Top subplot: Overlay of all waveforms
for waveform in waveforms:
    axs[0].plot(time_axis, waveform, alpha=0.3)
axs[0].set_xlabel("Time (ns)")
axs[0].set_ylabel("Amplitude (mV)")
axs[0].set_title(f"Overlay of {CAPTURES} Waveforms")
axs[0].grid(True)

# Bottom subplot: Histogram of pk2pk values
axs[1].hist(pk2pk_values, bins=20, edgecolor='black')
axs[1].set_xlabel("Peak-to-Peak Voltage (mV)")
axs[1].set_ylabel("Count")
axs[1].set_title(f"Histogram of Pk-Pk over {CAPTURES} Captures")
axs[1].grid(True)

# Display pyplot
plt.tight_layout()
plt.show()
