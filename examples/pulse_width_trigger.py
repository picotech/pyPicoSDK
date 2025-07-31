"""Pulse width trigger example using advanced trigger mode.
This script demonstrates configuring a pulse width qualifier to
trigger when a high pulse on Channel A exceeds a user-defined width.
The width is specified using :class:`pypicosdk.TIME_UNIT` in the same
way as sample rates use :class:`pypicosdk.SAMPLE_RATE`.
"""

import pypicosdk as psdk
from matplotlib import pyplot as plt

# Capture configuration
SAMPLES = 100_000
SAMPLE_RATE = 50  # in MS/s
PULSE_WIDTH = 600  # pulse width threshold
PULSE_WIDTH_UNIT = psdk.TIME_UNIT.US

# Initialize PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Generate a square wave and loopback to Channel A. This example will not trigger > 900 Hz
scope.set_siggen(frequency=800, pk2pk=2.0, wave_type=psdk.WAVEFORM.SQUARE)

# Enable Channel A and configure an advanced trigger
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)

# Convert desired sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(SAMPLE_RATE, psdk.SAMPLE_RATE.MSPS)

scope.set_pulse_width_trigger(
    channel=psdk.CHANNEL.A,
    timebase=TIMEBASE,
    samples=SAMPLES,
    time_lower=PULSE_WIDTH,
    threshold_lower_mv=0,
    threshold_upper_mv=0,
    time_lower_units=PULSE_WIDTH_UNIT,
    direction=psdk.THRESHOLD_DIRECTION.RISING,
    pulse_width_type=psdk.PULSE_WIDTH_TYPE.GREATER_THAN
)

# Run capture and retrieve data
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Close PicoScope connection
scope.close_unit()

# Plot captured waveform
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A])

# Draw trigger line on graph
plt.axvline(time_axis[int(SAMPLES/2)], color='r')
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()