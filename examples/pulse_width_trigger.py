"""
Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms.

Pulse width trigger example using advanced trigger mode.
This script demonstrates configuring a pulse width qualifier to trigger when a high pulse
on Channel A exceeds a user-defined width. The width is specified using
:class:`pypicosdk.TIME_UNIT` in the same way as sample rates use :class:`pypicosdk.SAMPLE_RATE`.
"""

import pypicosdk as psdk
from matplotlib import pyplot as plt

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 1000

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Generate a square wave and loopback to Channel A.
# By default this example is set to an output frequency of 1MHz - a high pulse width of 500ns
# as such, the script will not trigger by default.
# To create a pulse width trigger condition, decrease the "time_lower" arg to <= 500ns OR adjust
# the output frequency to within the conditions set in set_pulse_width_trigger()
scope.set_siggen(frequency=1_000_000, pk2pk=2.0, wave_type=psdk.WAVEFORM.SQUARE)

# Enable channel A with +/- 2V range (4V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)

# Convert desired sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

scope.set_pulse_width_trigger(
    channel=psdk.CHANNEL.A,
    timebase=TIMEBASE,
    samples=SAMPLES,
    time_lower=600,
    threshold_lower_mv=0,
    threshold_upper_mv=0,
    time_lower_units=psdk.TIME_UNIT.NS,
    direction=psdk.THRESHOLD_DIRECTION.RISING,
    pulse_width_type=psdk.PULSE_WIDTH_TYPE.GREATER_THAN
)

# Perform simple block capture via help function (inc. buffer setup, time axis, mV conversion etc.)
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES, pre_trig_percent=50)

# Release the device from the driver
scope.close_unit()

# Use matplotlib to plot the data
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()