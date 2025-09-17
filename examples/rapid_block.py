"""
Rapid block capture example for a PicoScope 6000E device

Description:
  Demonstrates capturing multiple waveforms in rapid block mode and
  overlaying the results on a single plot.

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
SAMPLES = 1000

# Create a local variable to hold number of captures for use in
# run_simple_rapid_block_capture helper function
CAPTURES = 20

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Setup capture parameters (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Set siggen to 100kHz & 0.8Vpkpk output sine wave
scope.set_siggen(frequency=100_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SINE)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # set timebase via requested sample interval

# Print to console the actual sample rate selected by the device driver
print(scope.get_actual_sample_rate())

# Perform rapid block capture via help function (inc. buffer setup, time axis mV conversion etc.)
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    captures=CAPTURES,
)

# Release the device from the driver
scope.close_unit()

# Overlay all captures on a single plot
for wf in buffers[psdk.CHANNEL.A]:
    plt.plot(time_axis, wf, alpha=0.3)
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()
