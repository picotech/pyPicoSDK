"""
This examples shows how to use the eRes or resolution enhancement on a square helo
wave. Pyplot will display the output showing a blue (origional) and orange
(enhanced) waveform.

Setup:
 - Connect:
        Channel A to AWG Ouput via BNC or Probe
"""

from matplotlib import pyplot as plt

import pypicosdk as psdk
from pypicosdk import resolution_enhancement

# Capture configuration
SAMPLES = 500

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=10_00_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SQUARE)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=1.25, unit=psdk.SAMPLE_RATE.GSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)
enhanced_buffer = resolution_enhancement(channel_buffer[psdk.CHANNEL.A], enhanced_bits=2)

# Finish with PicoScope
scope.close_unit()

# Create subplots: Top = Raw buffer, Bottom = Enhanced buffer
fig, ax = plt.subplots(figsize=(10, 6))

# Raw buffer
ax.plot(channel_buffer[psdk.CHANNEL.A], marker='x', label="Raw Buffer", alpha=0.7)

# Enhanced buffer
ax.plot(enhanced_buffer, marker='x', label="Enhanced Buffer", color="orange", alpha=0.7)

# Labels and title
ax.set_xlabel("Time (ns)")
ax.set_ylabel("Amplitude (mV)")
ax.set_title("Raw vs Resolution Enhanced Buffer")
ax.grid(True)
ax.legend()

plt.tight_layout()
plt.show()
