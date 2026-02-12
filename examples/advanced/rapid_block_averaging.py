"""
Copyright (C) 2026 Pico Technology Ltd. See LICENSE file for terms.

Averaging example for a PicoScope 6000E device.

Description:
    This example captures multiple waveforms in rapid block mode and then
    averages them to a single dimension array. The averaged buffer is then
    plotted along with the original rapid block captures.

Requirements:
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup:
  - Connect Channel A to the AWG output
"""

from matplotlib import pyplot as plt
import numpy as np
import pypicosdk as psdk

# Setup the capture parameters
SAMPLES = 1000
CAPTURES = 20

# Initialize the scope
scope = psdk.ps6000a()
scope.open_unit()

# Setup the scope to the same settings as the rapid_block.py example
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold=0, auto_trigger=0)
scope.set_siggen(frequency=100_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SINE)
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Run the rapid block capture
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    captures=CAPTURES,
)

print('Channel A shape:', buffers[psdk.CHANNEL.A].shape)

# Average all rapid block captures for each channel to a single dimension array
averaged_buffer = np.mean(buffers[psdk.CHANNEL.A], axis=0)

print('Averaged buffer shape:', averaged_buffer.shape)

# Close the scope
scope.close_unit()

# Plot all rapid block captures for each channel
for wf in buffers[psdk.CHANNEL.A]:
    plt.plot(time_axis, wf, alpha=0.1)

# Plot the averaged buffer
plt.plot(time_axis, averaged_buffer)

# Add labels to the plot
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()
