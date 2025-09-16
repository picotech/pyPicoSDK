"""
This example displays the dead time between consecutive rapid block captures using a
PicoScope. The script configures a signal generator to output a square wave, sets up a
single-channel capture with a trigger, and collects multiple captures in rapid succession.
It then retrieves trigger timing information to calculate and plot the dead time between
captures.

Setup:
 - Connect Channel A to AWG Output

Notes:
 - Pico examples use inline argument values for clarity
"""
from matplotlib import pyplot as plt
import numpy as np
import pypicosdk as psdk

# Create a local variable to hold number of samples for use in later functions
SAMPLES = 1000

# Create a local variable to hold number of captures for use in
# run_simple_rapid_block_capture helper function
CAPTURES = 20

# Initialize scope
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=20E6, pk2pk=3, wave_type=psdk.WAVEFORM.SQUARE)

# Enable channel A with +/- 2V range (4V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)

# Configure a simple rising edge trigger for channel A
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Print to console the actual sample rate selected by the device driver
print(scope.get_actual_sample_rate())

<<<<<<< Updated upstream
# Perform rapid block capture via help function
# (inc. buffer setup, time axix mV conversion etc.)
=======
# Perform rapid block capture via help function (inc. buffer setup, time axis mV conversion etc.)
>>>>>>> Stashed changes
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    captures=CAPTURES,
)

# Retrieve trigger timing information for each capture into a python dict.
# Note: In this example we do not actually puul the full sample data, only trigger info
trigger_info = scope.get_trigger_info(0, CAPTURES)

# Release the device from the driver
scope.close_unit()

# Calculate time between captures using the time axis to derive actual sample interval and count
sample_interval_ns = np.diff(time_axis)[0]
actual_samples = time_axis.size

# Create a list to store calculated dead times (ns) between consecutive captures
dead_times = []
for prev, curr in zip(trigger_info[:-1], trigger_info[1:]):
    # Calculate the difference in timestamp counter values between successive captures,
    # applying a bitmask to handle counter wrap-around as suggested in API guide (Time stamping)
    diff_samples = (
        int(curr["timeStampCounter"]) - int(prev["timeStampCounter"])
    ) & psdk.TIMESTAMP_COUNTER_MASK

    # Subtract the actual sample count to isolate the dead time in sample units
    dead_samples = diff_samples - actual_samples

    # Convert dead time from samples to nanoseconds and append to the list
    dead_times.append(dead_samples * sample_interval_ns)

# Print the calculated dead times for each pair of consecutive captures
print("Dead time between captures (ns):")
for i, dt in enumerate(dead_times, start=1):
    print(f"{i}->{i+1}: {dt:.2f}")

# setup and display dead time versus capture index for visual analysis
plt.plot(range(1, CAPTURES), dead_times, marker="x")
plt.xlabel("Capture index")
plt.ylabel("Dead time (ns)")
plt.title("Dead time between captures")
plt.grid(True)
plt.show()