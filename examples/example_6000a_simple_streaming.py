import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
sample_interval = 1
sample_units = psdk.PICO_TIME_UNIT.US
samples = 5000
channel_a = psdk.CHANNEL.A
range = psdk.RANGE.V1

# Initialise PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=0)

# Run streaming capture
channels, time_axis = scope.run_simple_streaming_capture(
    sample_interval,
    sample_units,
    samples,
)

# Finish with PicoScope
scope.close_unit()

# Plot data to pyplot
plt.plot(time_axis, channels[channel_a])
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()

