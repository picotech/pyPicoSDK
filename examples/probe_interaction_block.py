"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Probe interaction callback example for a PicoScope 6000E device

Description:
  Demonstrates how to register a probe interaction callback so your
  application is notified whenever an intelligent probe is connected or
  disconnected.  After the callback fires, a simple block capture is
  performed on Channel A.

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib pypicosdk

Setup:
  - Connect an intelligent PicoConnect probe to Channel A
"""
import time

from matplotlib import pyplot as plt
import pypicosdk as psdk

SAMPLES = 5_000


def on_probe_event(handle, status, probes, n_probes):
    """Callback invoked by the driver when a probe change is detected."""
    for i in range(n_probes):
        probe = probes[i]
        if probe.connected_:
            print(f"Probe connected on channel {probe.channel_}")
        else:
            print(f"Probe disconnected on channel {probe.channel_}")


scope = psdk.ps6000a()
scope.open_unit()

print(scope.get_unit_serial())

# Register the probe interaction callback immediately after opening the unit
scope.set_probe_interaction_callback(on_probe_event)

# Allow time for the initial probe callback events to fire
time.sleep(1.0)

# Enable channel A with +/- 1V range
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Configure a simple rising edge trigger on channel A
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold=0, auto_trigger=0)

# Set sample rate to 50 MS/s
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Perform a simple block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

scope.close_unit()

plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.ylim(scope.get_ylim())
plt.show()
