"""
This example displays the dead time between consecutive rapid block captures using a
PicoScope. The script configures a signal generator to output a square wave, sets up a
single-channel capture with a trigger, and collects multiple captures in rapid succession.
It then retrieves trigger timing information to calculate and plot the dead time between
captures.

Setup:
 - Connect Channel A to AWG Ouput

Notes:
 - Pico examples use inline argument values for clarity
"""
from matplotlib import pyplot as plt
import numpy as np
import pypicosdk as psdk

# Capture configuration
SAMPLES = 1000
CAPTURES = 20

# Initialize scope
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=20E6, pk2pk=3, wave_type=psdk.WAVEFORM.SQUARE)

# Configure channel and trigger
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Convert desired sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)

# Perform rapid block capture
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    captures=CAPTURES,
)

# Retrieve trigger timing information for each segment
trigger_info = scope.get_trigger_info(0, CAPTURES)

scope.close_unit()

# Calculate dead time between captures
# Use the returned time axis to derive the actual sample interval and count
sample_interval_ns = np.diff(time_axis)[0]
actual_samples = time_axis.size

dead_times = []
for prev, curr in zip(trigger_info[:-1], trigger_info[1:]):
    diff_samples = (
        int(curr["timeStampCounter"]) - int(prev["timeStampCounter"])
    ) & psdk.TIMESTAMP_COUNTER_MASK
    dead_samples = diff_samples - actual_samples
    dead_times.append(dead_samples * sample_interval_ns)

print("Dead time between captures (ns):")
for i, dt in enumerate(dead_times, start=1):
    print(f"{i}->{i+1}: {dt:.2f}")

plt.plot(range(1, CAPTURES), dead_times, marker="o")
plt.xlabel("Capture index")
plt.ylabel("Dead time (ns)")
plt.title("Dead time between captures")
plt.grid(True)
plt.show()