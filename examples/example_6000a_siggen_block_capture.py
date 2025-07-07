import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
timebase = 2
samples = 50_000
channel_a = psdk.CHANNEL.A
range = psdk.RANGE.V1

# SigGen variables
frequency = 100_000
pk2pk = 0.8
wave_type = psdk.WAVEFORM.SINE

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency, pk2pk, wave_type)

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=0)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(timebase, samples)

# Finish with PicoScope
scope.close_unit()

# Plot data to pyplot
plt.plot(time_axis, channel_buffer[channel_a])

# Add labels to pyplot
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.ylim(*scope.get_plot_range())
plt.grid(True)
plt.show()
