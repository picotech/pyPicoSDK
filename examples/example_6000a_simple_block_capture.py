import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
samples = 50_000
channel_a = psdk.CHANNEL.A
channel_b = psdk.CHANNEL.B
range = psdk.RANGE.V1

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Set capture timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500,
                                         unit=psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=range)
scope.set_channel(channel=channel_b, range=range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=0)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(
    TIMEBASE, samples, time_unit=psdk.TIME_UNIT.US
)

# Finish with PicoScope
scope.close_unit()

# Plot data to pyplot
plt.plot(time_axis, channel_buffer[channel_a], label='Channel A')
plt.plot(time_axis, channel_buffer[channel_b], label='Channel B')

# Add labels to pyplot
plt.xlabel("Time (\u03bcs)")
plt.ylabel("Amplitude (mV)")
plt.ylim(scope.get_plot_range())
plt.legend()
plt.grid(True)
plt.show()
