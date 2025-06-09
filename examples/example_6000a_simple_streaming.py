import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup parameters
sample_interval = 10  # in nanoseconds
samples = 5000
channel = psdk.CHANNEL.A
rng = psdk.RANGE.V1

# Initialise
scope = psdk.ps6000a()
scope.open_unit()

# Channel and trigger
scope.set_channel(channel=channel, range=rng)
scope.set_simple_trigger(channel=channel, threshold_mv=0)

# Run streaming capture
buffers, time_axis = scope.run_simple_streaming_capture(
    sample_interval,
    psdk.PICO_TIME_UNIT.NS,
    samples,
)

scope.close_unit()

# Plot results
plt.plot(time_axis, buffers[channel])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()
