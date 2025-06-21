import pypicosdk as psdk
from matplotlib import pyplot as plt

# Configuration
TIMEBASE = 2
SAMPLES = 1000
CAPTURES = 4
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1

# Initialise device
scope = psdk.ps6000a()
scope.open_unit()

# Setup capture parameters
scope.set_channel(channel=CHANNEL, range=RANGE)
scope.set_simple_trigger(channel=CHANNEL, threshold_mv=0)

# Run rapid block capture
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    n_captures=CAPTURES,
)

scope.close_unit()

# Plot the first capture as an example
plt.plot(time_axis, buffers[CHANNEL][0])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()
